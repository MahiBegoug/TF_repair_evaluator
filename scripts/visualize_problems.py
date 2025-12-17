"""
Visualize Problems Report

Generates an HTML report showing all problems/errors from the problems CSV,
displaying the problematic code blocks and error details.

Usage:
    python scripts/visualize_problems.py \
        --problems problems/problems.csv \
        --output problems_report.html
"""

import pandas as pd
import os
import argparse
import hashlib
import pickle
import html
from collections import namedtuple
from jinja2 import Environment, FileSystemLoader


def add_line_numbers_with_highlighting(code, block_start_line, error_start_line, error_end_line):
    """
    Add line numbers to code and mark the problematic lines with an indicator.
    
    Args:
        code: The code block content
        block_start_line: The starting line number of the code block in the file
        error_start_line: The starting line of the error
        error_end_line: The ending line of the error
    
    Returns:
        HTML string with line numbers and error markers
    """
    if not isinstance(code, str) or not code.strip():
        return ""
    
    lines = code.split('\n')
    result = []
    
    current_line = block_start_line if pd.notna(block_start_line) else 1
    error_start = error_start_line if pd.notna(error_start_line) else -1
    error_end = error_end_line if pd.notna(error_end_line) else -1
    
    for line in lines:
        is_error_line = error_start <= current_line <= error_end
        marker = "➤" if is_error_line else " "
        
        escaped_line = html.escape(line)
        result.append(f'<span class="code-line" data-line-num="{current_line}" data-marker="{marker}">{escaped_line}</span>')
        current_line += 1
    
    return '\n'.join(result)


def main():
    parser = argparse.ArgumentParser(description="Visualize problems/errors from validation")
    parser.add_argument("--problems", required=True, help="Path to problems CSV")
    parser.add_argument("--output", default="problems_report.html", help="Output HTML file")
    args = parser.parse_args()

    # Load problems CSV
    print(f"Loading {args.problems}...")
    problems = pd.read_csv(args.problems)
    
    print(f"Loaded {len(problems)} problems")
    
    # Group by project and file for better organization
    group_keys = ['project_name', 'filename']
    
    # Add optional grouping fields if they exist
    if 'severity' in problems.columns:
        problems['severity'] = problems['severity'].fillna('unknown')
    if 'summary' in problems.columns:
        problems['summary'] = problems['summary'].fillna('No summary')
    
    # Filter keys that actually exist
    available_keys = [k for k in group_keys if k in problems.columns]
    
    if not available_keys:
        print("Error: Required columns (project_name, filename) not found in problems CSV")
        return
    
    print(f"Grouping by: {available_keys}")
    
    # Sort by severity (error > warning > info)
    severity_order = {'error': 0, 'warning': 1, 'info': 2, 'unknown': 3}
    if 'severity' in problems.columns:
        problems['severity_order'] = problems['severity'].map(lambda x: severity_order.get(x, 3))
        problems = problems.sort_values(['severity_order', 'project_name', 'filename', 'line_start'])
        problems = problems.drop('severity_order', axis=1)
    else:
        problems = problems.sort_values(['project_name', 'filename'])
    
    # Get unique severity levels for filtering
    all_severities = []
    if 'severity' in problems.columns:
        all_severities = sorted(problems['severity'].unique().tolist())
    
    # Process code blocks with line numbers and highlighting
    print("Processing code blocks with line highlighting...")
    if 'impacted_block_content' in problems.columns:
        problems['highlighted_code'] = problems.apply(
            lambda row: add_line_numbers_with_highlighting(
                row.get('impacted_block_content', ''),
                row.get('impacted_block_start_line', 1),
                row.get('line_start', -1),
                row.get('line_end', -1)
            ),
            axis=1
        )
    else:
        problems['highlighted_code'] = ''
    
    groups = problems.groupby(available_keys)
    
    # Render template
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(os.path.join(script_dir, "templates")))
    template = env.get_template("problems_report.jinja")
    
    FileGroup = namedtuple('FileGroup', available_keys)
    
    print(f"Rendering problems report to {args.output}...")
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(template.render(
            groups=groups,
            FileGroup=FileGroup,
            all_severities=all_severities,
            total_problems=len(problems),
            md5=lambda d: hashlib.md5(pickle.dumps(d)).hexdigest()
        ))
    
    print(f"✅ Done! Report saved to: {args.output}")


if __name__ == "__main__":
    main()
