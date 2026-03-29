import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd

from repair_pipeline.apply_fix import FixApplier
from terraform_validation.writer import DiagnosticsWriter


def process_module_repair_tasks(module_tasks, clones_root, repair_mode, evaluator_kwargs):
    """
    Worker function to process a batch of repair attempts for a single module directory.

    Safety model:
    - Terraform validation reads a whole module directory and can create shared state (.terraform*).
    - Fix application mutates files in-place.
    - We therefore run tasks sequentially per module_dir to avoid concurrent mutation/validation
      within the same module.
    """
    # Delayed import avoids circular imports in subprocesses.
    from repair_pipeline.repair_driver import RepairEvaluator

    evaluator = RepairEvaluator(clones_root=clones_root, repair_mode=repair_mode, **evaluator_kwargs)
    results = []

    for task_data in module_tasks:
        row = task_data.get("row", {}) or {}
        project = task_data.get("project")
        original_file = task_data.get("original_file")
        fixed_file_content = task_data.get("fixed_file_content")
        start_line = task_data.get("start_line")
        end_line = task_data.get("end_line")

        iteration_id = row.get("iteration_id")
        oid = row.get("oid")

        backup_path = None
        try:
            baseline_errors = evaluator._get_baseline_errors(original_file, project)

            backup_path = FixApplier.apply_fix(
                original_file,
                fixed_file_content,
                start_line=start_line,
                end_line=end_line,
            )

            extracted_rows = evaluator._apply_and_validate(
                original_file,
                project,
                fixed_file_content,
                start_line,
                end_line,
                iteration_id,
                baseline_errors=baseline_errors,
                original_problem_oid=oid,
                write_to_csv=False,  # main process does all I/O
            )

            error_counts = evaluator._calculate_error_metrics(
                extracted_rows,
                original_file,
                baseline_errors,
                target_oid=oid,
            )

            resolution_metrics = evaluator._evaluate_resolution_metrics(
                row,
                extracted_rows,
                start_line,
                end_line,
                fixed_file_content,
            )

            outcome_row = evaluator._create_outcome_row(row, original_file, resolution_metrics, error_counts)

            results.append(
                {
                    "success": True,
                    "outcome_row": outcome_row,
                    "extracted_rows": extracted_rows,
                    "oid": oid,
                    "iteration": iteration_id,
                    "module": os.path.dirname(original_file) if original_file else None,
                }
            )
        except Exception as e:
            results.append(
                {
                    "success": False,
                    "error": str(e),
                    "oid": oid,
                    "iteration": iteration_id,
                    "module": os.path.dirname(original_file) if original_file else None,
                }
            )
        finally:
            if backup_path and original_file:
                FixApplier.restore_original(original_file, backup_path)

    return results


class ParallelRepairEvaluator:
    """Handles parallel execution of repair attempts."""

    def __init__(self, parent_evaluator):
        self.parent = parent_evaluator

    def evaluate(self, df, num_workers=4):
        """
        Dispatch tasks to a process pool, grouping work by module directory.

        This preserves correctness when the same module_dir appears across different iteration_id
        values, because those tasks will be executed sequentially within the same worker batch.
        """
        print(f"\n[PARALLEL] Starting parallel evaluation with {num_workers} workers...")

        evaluator_kwargs = {
            "output_csv": self.parent.output_csv,
            "outcomes_csv": self.parent.outcomes_csv,
            "problems_dataset": self.parent.problems_dataset_path,
            "debug_matching": self.parent.debug_matching,
        }

        tasks_by_module = {}  # norm_module_dir -> [task_data]

        for _, row in df.iterrows():
            project = self.parent._extract_project_name(row)
            if not project:
                continue

            original_file = self.parent._get_original_file_path(row["filename"])
            fixed_file_content, start_line, end_line = self.parent._get_fix_content_and_coordinates(row)

            if fixed_file_content is None or pd.isna(fixed_file_content):
                continue

            module_dir = os.path.normpath(os.path.dirname(original_file))
            tasks_by_module.setdefault(module_dir, []).append(
                {
                    "row": row.to_dict(),
                    "project": project,
                    "original_file": original_file,
                    "fixed_file_content": fixed_file_content,
                    "start_line": start_line,
                    "end_line": end_line,
                }
            )

        total_tasks = sum(len(v) for v in tasks_by_module.values())
        total_modules = len(tasks_by_module)
        print(f"[PARALLEL] Queued {total_tasks} tasks across {total_modules} unique modules.")

        if total_tasks == 0:
            print("[PARALLEL] No tasks to run.")
            return

        results_count = 0
        start_time = time.time()

        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = {
                executor.submit(
                    process_module_repair_tasks,
                    module_tasks,
                    self.parent.clones_root,
                    self.parent.repair_mode,
                    evaluator_kwargs,
                ): (module_dir, len(module_tasks))
                for module_dir, module_tasks in tasks_by_module.items()
            }

            for future in as_completed(futures):
                module_dir, module_task_count = futures[future]

                try:
                    module_results = future.result()
                except Exception as e:
                    # Entire module batch crashed (rare but possible). Mark them as "done" and continue.
                    results_count += module_task_count
                    print(f"[REJECT] Worker crashed for module {module_dir}: {e}")
                    continue

                for res in module_results:
                    results_count += 1
                    if res.get("success"):
                        if res.get("extracted_rows"):
                            DiagnosticsWriter.write_rows(
                                res["extracted_rows"],
                                self.parent.output_csv,
                                iteration_id=res.get("iteration"),
                                original_problem_oid=res.get("oid"),
                            )

                        pd.DataFrame([res["outcome_row"]]).to_csv(
                            self.parent.outcomes_csv,
                            mode="a",
                            header=False,
                            index=False,
                        )
                    else:
                        print(f"[REJECT] Failed task for OID {res.get('oid')}: {res.get('error')}")

                    if results_count % 10 == 0 or results_count == total_tasks:
                        elapsed = time.time() - start_time
                        avg = elapsed / max(1, results_count)
                        eta = avg * (total_tasks - results_count)
                        print(f"[PROGRESS] {results_count}/{total_tasks} completed. ETA: {eta:.1f}s")

        total_time = time.time() - start_time
        print(
            f"\n[PARALLEL] Completed in {total_time:.1f}s "
            f"(Average: {total_time / max(1, total_tasks):.2f}s per task)"
        )

