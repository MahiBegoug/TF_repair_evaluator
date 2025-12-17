import toml
import pandas as pd
import os
import glob
import difflib
import hashlib
import pickle
from collections import namedtuple
from jinja2 import Environment, FileSystemLoader

import subprocess
import tempfile

def make_diff(original: str, modified: str) -> str:
    if not isinstance(original, str): original = ""
    if not isinstance(modified, str): modified = ""
    
    # Normalize line endings (git handles this, but good to be safe)
    original = original.replace('\r\n', '\n')
    modified = modified.replace('\r\n', '\n')
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', suffix='.tf') as f_orig, \
         tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', suffix='.tf') as f_mod:
        f_orig.write(original)
        f_mod.write(modified)
        f_orig_path = f_orig.name
        f_mod_path = f_mod.name

    try:
        # Run git diff --no-index --ignore-all-space (-w)
        # --unified=3 for context
        # --no-color to get plain text
        result = subprocess.run(
            ['git', 'diff', '--no-index', '--ignore-all-space', '--unified=3', '--no-color', f_orig_path, f_mod_path],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        diff_output = result.stdout
        
        # git diff output includes headers we want to strip
        # diff --git ...
        # index ...
        # --- a/...
        # +++ b/...
        
        lines = diff_output.splitlines(keepends=True)
        if len(lines) >= 4 and lines[0].startswith('diff --git'):
            # Strip the first 4 lines header
            return ''.join(lines[4:])
        
        return diff_output

    except Exception as e:
        print(f"Error running git diff: {e}")
        # Fallback to simple comparison or empty
        return ""
    finally:
        # Cleanup temp files
        if os.path.exists(f_orig_path):
            os.unlink(f_orig_path)
        if os.path.exists(f_mod_path):
            os.unlink(f_mod_path)

def get_snippet_from_problems(oid, problems_df):
    try:
        if oid not in problems_df.index:
            return f"OID not found in problems.csv: {oid}"
        
        # Get file content from problems.csv
        content = problems_df.loc[oid, 'file_content']
        if pd.isna(content):
            return "Content is NaN in problems.csv"
            
        return str(content)
    except Exception as e:
        return f"Error retrieving snippet: {e}"

def main():
    # Resolve paths relative to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    # Load config
    config_path = os.path.join(project_root, "experiments.toml")
    if not os.path.exists(config_path):
        print(f"Config file not found: {config_path}")
        return

    try:
        config = toml.load(config_path)
        output_dir = config.get("output_dir", "results")
        # Adjust output_dir to be relative to project root if it's a relative path
        if not os.path.isabs(output_dir):
            output_dir = os.path.join(project_root, output_dir)
    except Exception:
        output_dir = os.path.join(project_root, "results")

    # Load problems.csv
    problems_path = os.path.join(project_root, "diagnostics", "problems.csv")
    if not os.path.exists(problems_path):
        print(f"problems.csv not found at {problems_path}")
        return
        
    try:
        problems_df = pd.read_csv(problems_path)
        # Set OID as index for faster lookup
        if 'oid' in problems_df.columns:
            problems_df.set_index('oid', inplace=True)
        else:
            print("oid column missing in problems.csv")
            return
    except Exception as e:
        print(f"Error reading problems.csv: {e}")
        return

    # Find CSVs
    csv_files = glob.glob(os.path.join(output_dir, "*.csv"))
    if not csv_files:
        print(f"No CSV files found in {output_dir}")
        return

    print(f"Found {len(csv_files)} result files.")

    # Load all results
    dfs = []
    for f in csv_files:
        try:
            df = pd.read_csv(f)
            dfs.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")

    if not dfs:
        print("No data loaded.")
        return

    df_all = pd.concat(dfs, ignore_index=True)

    # Add snippet/original column and fix type
    print("Preparing content for diffs...")
    
    def get_diff_data(row, problems_df):
        oid = row['oid']
        if oid not in problems_df.index:
            return "OID not found", "", "Unknown"
            
        # Check for full file fix first
        if 'fixed_file' in row and pd.notna(row['fixed_file']):
            original = str(problems_df.loc[oid, 'file_content']) if 'file_content' in problems_df.columns else ""
            modified = str(row['fixed_file'])
            return original, modified, "Full File"
            
        # Check for block fix
        if 'fixed_block_content' in row and pd.notna(row['fixed_block_content']):
            original = str(problems_df.loc[oid, 'impacted_block_content']) if 'impacted_block_content' in problems_df.columns else ""
            modified = str(row['fixed_block_content'])
            return original, modified, "Block Snippet"
            
        return "No fix content found", "", "Error"

    # Apply the function to get original, modified, and type
    diff_data = df_all.apply(lambda row: get_diff_data(row, problems_df), axis=1)
    
    df_all['original_content'] = diff_data.apply(lambda x: x[0])
    df_all['modified_content'] = diff_data.apply(lambda x: x[1])
    df_all['fix_type'] = diff_data.apply(lambda x: x[2])

    # Add diff column
    print("Generating diffs...")
    df_all['diff'] = df_all.apply(
        lambda row: make_diff(row['original_content'], row['modified_content']), 
        axis=1
    )

    # Group by problem
    # Key: project_name, filename, line_start, line_end, severity, summary
    group_keys = ['project_name', 'filename', 'line_start', 'line_end', 'severity', 'summary']
    # Filter keys that actually exist in df
    group_keys = [k for k in group_keys if k in df_all.columns]
    
    groups = df_all.groupby(group_keys)

    # Get list of all models for the dropdown
    all_models = sorted(df_all['llm_name'].unique().tolist())
    
    # Get list of all iterations
    all_iterations = sorted(df_all['iteration_id'].unique().tolist())

    # Render template (Dynamic Report)
    # Template is in local templates/ dir (moved with script)
    env = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates")))
    template = env.get_template("dynamic_report.jinja")
    
    Problem = namedtuple('Problem', group_keys)
    
    output_html = os.path.join(project_root, "fix_report.html")
    
    print(f"Rendering dynamic report to {output_html}...")
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(template.render(
            groups=groups,
            Problem=Problem,
            all_models=all_models,
            all_iterations=all_iterations,
            md5=lambda d: hashlib.md5(pickle.dumps(d)).hexdigest()
        ))
    
    print("Done!")

if __name__ == "__main__":
    main()
