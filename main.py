import argparse
import os
from repair_analyzer.repair_analysis import generate_repair_analysis_artifacts
from repair_pipeline.clone_lock import clone_tree_lock
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
    parser.add_argument(
        "--analysis-dir",
        default=None,
        help="Optional directory for iteration-aware repair analysis outputs"
    )
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Skip generation of iteration-aware repair analysis artifacts"
    )
    parser.add_argument(
        "--validation-timeout-seconds",
        type=int,
        default=None,
        help="Optional timeout for each terraform validate invocation"
    )
    
    args = parser.parse_args()
    
    # Ensure clones dir is absolute or correctly relative
    clones_dir = os.path.abspath(args.clones_dir)
    
    print(f"Using clones directory: {clones_dir}")
    print(f"Reading fixes from: {args.fixes_csv}")
    print(f"Writing results to: {args.output_csv}")
    
    with clone_tree_lock(clones_dir):
        evaluator = RepairEvaluator(
            output_csv=args.output_csv,
            outcomes_csv=args.outcomes_csv,
            clones_root=clones_dir,
            repair_mode=args.repair_mode,
            problems_dataset=args.problems_dataset,
            clear_existing=args.clear_existing,
            debug_matching=args.debug_matching,
            validation_timeout_seconds=args.validation_timeout_seconds,
        )
        
        evaluator.evaluate_repairs(
            llm_fixes_csv=args.fixes_csv,
            parallel=args.parallel,
            num_workers=args.parallel_workers
        )

    if not args.skip_analysis:
        analysis_outputs = generate_repair_analysis_artifacts(
            fixes_csv=args.fixes_csv,
            outcomes_csv=args.outcomes_csv,
            diagnostics_csv=args.output_csv,
            analysis_dir=args.analysis_dir,
            problems_csv=args.problems_dataset,
            report_title=f"TFRepair Analysis for {os.path.basename(args.fixes_csv)}",
        )
        print("Analysis artifacts:")
        for name, path in analysis_outputs.items():
            print(f"  {name}: {path}")
