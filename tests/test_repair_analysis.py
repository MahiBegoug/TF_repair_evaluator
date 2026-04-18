import tempfile
import unittest
from pathlib import Path

import pandas as pd

from repair_analyzer.repair_analysis import (
    build_fixed_types_overall,
    build_introduced_error_audit,
    build_introduced_types_overall,
    build_iteration_summary,
    generate_repair_analysis_artifacts,
    load_repair_analysis_data,
)


class TestRepairAnalysis(unittest.TestCase):
    def test_iteration_aware_analysis_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            fixes_csv = tmp / "fixes.csv"
            outcomes_csv = tmp / "outcomes.csv"
            diagnostics_csv = tmp / "diagnostics.csv"
            diagnostics_oid_csv = tmp / "diagnostics_oid.csv"
            problems_csv = tmp / "problems.csv"
            analysis_dir = tmp / "analysis"

            pd.DataFrame(
                [
                    {
                        "iteration_id": "1",
                        "project_name": "proj",
                        "working_directory": "clones/proj",
                        "oid": "oid-a",
                        "specific_oid": "spec-a",
                        "filename": "clones/proj/main.tf",
                        "severity": "warning",
                        "summary": "Deprecated attribute",
                        "detail": "name is deprecated",
                    },
                    {
                        "iteration_id": "2",
                        "project_name": "proj",
                        "working_directory": "clones/proj",
                        "oid": "oid-a",
                        "specific_oid": "spec-a",
                        "filename": "clones/proj/main.tf",
                        "severity": "warning",
                        "summary": "Deprecated attribute",
                        "detail": "name is deprecated",
                    },
                    {
                        "iteration_id": "1",
                        "project_name": "proj",
                        "working_directory": "clones/proj",
                        "oid": "oid-b",
                        "specific_oid": "spec-b",
                        "filename": "clones/proj/vars.tf",
                        "severity": "error",
                        "summary": "Missing required argument",
                        "detail": "bucket is required",
                    },
                    {
                        "iteration_id": "2",
                        "project_name": "proj",
                        "working_directory": "clones/proj",
                        "oid": "oid-b",
                        "specific_oid": "spec-b",
                        "filename": "clones/proj/vars.tf",
                        "severity": "error",
                        "summary": "Missing required argument",
                        "detail": "bucket is required",
                    },
                ]
            ).to_csv(fixes_csv, index=False)

            pd.DataFrame(
                [
                    {
                        "specific_oid": "spec-a",
                        "iteration_id": "1",
                        "is_fixed": True,
                        "module_fix_introduced_errors": 0,
                        "module_original_errors_remaining": 0,
                    },
                    {
                        "specific_oid": "spec-a",
                        "iteration_id": "2",
                        "is_fixed": False,
                        "module_fix_introduced_errors": 1,
                        "module_original_errors_remaining": 1,
                    },
                    {
                        "specific_oid": "spec-b",
                        "iteration_id": "1",
                        "is_fixed": False,
                        "module_fix_introduced_errors": 2,
                        "module_original_errors_remaining": 1,
                    },
                    {
                        "specific_oid": "spec-b",
                        "iteration_id": "2",
                        "is_fixed": True,
                        "module_fix_introduced_errors": 1,
                        "module_original_errors_remaining": 0,
                    },
                ]
            ).to_csv(outcomes_csv, index=False)

            pd.DataFrame(
                [
                    {
                        "specific_oid": "diag-a-2",
                        "project_name": "proj",
                        "working_directory": "clones/proj",
                        "original_problem_specific_oid": "spec-a",
                        "iteration_id": "2",
                        "summary": "Reference to undeclared resource",
                        "severity": "error",
                        "filename": "clones/proj/other.tf",
                        "line_start": 12,
                        "block_type": "resource",
                        "block_identifiers": "other",
                        "introduced_in_this_iteration": True,
                        "is_new_to_dataset": True,
                        "exists_in_iterations": "",
                    },
                    {
                        "specific_oid": "diag-b-1a",
                        "project_name": "proj",
                        "working_directory": "clones/proj",
                        "original_problem_specific_oid": "spec-b",
                        "iteration_id": "1",
                        "summary": "Unsupported argument",
                        "severity": "error",
                        "filename": "clones/proj/vars.tf",
                        "line_start": 8,
                        "block_type": "resource",
                        "block_identifiers": "bucket",
                        "introduced_in_this_iteration": True,
                        "is_new_to_dataset": True,
                        "exists_in_iterations": "",
                    },
                    {
                        "specific_oid": "diag-b-1b",
                        "project_name": "proj",
                        "working_directory": "clones/proj",
                        "original_problem_specific_oid": "spec-b",
                        "iteration_id": "1",
                        "summary": "Unsupported argument",
                        "severity": "error",
                        "filename": "clones/proj/vars.tf",
                        "line_start": 20,
                        "block_type": "resource",
                        "block_identifiers": "other_bucket",
                        "introduced_in_this_iteration": True,
                        "is_new_to_dataset": False,
                        "exists_in_iterations": "2",
                    },
                    {
                        "specific_oid": "diag-b-2",
                        "project_name": "proj",
                        "working_directory": "clones/proj",
                        "original_problem_specific_oid": "spec-b",
                        "iteration_id": "2",
                        "summary": "Unsupported argument",
                        "severity": "error",
                        "filename": "clones/proj/vars.tf",
                        "line_start": 25,
                        "block_type": "resource",
                        "block_identifiers": "other_bucket",
                        "introduced_in_this_iteration": True,
                        "is_new_to_dataset": False,
                        "exists_in_iterations": "1",
                    },
                ]
            ).to_csv(diagnostics_csv, index=False)

            # Same diagnostics, but using only the location OID field (older schema). The analyzer should infer
            # `original_problem_specific_oid` via (iteration_id, original_problem_oid) -> specific_oid mapping.
            pd.DataFrame(
                [
                    {
                        "specific_oid": "diag-a-2",
                        "project_name": "proj",
                        "working_directory": "clones/proj",
                        "original_problem_oid": "oid-a",
                        "iteration_id": "2",
                        "summary": "Reference to undeclared resource",
                        "severity": "error",
                        "filename": "clones/proj/other.tf",
                        "line_start": 12,
                        "block_type": "resource",
                        "block_identifiers": "other",
                        "introduced_in_this_iteration": True,
                        "is_new_to_dataset": True,
                        "exists_in_iterations": "",
                    },
                    {
                        "specific_oid": "diag-b-1a",
                        "project_name": "proj",
                        "working_directory": "clones/proj",
                        "original_problem_oid": "oid-b",
                        "iteration_id": "1",
                        "summary": "Unsupported argument",
                        "severity": "error",
                        "filename": "clones/proj/vars.tf",
                        "line_start": 8,
                        "block_type": "resource",
                        "block_identifiers": "bucket",
                        "introduced_in_this_iteration": True,
                        "is_new_to_dataset": True,
                        "exists_in_iterations": "",
                    },
                    {
                        "specific_oid": "diag-b-1b",
                        "project_name": "proj",
                        "working_directory": "clones/proj",
                        "original_problem_oid": "oid-b",
                        "iteration_id": "1",
                        "summary": "Unsupported argument",
                        "severity": "error",
                        "filename": "clones/proj/vars.tf",
                        "line_start": 20,
                        "block_type": "resource",
                        "block_identifiers": "other_bucket",
                        "introduced_in_this_iteration": True,
                        "is_new_to_dataset": False,
                        "exists_in_iterations": "2",
                    },
                    {
                        "specific_oid": "diag-b-2",
                        "project_name": "proj",
                        "working_directory": "clones/proj",
                        "original_problem_oid": "oid-b",
                        "iteration_id": "2",
                        "summary": "Unsupported argument",
                        "severity": "error",
                        "filename": "clones/proj/vars.tf",
                        "line_start": 25,
                        "block_type": "resource",
                        "block_identifiers": "other_bucket",
                        "introduced_in_this_iteration": True,
                        "is_new_to_dataset": False,
                        "exists_in_iterations": "1",
                    },
                ]
            ).to_csv(diagnostics_oid_csv, index=False)

            pd.DataFrame(
                [
                    {
                        "specific_oid": "spec-a",
                        "block_type": "resource",
                        "block_identifiers": "main",
                        "impacted_block_start_line": 1,
                        "impacted_block_end_line": 10,
                    },
                    {
                        "specific_oid": "spec-b",
                        "block_type": "resource",
                        "block_identifiers": "bucket",
                        "impacted_block_start_line": 5,
                        "impacted_block_end_line": 15,
                    },
                ]
            ).to_csv(problems_csv, index=False)

            attempts_df, diagnostics_df, _ = load_repair_analysis_data(
                fixes_csv=str(fixes_csv),
                outcomes_csv=str(outcomes_csv),
                diagnostics_csv=str(diagnostics_csv),
                problems_csv=str(problems_csv),
            )
            self.assertIn("module_fix_introduced_errors_outcome_raw", attempts_df.columns)
            self.assertIn("introduced_count_gap_raw_minus_classified", attempts_df.columns)
            self.assertIn("introduced_count_match", attempts_df.columns)
            self.assertIn("strict_success_from_outcome_raw", attempts_df.columns)
            self.assertIn("strict_success_from_classified_diagnostics", attempts_df.columns)
            self.assertIn("strict_success_agreement", attempts_df.columns)

            iteration_summary_df = build_iteration_summary(attempts_df)
            fixed_types_df = build_fixed_types_overall(attempts_df)
            introduced_audit_df = build_introduced_error_audit(attempts_df)
            introduced_types_df = build_introduced_types_overall(attempts_df, diagnostics_df)

            self.assertEqual(iteration_summary_df.loc[0, "repairs_attempted"], 2)
            self.assertEqual(iteration_summary_df.loc[0, "fixed_repairs"], 1)
            self.assertEqual(iteration_summary_df.loc[0, "strict_fixed_repairs"], 1)
            self.assertEqual(iteration_summary_df.loc[0, "introduced_diagnostics"], 2)
            self.assertEqual(iteration_summary_df.loc[0, "new_problems_fixed"], 1)
            self.assertAlmostEqual(iteration_summary_df.loc[0, "cumulative_fix_coverage"], 0.5)

            self.assertEqual(iteration_summary_df.loc[1, "fixed_repairs"], 1)
            self.assertEqual(iteration_summary_df.loc[1, "strict_fixed_repairs"], 0)
            self.assertEqual(iteration_summary_df.loc[1, "introduced_diagnostics"], 2)
            self.assertEqual(iteration_summary_df.loc[1, "new_problems_fixed"], 1)
            self.assertAlmostEqual(iteration_summary_df.loc[1, "cumulative_fix_coverage"], 1.0)

            deprecated_row = fixed_types_df[fixed_types_df["original_summary"] == "Deprecated attribute"].iloc[0]
            self.assertEqual(deprecated_row["fixed_repairs"], 1)
            self.assertEqual(deprecated_row["strict_fixed_repairs"], 1)

            unsupported_row = introduced_types_df[introduced_types_df["introduced_summary"] == "Unsupported argument"].iloc[0]
            self.assertEqual(unsupported_row["introduced_diagnostics"], 3)
            self.assertEqual(unsupported_row["truly_new_diagnostics"], 1)
            self.assertEqual(unsupported_row["cross_iteration_repeats"], 2)
            self.assertEqual(unsupported_row["same_block_diagnostics"], 1)
            self.assertEqual(unsupported_row["same_file_other_block_diagnostics"], 2)
            self.assertEqual(unsupported_row["same_module_other_file_diagnostics"], 0)

            ref_row = introduced_types_df[introduced_types_df["introduced_summary"] == "Reference to undeclared resource"].iloc[0]
            self.assertEqual(ref_row["same_module_other_file_diagnostics"], 1)
            self.assertEqual(introduced_audit_df.loc[0, "repairs_with_matching_introduced_counts"], 4)
            self.assertEqual(introduced_audit_df.loc[0, "repairs_with_mismatching_introduced_counts"], 0)
            self.assertAlmostEqual(introduced_audit_df.loc[0, "introduced_count_match_rate"], 1.0)
            self.assertEqual(introduced_audit_df.loc[0, "strict_success_disagreement_repairs"], 0)

            # Validate inference-based join logic (diagnostics only provide original_problem_oid).
            attempts_df2, diagnostics_df2, _ = load_repair_analysis_data(
                fixes_csv=str(fixes_csv),
                outcomes_csv=str(outcomes_csv),
                diagnostics_csv=str(diagnostics_oid_csv),
                problems_csv=str(problems_csv),
            )
            # Inference should produce origin_problem_key == the original specific_oid from fixes/outcomes.
            inferred_keys = diagnostics_df2[diagnostics_df2["introduced_in_this_iteration"]]["origin_problem_key"].unique().tolist()
            self.assertIn("spec-a", inferred_keys)
            self.assertIn("spec-b", inferred_keys)
            introduced_types_df2 = build_introduced_types_overall(attempts_df2, diagnostics_df2)
            unsupported_row2 = introduced_types_df2[introduced_types_df2["introduced_summary"] == "Unsupported argument"].iloc[0]
            self.assertEqual(unsupported_row2["introduced_diagnostics"], 3)

            outputs = generate_repair_analysis_artifacts(
                fixes_csv=str(fixes_csv),
                outcomes_csv=str(outcomes_csv),
                diagnostics_csv=str(diagnostics_csv),
                analysis_dir=str(analysis_dir),
                problems_csv=str(problems_csv),
                report_title="Test Report",
            )

            self.assertTrue(Path(outputs["html_report"]).exists())
            self.assertTrue(Path(outputs["iteration_summary_csv"]).exists())
            self.assertTrue(Path(outputs["introduced_diagnostics_detailed_csv"]).exists())
            self.assertTrue(Path(outputs["summary_resolution_overall_csv"]).exists())
            self.assertTrue(Path(outputs["solved_unsolved_figure_svg"]).exists())
            self.assertTrue(Path(outputs["introduced_scope_figure_svg"]).exists())
            self.assertTrue(Path(outputs["top_fixed_types_figure_svg"]).exists())
            self.assertTrue(Path(outputs["top_introduced_types_figure_svg"]).exists())
            self.assertTrue(Path(outputs["summary_resolution_radar_figure_svg"]).exists())
            self.assertTrue(Path(outputs["paired_distribution_figure_svg"]).exists())
            self.assertTrue(Path(outputs["solved_unsolved_figure_pdf"]).exists())
            self.assertTrue(Path(outputs["introduced_scope_figure_pdf"]).exists())
            self.assertTrue(Path(outputs["top_fixed_types_figure_pdf"]).exists())
            self.assertTrue(Path(outputs["top_introduced_types_figure_pdf"]).exists())
            self.assertTrue(Path(outputs["summary_resolution_radar_figure_pdf"]).exists())
            self.assertTrue(Path(outputs["paired_distribution_figure_pdf"]).exists())
            self.assertTrue(Path(outputs["introduced_error_audit_csv"]).exists())
            self.assertTrue(Path(outputs["introduced_error_audit_mismatches_csv"]).exists())
            attempt_level_df = pd.read_csv(outputs["attempt_level_csv"])
            self.assertIn("module_fix_introduced_errors_outcome_raw", attempt_level_df.columns)
            self.assertIn("introduced_count_gap_raw_minus_classified", attempt_level_df.columns)
            self.assertIn("introduced_count_match", attempt_level_df.columns)
            self.assertIn("strict_success_agreement", attempt_level_df.columns)
            html_text = Path(outputs["html_report"]).read_text(encoding="utf-8")
            self.assertIn("Figure 1. Solved and Unresolved Problems Across Iterations", html_text)
            self.assertIn("Figure 4. Introduced Diagnostics by Scope Across Iterations", html_text)
            self.assertIn("Figure 7. Summary-Level Strict Resolution Profile (%)", html_text)
            self.assertIn("Problem Lifecycle Across Iterations", html_text)
            self.assertIn("Introduced Error Audit", html_text)

    def test_introduced_error_audit_flags_mismatch(self):
        attempts_df = pd.DataFrame(
            [
                {
                    "iteration_id": "1",
                    "iteration_order": 1,
                    "original_problem_key": "spec-1",
                    "problem_type_label": "Missing required argument [resource, error]",
                    "original_filename": "clones/proj/main.tf",
                    "is_fixed": True,
                    "has_outcome_row": True,
                    "module_fix_introduced_errors_outcome_raw": 1,
                    "introduced_diagnostics_from_csv": 0,
                }
            ]
        )

        audit_df = build_introduced_error_audit(attempts_df)
        self.assertEqual(audit_df.loc[0, "repairs_with_mismatching_introduced_counts"], 1)
        self.assertEqual(audit_df.loc[0, "introduced_total_gap_raw_minus_classified"], 1)
        self.assertEqual(audit_df.loc[0, "strict_success_disagreement_repairs"], 1)

    def test_ambiguous_origin_oid_join_raises(self):
        # If diagnostics only provide location-based OIDs and (iteration_id, oid) maps to multiple specific problems,
        # the analyzer should fail closed rather than silently misattribute introduced diagnostics.
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            fixes_csv = tmp / "fixes.csv"
            outcomes_csv = tmp / "outcomes.csv"
            diagnostics_csv = tmp / "diagnostics.csv"

            pd.DataFrame(
                [
                    {
                        "iteration_id": "1",
                        "project_name": "proj",
                        "working_directory": "clones/proj",
                        "oid": "same-oid",
                        "specific_oid": "spec-1",
                        "filename": "clones/proj/main.tf",
                        "severity": "error",
                        "summary": "Missing required argument",
                        "detail": "bucket is required",
                    },
                    {
                        "iteration_id": "1",
                        "project_name": "proj",
                        "working_directory": "clones/proj",
                        "oid": "same-oid",
                        "specific_oid": "spec-2",
                        "filename": "clones/proj/vars.tf",
                        "severity": "error",
                        "summary": "Unsupported argument",
                        "detail": "name is unsupported",
                    },
                ]
            ).to_csv(fixes_csv, index=False)

            pd.DataFrame(
                [
                    {"specific_oid": "spec-1", "iteration_id": "1", "is_fixed": False, "module_fix_introduced_errors": 1, "module_original_errors_remaining": 1},
                    {"specific_oid": "spec-2", "iteration_id": "1", "is_fixed": False, "module_fix_introduced_errors": 1, "module_original_errors_remaining": 1},
                ]
            ).to_csv(outcomes_csv, index=False)

            pd.DataFrame(
                [
                    {
                        "specific_oid": "diag-1",
                        "project_name": "proj",
                        "working_directory": "clones/proj",
                        "original_problem_oid": "same-oid",
                        "iteration_id": "1",
                        "summary": "Reference to undeclared resource",
                        "severity": "error",
                        "filename": "clones/proj/other.tf",
                        "line_start": 12,
                        "block_type": "resource",
                        "block_identifiers": "other",
                        "introduced_in_this_iteration": True,
                        "is_new_to_dataset": True,
                        "exists_in_iterations": "",
                    }
                ]
            ).to_csv(diagnostics_csv, index=False)

            with self.assertRaises(ValueError):
                load_repair_analysis_data(
                    fixes_csv=str(fixes_csv),
                    outcomes_csv=str(outcomes_csv),
                    diagnostics_csv=str(diagnostics_csv),
                    problems_csv=None,
                )


if __name__ == "__main__":
    unittest.main()
