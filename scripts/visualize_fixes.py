"""
Visualize LLM Fixes with Validation Status

Generates an HTML report showing diffs between original and fixed code,
with validation status indicators (✓ fixed, ✗ still has errors, etc.).

Usage:
    python scripts/visualize_fixes.py \\
        --llm-responses llm_responses/gpt_oss_20b_snippet_only_example.csv \\
        --repair-results llms_fixes_results/gpt_oss_20b_snippet_only_example_repair_results.csv \\
        --problems problems/problems.csv \\
        --output fix_report.html
"""

import pandas as pd
import os
import argparse
import hashlib
import pickle
from collections import namedtuple
from jinja2 import Environment, FileSystemLoader
import subprocess
import tempfile


def _normalize_path_for_oid(path: str) -> str:
    """
    Match TFRepair path normalization used for oid/specific_oid hashing.

    - Convert backslashes to forward slashes
    - Strip whitespace
    - Ensure we keep only the trailing `clones/...` portion if present
    """
    if not path:
        return ""
    p = str(path).strip().replace("\\", "/")
    if "clones/" in p:
        p = "clones/" + p.split("clones/")[-1]
    return p


def _normalize_text_for_oid(text: str) -> str:
    """
    Match terraform_validation.extractor.DiagnosticsExtractor.normalize_for_oid.

    Important: baseline hashes keep quotes/backticks; we only lowercase + trim.
    """
    if not text:
        return ""
    return str(text).lower().strip()


def compute_specific_oid(row: dict) -> str:
    filename = _normalize_path_for_oid(row.get("filename", ""))
    line_start = str(row.get("line_start", "")).strip()
    line_end = str(row.get("line_end", "")).strip()
    summary = _normalize_text_for_oid(row.get("summary", ""))
    detail = _normalize_text_for_oid(row.get("detail", ""))
    base = f"{filename}|{line_start}|{line_end}|{summary}|{detail}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]


def _normalize_for_ws_compare(text: str) -> str:
    """Whitespace-insensitive comparison helper for 'did anything really change?'."""
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    # Strip all whitespace, keep punctuation/quotes/etc.
    return "".join(text.split())


def make_diff(original: str, modified: str, ignore_whitespace: bool = False) -> str:
    """Generate git-style diff between original and modified content."""
    if not isinstance(original, str):
        original = ""
    if not isinstance(modified, str):
        modified = ""
    
    # Normalize line endings
    original = original.replace('\\r\\n', '\\n')
    modified = modified.replace('\\r\\n', '\\n')
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', suffix='.tf') as f_orig, \
         tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', suffix='.tf') as f_mod:
        f_orig.write(original)
        f_mod.write(modified)
        f_orig_path = f_orig.name
        f_mod_path = f_mod.name

    try:
        # Run git diff with more context to show full blocks
        cmd = ['git', 'diff', '--no-index', '--unified=10', '--no-color', f_orig_path, f_mod_path]
        if ignore_whitespace:
            cmd.insert(3, '--ignore-all-space')
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        diff_output = result.stdout
        
        # Strip the first 4 header lines from git diff
        lines = diff_output.splitlines(keepends=False)
        if len(lines) >= 4 and lines[0].startswith('diff --git'):
            diff_lines = lines[4:]
        else:
            diff_lines = lines
        
        # Process diff with actual line numbers
        import html
        import re
        
        result_lines = []
        old_line_num = 0
        new_line_num = 0
        
        for line in diff_lines:
            # Check for hunk header (e.g., @@ -1,5 +1,5 @@)
            hunk_match = re.match(r'^@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@', line)
            if hunk_match:
                old_line_num = int(hunk_match.group(1))
                new_line_num = int(hunk_match.group(2))
                result_lines.append(f'<span class="line hunk-header">{html.escape(line)}</span>')
                continue
            
            # Determine line type and numbers
            if line.startswith('-'):
                # Deletion: show old line number only
                line_num_display = f'{old_line_num:4} {"":4}'
                old_line_num += 1
            elif line.startswith('+'):
                # Addition: show new line number only
                line_num_display = f'{"":4} {new_line_num:4}'
                new_line_num += 1
            else:
                # Context: show both line numbers
                line_num_display = f'{old_line_num:4} {new_line_num:4}'
                old_line_num += 1
                new_line_num += 1
            
            escaped_line = html.escape(line)
            result_lines.append(f'<span class="line" data-line-nums="{line_num_display}">{escaped_line}</span>')
        
        return '\n'.join(result_lines)

    except Exception as e:
        print(f"Error running git diff: {e}")
        return ""
    finally:
        # Cleanup temp files
        if os.path.exists(f_orig_path):
            os.unlink(f_orig_path)
        if os.path.exists(f_mod_path):
            os.unlink(f_mod_path)


