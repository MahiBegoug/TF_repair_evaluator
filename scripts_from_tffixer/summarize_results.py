import toml
import pandas as pd
import os
import argparse

def main():
    # Resolve paths relative to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    parser = argparse.ArgumentParser(description="Summarize experiment results")
    parser.add_argument("--config", default=os.path.join(project_root, "experiments.toml"), help="Path to TOML config file")
    args = parser.parse_args()

    if not os.path.exists(args.config):
        print(f"Config file not found: {args.config}")
        return

    try:
        config = toml.load(args.config)
    except Exception as e:
        print(f"Error loading config: {e}")
        return

    models = config.get("models", {})
    experiments = config.get("experiments", {})
    output_dir = config.get("output_dir", "results")
    
    # Adjust output_dir if relative
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(project_root, output_dir)

    if not models or not experiments:
        print("No models or experiments defined in config.")
        return

    # Prepare data for DataFrame
    # Rows: Experiments
    # Columns: Models
    
    data = {}
    
    for model_name in models.keys():
        model_col = []
        for exp_name in experiments.keys():
            # Construct filename as done in run_experiments.py
            model_name_clean = model_name.split("/")[-1]
            safe_model = model_name_clean.replace("-", "_")
            filename = f"{safe_model}_{exp_name}.csv"
            filepath = os.path.join(output_dir, filename)
            
            count = 0
            if os.path.exists(filepath):
                try:
                    # Count rows, assuming header exists
                    df = pd.read_csv(filepath)
                    count = len(df)
                except Exception:
                    count = "Err"
            
            model_col.append(count)
        data[model_name] = model_col

    # Create DataFrame
    df_summary = pd.DataFrame(data, index=list(experiments.keys()))
    
    # Print formatted table
    print("\nExperiment Summary (Count of processed instances):")
    print("=" * 80)
    # Use to_string to print the whole table
    print(df_summary.to_string())
    print("=" * 80)

if __name__ == "__main__":
    main()
