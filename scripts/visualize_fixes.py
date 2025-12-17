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


def make_diff(original: str, modified: str) -> str:
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
        result = subprocess.run(
            ['git', 'diff', '--no-index', '--ignore-all-space', '--unified=10', '--no-color', f_orig_path, f_mod_path],
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
    args = parser.parse_args()

    # Load CSVs
    print(f"Loading {args.llm_responses}...")
    llm_responses = pd.read_csv(args.llm_responses)
    
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
    
    # Set OID as index for problems for faster lookup
    if 'oid' in problems.columns:
        problems.set_index('oid', inplace=True)
    else:
        print("Warning: 'oid' column missing in problems.csv")
        return

    # Merge llm_responses with repair_results (if available) on oid + iteration_id
    if repair_results is not None:
        df_all = llm_responses.merge(
            repair_results, 
            on=['oid', 'iteration_id'], 
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
        # Group new diagnostics by oid + iteration_id
        new_diag_grouped = new_diagnostics.groupby(['oid', 'iteration_id'])
        
        def get_new_errors(row, problems_df, new_diag_df):
            """Get list of new errors introduced by this fix"""
            key = (row['oid'], row['iteration_id'])
            if key not in new_diag_df.groups:
                return []
            
            # Get original error line range
            orig_line_start = row['line_start'] if 'line_start' in row else None
            orig_line_end = row['line_end'] if 'line_end' in row else None
            
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
                
                result.append({
                    'severity': err.get('severity', 'unknown'),
                    'summary': err.get('summary', 'No summary'),
                    'detail': err.get('detail', ''),
                    'line_start': err.get('line_start', '?'),
                    'line_end': err.get('line_end', '?'),
                    'same_line': same_line
                })
            return result
        
        df_all['new_errors'] = df_all.apply(
            lambda row: get_new_errors(row, problems, new_diag_grouped), 
            axis=1
        )
    else:
        df_all['new_errors'] = [[] for _ in range(len(df_all))]


    # Add original content and generate diffs
    print("Preparing content for diffs...")
    
    def get_diff_data(row, problems_df):
        oid = row['oid']
        if oid not in problems_df.index:
            return "OID not found", "", "Error"
            
        # Get original content from problems
        original = str(problems_df.loc[oid, 'impacted_block_content']) if 'impacted_block_content' in problems_df.columns else ""
        
        # Get modified content from LLM responses
        if 'fixed_block_content' in row and pd.notna(row['fixed_block_content']):
            modified = str(row['fixed_block_content'])
            fix_type = "Block Snippet"
        elif 'fixed_file' in row and pd.notna(row['fixed_file']):
            modified = str(row['fixed_file'])
            fix_type = "Full File"
            original = str(problems_df.loc[oid, 'file_content']) if 'file_content' in problems_df.columns else ""
        else:
            modified = ""
            fix_type = "No Fix"
            
        return original, modified, fix_type

    # Apply the function
    diff_data = df_all.apply(lambda row: get_diff_data(row, problems), axis=1)
    
    df_all['original_content'] = diff_data.apply(lambda x: x[0])
    df_all['modified_content'] = diff_data.apply(lambda x: x[1])
    df_all['fix_type'] = diff_data.apply(lambda x: x[2])
    
    # Add original problem detail and summary
    def get_problem_info(row, problems_df):
        """Get original problem detail and summary"""
        oid = row['oid']
        if oid not in problems_df.index:
            return "", ""
        
        detail = str(problems_df.loc[oid, 'detail']) if 'detail' in problems_df.columns and pd.notna(problems_df.loc[oid, 'detail']) else ""
        summary = str(problems_df.loc[oid, 'summary']) if 'summary' in problems_df.columns and pd.notna(problems_df.loc[oid, 'summary']) else ""
        
        return detail, summary
    
    problem_info = df_all.apply(lambda row: get_problem_info(row, problems), axis=1)
    df_all['original_problem_detail'] = problem_info.apply(lambda x: x[0])
    df_all['original_problem_summary'] = problem_info.apply(lambda x: x[1])

    # Generate diffs
    print("Generating diffs...")
    df_all['diff'] = df_all.apply(
        lambda row: make_diff(row['original_content'], row['modified_content']), 
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
    
    print(f"✅ Done! Report saved to: {args.output}")


if __name__ == "__main__":
    main()
