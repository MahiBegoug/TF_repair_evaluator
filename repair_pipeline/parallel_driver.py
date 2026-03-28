import os
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import Manager
import time

from repair_pipeline.apply_fix import FixApplier
from terraform_validation.writer import DiagnosticsWriter

def process_single_repair_task(task_data, clones_root, repair_mode, lock, evaluator_kwargs):
    """
    Worker function to process a single repair attempt.
    This must be a standalone function for ProcessPoolExecutor.
    """
    # Delay import to avoid circular dependencies or initialization issues in subprocesses
    from repair_pipeline.repair_driver import RepairEvaluator
    
    row = task_data['row']
    project = task_data['project']
    original_file = task_data['original_file']
    fixed_file_content = task_data['fixed_file_content']
    start_line = task_data['start_line']
    end_line = task_data['end_line']
    iteration_id = row.get("iteration_id")
    oid = row.get("oid")

    # Initialize a local evaluator instance for this worker
    evaluator = RepairEvaluator(clones_root=clones_root, repair_mode=repair_mode, **evaluator_kwargs)
    
    # Use the shared lock for this specific module directory
    with lock:
        try:
            # 1. BASELINE: Capture errors from original file (cached)
            baseline_errors = evaluator._get_baseline_errors(original_file, project)

            # 2. APPLY: Inject code
            backup_path = FixApplier.apply_fix(
                original_file,
                fixed_file_content,
                start_line=start_line,
                end_line=end_line
            )

            # 3. VALIDATE: Run terraform validate
            # write_to_csv=False is critical here; main process handles I/O
            extracted_rows = evaluator._apply_and_validate(
                original_file, project, fixed_file_content, 
                start_line, end_line, iteration_id,
                baseline_errors=baseline_errors,
                original_problem_oid=oid,
                write_to_csv=False
            )

            # 4. METRICS: Calculate error counts
            error_counts = evaluator._calculate_error_metrics(
                extracted_rows, 
                original_file, 
                baseline_errors, 
                target_oid=oid
            )

            # 5. RESOLUTION: Evaluate if error was resolved
            resolution_metrics = evaluator._evaluate_resolution_metrics(
                row, extracted_rows, start_line, end_line, fixed_file_content
            )

            # 6. OUTCOME: Create outcome row
            outcome_row = evaluator._create_outcome_row(
                row, original_file, resolution_metrics, error_counts
            )
            
            return {
                "success": True,
                "outcome_row": outcome_row,
                "extracted_rows": extracted_rows,
                "oid": oid,
                "iteration": iteration_id,
                "module": os.path.dirname(original_file)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "oid": oid,
                "iteration": iteration_id
            }
        finally:
            # 7. RESTORE: Revert to original state
            if 'backup_path' in locals():
                FixApplier.restore_original(original_file, backup_path)


class ParallelRepairEvaluator:
    """Handles parallel execution of repair attempts."""

    def __init__(self, parent_evaluator):
        self.parent = parent_evaluator

    def evaluate(self, df, num_workers=4):
        """Dispatches tasks to process pool with directory-level locking."""
        print(f"\n[PARALLEL] Starting parallel evaluation with {num_workers} workers...")
        
        manager = Manager()
        df['module_dir'] = df['filename'].apply(lambda f: os.path.dirname(self.parent._get_original_file_path(f)))
        unique_dirs = df['module_dir'].unique()
        dir_locks = {d: manager.Lock() for d in unique_dirs}
        
        evaluator_kwargs = {
            "output_csv": self.parent.output_csv,
            "outcomes_csv": self.parent.outcomes_csv,
            "problems_dataset": self.parent.problems_dataset_path
        }
        
        tasks = []
        for idx, row in df.iterrows():
            project = self.parent._extract_project_name(row)
            if not project: continue
            
            original_file = self.parent._get_original_file_path(row["filename"])
            fixed_file_content, start_line, end_line = self.parent._get_fix_content_and_coordinates(row)
            
            if fixed_file_content is None or pd.isna(fixed_file_content): continue

            tasks.append({
                'task_data': {
                    'row': row.to_dict(),
                    'project': project,
                    'original_file': original_file,
                    'fixed_file_content': fixed_file_content,
                    'start_line': start_line,
                    'end_line': end_line
                },
                'module_dir': os.path.dirname(original_file)
            })

        print(f"[PARALLEL] Queued {len(tasks)} tasks across {len(unique_dirs)} unique modules.")
        
        results_count = 0
        start_time = time.time()
        
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(process_single_repair_task, t['task_data'], self.parent.clones_root, self.parent.repair_mode, dir_locks[t['module_dir']], evaluator_kwargs) for t in tasks]
            
            for future in as_completed(futures):
                res = future.result()
                results_count += 1
                
                if res["success"]:
                    # Centralized I/O for thread safety
                    if res["extracted_rows"]:
                        DiagnosticsWriter.write_rows(
                            res["extracted_rows"], 
                            self.parent.output_csv,
                            iteration_id=res["iteration"],
                            original_problem_oid=res["oid"]
                        )
                    
                    pd.DataFrame([res["outcome_row"]]).to_csv(self.parent.outcomes_csv, mode='a', header=False, index=False)
                    
                    if results_count % 10 == 0 or results_count == len(tasks):
                        elapsed = time.time() - start_time
                        avg = elapsed / results_count
                        eta = avg * (len(tasks) - results_count)
                        print(f"[PROGRESS] {results_count}/{len(tasks)} completed. ETA: {eta:.1f}s")
                else:
                    print(f"[REJECT] Failed task for OID {res.get('oid')}: {res.get('error')}")

        total_time = time.time() - start_time
        print(f"\n[PARALLEL] ✓ Completed in {total_time:.1f}s (Average: {total_time/len(tasks):.2f}s per task)")
