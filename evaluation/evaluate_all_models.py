import os
import glob
import subprocess
import argparse

def main():
    parser = argparse.ArgumentParser(description="Evaluate all LLM fixes in llms_fixes_results")
    parser.add_argument("--config", default="evaluation/evaluation_config.json", help="Path to configuration file")
    args = parser.parse_args()

    import json
    try:
        with open(args.config, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Config file not found: {args.config}")
        return

    fixes_dir = config.get("fixes_dir", "llms_fixes_results")
    output_dir = config.get("output_dir", "evaluation/data")
    results_dir = config.get("results_dir", "evaluation/results")
    clones_dir = config.get("clones_dir", "../TFReproducer/clones")
    k_values = config.get("k_values", [1, 5, 10])
    
    # New config options
    target_models = config.get("models", [])
    generate_synthetic = config.get("generate_synthetic_data", False)
    data_type = config.get("data_type", "all") # "synthetic", "real", "all"
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(fixes_dir, exist_ok=True)
    
    problems_dir = "problems"
    problems_csv = os.path.join(problems_dir, "problems.csv")
    os.makedirs(problems_dir, exist_ok=True)

    # 0. Generate synthetic data if requested
    if generate_synthetic:
        print("\n=== Generating Synthetic Data ===")
        cmd_gen = [
            "python", "evaluation/generate_synthetic_outcomes.py",
            "--output-dir", fixes_dir
        ]
        print(f"Running: {' '.join(cmd_gen)}")
        subprocess.run(cmd_gen, check=True)

    # 1. Ensure problems.csv exists (we assume it's already generated or we can generate it)
    # For now, we assume the user has run generate_synthetic_outcomes.py or we should extract it from the fixes.
    # But since we are evaluating real data, we might need to rely on the fixes CSVs themselves.
    # The calculate_pass_at_k.py expects a problems.csv. 
    # Let's assume for this workflow we generate a problems.csv from the fixes file being evaluated 
    # OR we just point to a common one if available.
    
    # Actually, calculate_pass_at_k.py needs a problems.csv to know the total set of problems (n).
    # If we don't have a master problems list, we can infer it from the fixes CSV if it contains all problems.
    
    csv_files = glob.glob(os.path.join(fixes_dir, "*.csv"))
    
    csv_files = glob.glob(os.path.join(fixes_dir, "*.csv"))
    
    for csv_file in csv_files:
        filename = os.path.basename(csv_file)
        model_name = filename.replace("llm_fullfile_repair_results_", "").replace(".csv", "")
        
        # Filter by data type
        is_synthetic = "synthetic" in filename
        if data_type == "synthetic" and not is_synthetic:
            continue
        if data_type == "real" and is_synthetic:
            continue
            
        # Filter by model name
        if target_models:
            # Check if any of the target models is a substring of the filename/model_name
            # This is a simple check; might need refinement if model names overlap
            matched = False
            for tm in target_models:
                if tm in model_name:
                    matched = True
                    break
            if not matched:
                continue
        
        print(f"\n=== Evaluating Model: {model_name} ({filename}) ===")
        
        # Define output paths
        outcomes_csv = os.path.join(output_dir, f"{model_name}_outcomes.csv")
        results_csv = os.path.join(output_dir, f"{model_name}_results.csv")
        
        # Check if the input CSV is already an outcome file (has 'plausible_fix' column)
        import pandas as pd
        try:
            df = pd.read_csv(csv_file)
            is_outcome_file = 'plausible_fix' in df.columns
        except Exception:
            is_outcome_file = False

        if is_outcome_file:
            print(f"  -> Detected pre-computed outcomes. Skipping repair step.")
            # If it's an outcome file, we just copy it to the output dir as the outcomes csv
            import shutil
            shutil.copy(csv_file, outcomes_csv)
        else:
            # 1. Run main.py to evaluate repairs
            cmd = [
                "python", "main.py",
                "--fixes-csv", csv_file,
                "--output-csv", results_csv,
                "--outcomes-csv", outcomes_csv,
                "--clones-dir", clones_dir
            ]
            
            print(f"Running: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
        
        # 2. Use the shared problems.csv
        if not os.path.exists(problems_csv):
             print(f"Error: Problems file not found at {problems_csv}")
             continue
        
        # 3. Calculate pass@k
        pass_at_k_csv = os.path.join(results_dir, f"{model_name}_pass_at_k.csv")
        cmd_calc = [
            "python", "evaluation/calculate_pass_at_k.py",
            "--problems-csv", problems_csv,
            "--fixes-csv", outcomes_csv,
            "--k-values", *[str(k) for k in k_values],
            "--save-to", pass_at_k_csv
        ]
        
        print(f"Calculating pass@k for {model_name}...")
        subprocess.run(cmd_calc, check=True)

    # Aggregate all pass@k results
    print("\n=== Aggregated Results ===")
    all_results = []
    pass_at_k_files = glob.glob(os.path.join(results_dir, "*_pass_at_k.csv"))
    for pk_file in pass_at_k_files:
        try:
            df = pd.read_csv(pk_file)
            all_results.append(df)
        except Exception as e:
            print(f"Error reading {pk_file}: {e}")
    
    if all_results:
        summary_df = pd.concat(all_results, ignore_index=True)
        summary_csv = os.path.join(results_dir, "summary_pass_at_k.csv")
        summary_df.to_csv(summary_csv, index=False)
        print(summary_df)
        print(f"\nSummary saved to {summary_csv}")
    else:
        print("No pass@k results found.")

if __name__ == "__main__":
    main()
