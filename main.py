import argparse
import os
from repair_pipeline.repair_driver import RepairEvaluator

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run TF Repair Evaluation")
    parser.add_argument("--clones-dir", default="../TFReproducer/clones", help="Path to the clones directory")
    parser.add_argument("--output-csv", default="repair_results.csv", help="Output CSV for repair results")
    parser.add_argument("--outcomes-csv", default="repair_outcomes.csv", help="Output CSV for repair outcomes (plausible/not)")
    parser.add_argument("--fixes-csv", required=True, help="Input CSV with LLM fixes")
    
    args = parser.parse_args()
    
    # Ensure clones dir is absolute or correctly relative
    clones_dir = os.path.abspath(args.clones_dir)
    
    print(f"Using clones directory: {clones_dir}")
    print(f"Reading fixes from: {args.fixes_csv}")
    print(f"Writing results to: {args.output_csv}")
    
    evaluator = RepairEvaluator(
        output_csv=args.output_csv,
        outcomes_csv=args.outcomes_csv,
        clones_root=clones_dir
    )
    
    evaluator.evaluate_repairs(
        llm_fixes_csv=args.fixes_csv
    )
