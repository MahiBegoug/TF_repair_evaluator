import os
import pandas as pd
from repair_pipeline.repair_driver import RepairEvaluator
from repair_pipeline.parallel_driver import ParallelRepairEvaluator

def run_test():
    # Setup Main Evaluator
    evaluator = RepairEvaluator(
        clones_root="clones",
        problems_dataset="problems/problems.csv",
        output_csv="tmp/test_parallel_diagnostics.csv",
        outcomes_csv="tmp/test_parallel_outcomes.csv",
        clear_existing=True
    )

    # Create a 1-row DataFrame for alphagov__paas-cf
    df = pd.read_csv("llm_responses/codellama_subset_20.csv")
    paas_df = df[df['filename'].str.contains("paas-cf")].head(1)

    print(f"Running parallel evaluation for project: {paas_df.iloc[0]['project_name']}")

    # Run Parallel
    parallel_evaluator = ParallelRepairEvaluator(evaluator)
    parallel_evaluator.evaluate(paas_df, num_workers=1)

    # Verify results
    if os.path.exists("tmp/test_parallel_diagnostics.csv"):
        res_df = pd.read_csv("tmp/test_parallel_diagnostics.csv")
        print("\n--- PARALLEL RESULTS ---")
        print(res_df[['block_identifiers', 'summary', 'introduced_in_this_iteration']])
    else:
        print("FAILURE: No diagnostics file produced.")

if __name__ == '__main__':
    run_test()
