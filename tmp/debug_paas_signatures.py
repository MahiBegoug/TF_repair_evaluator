import pandas as pd
import os

# Load the files
problems_path = r"manual_inspection\alphagov__paas-cf\paas_problems.csv"
diagnostics_path = r"manual_inspection\alphagov__paas-cf\paas_diagnostics.csv"

problems = pd.read_csv(problems_path)
diagnostics = pd.read_csv(diagnostics_path)

print("--- BASELINE SIGNATURES ---")
for _, p in problems.iterrows():
    filename = str(p.get('filename', '') or '').strip()
    block_id = str(p.get('block_identifiers', '') or '').strip()
    summary = str(p.get('summary', '') or '').strip()
    detail = str(p.get('detail', '') or '').strip()
    
    sig = f"{filename}|{block_id}|{summary}|{detail}"
    print(f"'{sig}'")

print("\n--- DIAGNOSTIC SIGNATURES ---")
for _, d in diagnostics.iterrows():
    filename = str(d.get('filename', '') or '').strip()
    block_id = str(d.get('block_identifiers', '') or '').strip()
    summary = str(d.get('summary', '') or '').strip()
    detail = str(d.get('detail', '') or '').strip()
    
    sig = f"{filename}|{block_id}|{summary}|{detail}"
    print(f"'{sig}' (introduced: {d.get('introduced_in_this_iteration')})")
