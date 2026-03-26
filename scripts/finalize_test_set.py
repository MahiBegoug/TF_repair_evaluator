import pandas as pd
import os

input_file = "llm_responses/CodeLlama_34b_Instruct_hf_docs_snippet_marked_code_only_xml.csv"
output_file = "llm_responses/test_5_projects_16_iterations.csv"

# Read only header to find column names
cols = pd.read_csv(input_file, nrows=0).columns.tolist()
print(f"Columns: {cols}")

# Find OIDs with exactly 16 iterations
df = pd.read_csv(input_file, usecols=['oid', 'iteration_id'])
counts = df.groupby('oid')['iteration_id'].count()
valid_oids = counts[counts == 16].index.tolist()

print(f"Found {len(valid_oids)} OIDs with 16 iterations.")

if len(valid_oids) < 5:
    print("Warning: Fewer than 5 OIDs have 16 iterations. Picking all available.")
    selected_oids = valid_oids
else:
    # Pick first 5 for stability
    selected_oids = valid_oids[:5]

print(f"Selected OIDs: {selected_oids}")

# Filter the original file
# We read it in chunks to avoid memory issues with 27MB file (though 27MB is fine, let's be safe)
reader = pd.read_csv(input_file, chunksize=10000)
filtered_chunks = []
for chunk in reader:
    filtered_chunks.append(chunk[chunk['oid'].isin(selected_oids)])

subset_df = pd.concat(filtered_chunks)
subset_df.to_csv(output_file, index=False)
print(f"Created {output_file} with {len(subset_df)} rows.")

# Also update problems dataset to include THESE OIDs
problems_df = pd.read_csv("problems/problems.csv")
benchmark_df = problems_df[problems_df['oid'].isin(selected_oids)]
benchmark_df.to_csv("problems/benchmark_unique_diagnostics.csv", index=False)
print(f"Created problems/benchmark_unique_diagnostics.csv with {len(benchmark_df)} unique problems.")
