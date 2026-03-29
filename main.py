import argparse
import os
from repair_pipeline.repair_driver import RepairEvaluator

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run TF Repair Evaluation")
    parser.add_argument("--clones-dir", default="../TFReproducer/clones", help="Path to the clones directory")
    parser.add_argument("--output-csv", default="repair_results.csv", help="Output CSV for repair results")
    parser.add_argument("--outcomes-csv", default="repair_outcomes.csv", help="Output CSV for repair outcomes (plausible/not)")
    parser.add_argument("--fixes-csv", required=True, help="Input CSV with LLM fixes")
    parser.add_argument("--repair-mode", default="auto", choices=["auto", "block", "file"], help="Mode of repair: block or file")
    parser.add_argument("--problems-dataset", default=None, help="Path to problems dataset for block coordinates")
    parser.add_argument("--parallel", action="store_true", help="Enable parallel evaluation")
    parser.add_argument("--parallel-workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Delete existing output/outcomes CSVs before writing (fresh run)"
    )
    parser.add_argument(
        "--debug-matching",
        action="store_true",
        help="Print verbose diagnostics about OID/specific_oid matching and block coordinate lookups"
    )
    
    args = parser.parse_args()
    
    # Ensure clones dir is absolute or correctly relative
    clones_dir = os.path.abspath(args.clones_dir)
    
    print(f"Using clones directory: {clones_dir}")
    print(f"Reading fixes from: {args.fixes_csv}")
    print(f"Writing results to: {args.output_csv}")
    
    evaluator = RepairEvaluator(
        output_csv=args.output_csv,
        outcomes_csv=args.outcomes_csv,
        clones_root=clones_dir,
        repair_mode=args.repair_mode,
        problems_dataset=args.problems_dataset,
        clear_existing=args.clear_existing,
        debug_matching=args.debug_matching
    )
    
    evaluator.evaluate_repairs(
        llm_fixes_csv=args.fixes_csv,
        parallel=args.parallel,
        num_workers=args.parallel_workers
    )
