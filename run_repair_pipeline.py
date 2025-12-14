import os
import glob
import argparse
import subprocess
import sys

def main():
    parser = argparse.ArgumentParser(description="Run repair pipeline on raw LLM responses")
    parser.add_argument("--config", default="repair_config.json", help="Path to configuration file")
    args = parser.parse_args()

    import json
    try:
        with open(args.config, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Config file not found: {args.config}")
        return

    responses_config = config.get("responses", {})
    # Support both new nested structure and old flat structure (fallback)
    input_dir = responses_config.get("input_dir", config.get("input_dir", "llm_responses"))
    target_models = responses_config.get("models", config.get("models", []))
    
    output_dir = config.get("output_dir", "llms_fixes_results")
    clones_dir = config.get("clones_dir", "../TFReproducer/clones")
    repair_mode = config.get("repair_mode", "auto")

    if not os.path.exists(input_dir):
        print(f"Error: Input directory '{input_dir}' does not exist.")
        return

    os.makedirs(output_dir, exist_ok=True)

    csv_files = glob.glob(os.path.join(input_dir, "*.csv"))
    
    if not csv_files:
        print(f"No CSV files found in {input_dir}")
        return

    print(f"Found {len(csv_files)} files to process.")

    for csv_file in csv_files:
        filename = os.path.basename(csv_file)
        
        # Filter by model name if specified
        if target_models:
            matched = False
            for tm in target_models:
                if tm in filename:
                    matched = True
                    break
            if not matched:
                continue

        print(f"\nProcessing: {filename}")
        
        # Define output paths
        # We keep the same filename for the outcomes file in the output directory
        outcomes_csv = os.path.join(output_dir, filename)
        
        # We also generate a detailed diagnostics file
        diagnostics_filename = filename.replace(".csv", "_diagnostics.csv")
        diagnostics_csv = os.path.join(output_dir, diagnostics_filename)

        cmd = [
            sys.executable, "main.py",
            "--fixes-csv", csv_file,
            "--outcomes-csv", outcomes_csv,
            "--output-csv", diagnostics_csv,
            "--clones-dir", clones_dir,
            "--repair-mode", repair_mode
        ]
        
        try:
            subprocess.run(cmd, check=True)
            print(f"Success! Results saved to {outcomes_csv}")
        except subprocess.CalledProcessError as e:
            print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    main()
