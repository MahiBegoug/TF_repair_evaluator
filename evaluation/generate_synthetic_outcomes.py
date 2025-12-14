import pandas as pd
import random
import os
import argparse

def generate_data(output_dir="evaluation/data"):
    models = {
        "gemini": 0.8,       # High performance
        "chatgpt4.1": 0.5,   # Medium performance
        "codellama": 0.2     # Low performance
    }
    
    n_problems = 10
    n_samples = 20
    
    problems = []
    
    # Generate problems
    for i in range(n_problems):
        oid = f"problem_{i}"
        filename = f"file_{i}.tf"
        problems.append({"oid": oid, "filename": filename})
        
    # Save problems.csv
    problems_dir = "problems"
    os.makedirs(problems_dir, exist_ok=True)
    
    problems_df = pd.DataFrame(problems)
    problems_df.to_csv(os.path.join(problems_dir, "problems.csv"), index=False)
    print(f"Generated {os.path.join(problems_dir, 'problems.csv')}")

    # Generate fixes for each model
    for model, success_rate in models.items():
        fixes = []
        for i in range(n_problems):
            oid = f"problem_{i}"
            filename = f"file_{i}.tf"
            for j in range(n_samples):
                is_success = random.random() < success_rate
                fixes.append({
                    "oid": oid,
                    "filename": filename,
                    "iteration_id": j,
                    "plausible_fix": is_success
                })
        
        fixes_df = pd.DataFrame(fixes)
        output_path = os.path.join(output_dir, f"{model}_synthetic_fixes.csv")
        fixes_df.to_csv(output_path, index=False)
        print(f"Generated {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic repair outcomes")
    parser.add_argument("--output-dir", default="evaluation/data", help="Directory to save generated CSVs")
    args = parser.parse_args()
    
    generate_data(args.output_dir)