def main():
    parser = argparse.ArgumentParser(description="Visualize LLM fixes with validation status")
    parser.add_argument("--llm-responses", required=True, help="Path to LLM responses CSV (contains fixed_block_content)")
    parser.add_argument("--repair-results", help="Path to repair results CSV (contains validation status)")
    parser.add_argument("--new-diagnostics", help="Path to new diagnostics CSV (errors introduced by fixes)")
    parser.add_argument("--problems", default="problems/problems.csv", help="Path to problems CSV")
    parser.add_argument("--output", default="fix_report.html", help="Output HTML file")
    parser.add_argument("--verbose", action="store_true", help="Print verbose processing/debug logs")
    parser.add_argument("--ignore-whitespace", action="store_true", help="Ignore all whitespace in diff rendering (git --ignore-all-space)")
    args = parser.parse_args()

    # Load CSVs
    print(f"Loading {args.llm_responses}...")
    llm_responses = pd.read_csv(args.llm_responses)
    # Avoid "nan" showing up in the HTML for free-text columns
    for c in ["project_name", "filename", "llm_name", "summary", "detail", "fixed_block_content", "fixed_file", "explanation"]:
        if c in llm_responses.columns:
            llm_responses[c] = llm_responses[c].fillna("")
    
    repair_results = None
    if args.repair_results:
        print(f"Loading {args.repair_results}...")
        repair_results = pd.read_csv(args.repair_results)
    
    new_diagnostics = None
    if args.new_diagnostics:
        print(f"Loading {args.new_diagnostics}...")
        new_diagnostics = pd.read_csv(args.new_diagnostics)
    
    print(f"Loading {args.problems}...")
    problems = pd.read_csv(args.problems)

    if 'oid' not in problems.columns:
        print("Warning: 'oid' column missing in problems.csv")
        return

    # Build indices for lookups. In TFRepair, the LLM input `oid` is not always the same
    # as the baseline dataset `oid`, so prefer joining/lookup by `specific_oid` when present.
    problems_by_oid = problems.set_index('oid', drop=False)
    problems_by_specific_oid = None
    if 'specific_oid' in problems.columns:
        problems_by_specific_oid = problems.set_index('specific_oid', drop=False)

    # Merge llm_responses with repair_results (if available)
    if repair_results is not None:
        # The repair pipeline may output `oid` as the matched baseline oid (for consistent tracking),
        # which does not necessarily equal the original LLM-response `oid`. `specific_oid` is the
        # stable join key when hash parity is maintained, so we prefer it when available.
        if 'specific_oid' not in llm_responses.columns:
            llm_responses = llm_responses.copy()
            llm_responses['specific_oid'] = llm_responses.apply(
                lambda r: compute_specific_oid(r.to_dict()),
                axis=1
            )

        if 'specific_oid' in repair_results.columns and 'specific_oid' in llm_responses.columns:
            join_keys = ['specific_oid', 'iteration_id']
        else:
            join_keys = ['oid', 'iteration_id']

        if args.verbose:
            print(f"Merging repair results on keys: {join_keys}")

        df_all = llm_responses.merge(
            repair_results,
            on=join_keys,
            how='left',
            suffixes=('', '_result')
        )
        print(f"Merged {len(df_all)} records")
    else:
        df_all = llm_responses
        print(f"Loaded {len(df_all)} records (no repair results)")
    
    # Process new diagnostics if available
    if new_diagnostics is not None:
        print("Processing new diagnostics...")
        # Group new diagnostics by original_problem_oid + iteration_id
        # This links new errors back to the fix that caused them
        new_diag_grouped = new_diagnostics.groupby(['original_problem_oid', 'iteration_id'])
        
        def get_new_errors(row, problems_df, new_diag_df):
            """Get list of new errors introduced by this fix"""
            key = (row['oid'], row['iteration_id'])
            if key not in new_diag_df.groups:
                if args.verbose:
                    print(f"  [DEBUG] Key {key} not found in new_diag groups. Available: {list(new_diag_df.groups.keys())[:3]}")
                return []
            
            if args.verbose:
                print(f"  [DEBUG] Processing key {key}, found {len(new_diag_df.get_group(key))} errors")
            
            # Get original error details for filtering
            orig_line_start = row.get('line_start', None)
            orig_line_end = row.get('line_end', None)
            orig_summary = row.get('summary', '')
            orig_severity = row.get('severity', '')
            
            # Get all new diagnostics for this fix
            new_errs = new_diag_df.get_group(key)
            
            result = []
            for _, err in new_errs.iterrows():
                # Check if the new error is on the same line as original
                same_line = False
                if orig_line_start and 'line_start' in err:
                    err_line = err['line_start']
                    # Check if error line overlaps with original range
                    same_line = (orig_line_start <= err_line <= (orig_line_end if orig_line_end else orig_line_start))
                
                # Use new tracking columns if available
                is_new_to_dataset = err.get('is_new_to_dataset', None)
                introduced_in_this_iteration = err.get('introduced_in_this_iteration', None)
                first_seen_in = err.get('first_seen_in', '')
                exists_in_iterations = err.get('exists_in_iterations', '')
                
                # Determine error category
                if err.get('is_original_error', False):
                    error_category = 'original'
                elif introduced_in_this_iteration:
                    error_category = 'introduced_this_iteration'
                elif is_new_to_dataset:
                    error_category = 'truly_new'
                elif exists_in_iterations:
                    error_category = 'exists_in_other_experiments'
                else:
                    # Fallback for old data without new columns
                    error_category = 'unknown'
                
                # SKIP ORIGINAL ERRORS - they're not "new" errors!
                # Original errors existed in baseline and shouldn't be shown in "Issues Found After Fix"
                if error_category == 'original':
                    if args.verbose:
                        print(f"  [SKIP] Original error on line {err.get('line_start')}: {err.get('summary', '')[:50]}...")
                    continue
                
                err_summary = err.get('summary', '')
                err_severity = err.get('severity', '')
                
                # Debug logging
                if args.verbose:
                    print(f"  [INCLUDE] {error_category.upper()} on line {err.get('line_start')}: {err_summary[:50]}...")
                    if error_category == 'introduced_this_iteration':
                        print(f"    → This iteration introduced it (first_seen_in: {first_seen_in})")
                    elif error_category == 'exists_in_other_experiments':
                        print(f"    → Also in iterations: {exists_in_iterations}")
                
                result.append({
                    'severity': err_severity if err_severity else 'unknown',
                    'summary': err_summary if err_summary else 'No summary',
                    'detail': err.get('detail', ''),
                    'line_start': err.get('line_start', '?'),
                    'line_end': err.get('line_end', '?'),
                    'same_line': same_line,
                    'error_category': error_category,
                    'first_seen_in': first_seen_in,
                    'exists_in_iterations': exists_in_iterations
                })
            
            # Deduplicate errors based on severity, summary, detail, and line
            # Include 'detail' to avoid over-deduplication of similar errors with different specifics
            seen = set()
            unique_result = []
            for err in result:
                # Use first 100 chars of detail to avoid issues with very long details
                # Handle NaN/float values from pandas
                detail_val = err.get('detail', '')
                if isinstance(detail_val, str):
                    detail_key = detail_val[:100]
                else:
                    detail_key = ''
                key = (err['severity'], err['summary'], detail_key, err['line_start'], err['line_end'])
                if key not in seen:
                    seen.add(key)
                    unique_result.append(err)
            
            return unique_result
        
        df_all['new_errors'] = df_all.apply(
            lambda row: get_new_errors(row, problems, new_diag_grouped), 
            axis=1
        )
    else:
        df_all['new_errors'] = [[] for _ in range(len(df_all))]


    # Add original content and generate diffs
    print("Preparing content for diffs...")
    
    def _select_problem_row(row):
        """
        Resolve the baseline problem row to use for original content.

        Prefer specific_oid (stable) and then fall back to baseline oid (oid_result),
        and finally to the input oid.
        """
        spec = row.get('specific_oid', None)
        if problems_by_specific_oid is not None and spec is not None and spec in problems_by_specific_oid.index:
            pr = problems_by_specific_oid.loc[spec]
            # Handle any accidental duplicates by picking the first.
            if isinstance(pr, pd.DataFrame):
                return pr.iloc[0]
            return pr

        oid_result = row.get('oid_result', None)
        if oid_result is not None and oid_result in problems_by_oid.index:
            return problems_by_oid.loc[oid_result]

        oid = row.get('oid', None)
        if oid is not None and oid in problems_by_oid.index:
            return problems_by_oid.loc[oid]

        return None

    def get_diff_data(row, _problems_unused):
        p_row = _select_problem_row(row)
        if p_row is None:
            return "Problem not found", "", "Error"

        # Get original content from problems
        original = str(p_row.get('impacted_block_content', "")) if 'impacted_block_content' in p_row else ""
        
        # Get modified content from LLM responses
        if 'fixed_block_content' in row and pd.notna(row['fixed_block_content']):
            modified = str(row['fixed_block_content'])
            fix_type = "Block Snippet"
        elif 'fixed_file' in row and pd.notna(row['fixed_file']):
            modified = str(row['fixed_file'])
            fix_type = "Full File"
            original = str(p_row.get('file_content', "")) if 'file_content' in p_row else ""
        else:
            modified = ""
            fix_type = "No Fix"
            
        return original, modified, fix_type

    # Apply the function
    diff_data = df_all.apply(lambda row: get_diff_data(row, problems), axis=1)
    
    df_all['original_content'] = diff_data.apply(lambda x: x[0])
    df_all['modified_content'] = diff_data.apply(lambda x: x[1])
    df_all['fix_type'] = diff_data.apply(lambda x: x[2])

    # Flags to explain why a diff may look "empty" to a human reviewer
    df_all['diff_same_exact'] = df_all.apply(
        lambda r: (r.get('original_content', '') == r.get('modified_content', '')),
        axis=1
    )
    df_all['diff_same_ignore_ws'] = df_all.apply(
        lambda r: (_normalize_for_ws_compare(r.get('original_content', '')) == _normalize_for_ws_compare(r.get('modified_content', ''))),
        axis=1
    )
    
    # Add original problem detail and summary
    def get_problem_info(row, _problems_unused):
        """Get original problem detail and summary"""
        p_row = _select_problem_row(row)
        if p_row is None:
            return "", ""

        detail = str(p_row.get('detail', '')) if 'detail' in p_row and pd.notna(p_row.get('detail', None)) else ""
        summary = str(p_row.get('summary', '')) if 'summary' in p_row and pd.notna(p_row.get('summary', None)) else ""
        
        return detail, summary
    
    problem_info = df_all.apply(lambda row: get_problem_info(row, problems), axis=1)
    df_all['original_problem_detail'] = problem_info.apply(lambda x: x[0])
    df_all['original_problem_summary'] = problem_info.apply(lambda x: x[1])

    # Generate diffs
    print("Generating diffs...")
    df_all['diff'] = df_all.apply(
        lambda row: make_diff(row['original_content'], row['modified_content'], ignore_whitespace=args.ignore_whitespace),
        axis=1
    )

    # Group by problem (using fields that identify the original error)
    group_keys = ['project_name', 'filename', 'line_start', 'line_end']
    if 'severity' in df_all.columns:
        group_keys.append('severity')
    if 'summary' in df_all.columns:
        group_keys.append('summary')
    
    # Filter keys that actually exist
    group_keys = [k for k in group_keys if k in df_all.columns]
    
    print(f"Grouping by: {group_keys}")
    groups = df_all.groupby(group_keys)

    # Get list of all models and iterations for UI
    all_models = sorted(df_all['llm_name'].unique().tolist()) if 'llm_name' in df_all.columns else []
    all_iterations = sorted(df_all['iteration_id'].unique().tolist())

    # Render template
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(os.path.join(script_dir, "templates")))
    template = env.get_template("dynamic_report.jinja")
    
    Problem = namedtuple('Problem', group_keys)
    
    print(f"Rendering dynamic report to {args.output}...")
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(template.render(
            groups=groups,
            Problem=Problem,
            all_models=all_models,
            all_iterations=all_iterations,
            md5=lambda d: hashlib.md5(pickle.dumps(d)).hexdigest()
        ))
    
    print(f"[OK] Done! Report saved to: {args.output}")


if __name__ == "__main__":
    main()
