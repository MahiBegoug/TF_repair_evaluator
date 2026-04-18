import os

import pandas as pd

from repair_analyzer.constants import SCOPE_LEVELS
from repair_analyzer.utils import (
    _build_problem_type_label,
    _coerce_bool,
    _coerce_int,
    _ensure_specific_oid,
    _iteration_sort_key,
    _normalize_path_text,
    _safe_text,
)


def _match_same_block(row) -> bool:
    original_filename = _normalize_path_text(row.get("original_filename"))
    introduced_filename = _normalize_path_text(row.get("filename"))
    if not original_filename or original_filename != introduced_filename:
        return False

    original_block_type = _safe_text(row.get("original_block_type"), default="")
    introduced_block_type = _safe_text(row.get("block_type"), default="")
    original_block_identifiers = _safe_text(row.get("original_block_identifiers"), default="")
    introduced_block_identifiers = _safe_text(row.get("block_identifiers"), default="")

    if (
        original_block_type
        and introduced_block_type
        and original_block_identifiers
        and introduced_block_identifiers
        and original_block_type == introduced_block_type
        and original_block_identifiers == introduced_block_identifiers
    ):
        return True

    original_start = _coerce_int(row.get("original_block_start_line"), default=-1)
    original_end = _coerce_int(row.get("original_block_end_line"), default=-1)
    introduced_line = _coerce_int(row.get("line_start"), default=-1)
    return (
        original_start >= 0
        and original_end >= original_start
        and introduced_line >= original_start
        and introduced_line <= original_end
    )


def _classify_scope_granularity(row) -> str:
    original_module = _normalize_path_text(row.get("original_working_directory"))
    introduced_module = _normalize_path_text(row.get("working_directory"))
    original_filename = _normalize_path_text(row.get("original_filename"))
    introduced_filename = _normalize_path_text(row.get("filename"))

    same_module = bool(original_module and introduced_module and original_module == introduced_module)
    if not same_module:
        same_project = _safe_text(row.get("original_project_name"), default="") == _safe_text(row.get("project_name"), default="")
        same_module = bool(same_project and original_filename and introduced_filename and original_filename == introduced_filename)

    same_file = same_module and bool(original_filename and introduced_filename and original_filename == introduced_filename)
    same_block = same_file and _match_same_block(row)

    if same_block:
        return "same_block"
    if same_file:
        return "same_file_other_block"
    if same_module:
        return "same_module_other_file"
    return "outside_original_module"


def load_repair_analysis_data(
    fixes_csv: str,
    outcomes_csv: str,
    diagnostics_csv: str | None = None,
    problems_csv: str | None = None,
):
    fixes_df = _ensure_specific_oid(pd.read_csv(fixes_csv))
    fixes_df = fixes_df.copy()
    fixes_df["iteration_id"] = fixes_df["iteration_id"].astype(str)
    fixes_df["specific_oid"] = fixes_df["specific_oid"].astype(str)
    if "oid" in fixes_df.columns:
        fixes_df["oid"] = fixes_df["oid"].astype(str)
    fixes_df["original_summary"] = (
        fixes_df["summary"] if "summary" in fixes_df.columns else pd.Series("", index=fixes_df.index)
    ).apply(_safe_text)
    fixes_df["original_severity"] = (
        fixes_df["severity"] if "severity" in fixes_df.columns else pd.Series("", index=fixes_df.index)
    ).apply(_safe_text)
    fixes_df["original_filename"] = (
        fixes_df["filename"] if "filename" in fixes_df.columns else pd.Series("", index=fixes_df.index)
    ).apply(_normalize_path_text)
    fixes_df["original_working_directory"] = (
        fixes_df["working_directory"]
        if "working_directory" in fixes_df.columns
        else fixes_df["original_filename"].map(lambda value: os.path.dirname(value) if value else "")
    ).apply(_normalize_path_text)
    fixes_df["original_project_name"] = (
        fixes_df["project_name"] if "project_name" in fixes_df.columns else pd.Series("", index=fixes_df.index)
    ).apply(_safe_text)

    problems_df = None
    if problems_csv and os.path.exists(problems_csv):
        problems_df = _ensure_specific_oid(pd.read_csv(problems_csv))
        problems_df = problems_df.copy()
        problems_df["specific_oid"] = problems_df["specific_oid"].astype(str)
        problem_cols = [
            col
            for col in [
                "specific_oid",
                "block_type",
                "block_identifiers",
                "project_name",
                "impacted_block_start_line",
                "impacted_block_end_line",
            ]
            if col in problems_df.columns
        ]
        if problem_cols:
            fixes_df = fixes_df.merge(
                problems_df[problem_cols].drop_duplicates(subset=["specific_oid"]),
                on="specific_oid",
                how="left",
                suffixes=("", "_problem"),
            )

    outcomes_df = pd.read_csv(outcomes_csv) if outcomes_csv and os.path.exists(outcomes_csv) else pd.DataFrame()
    if not outcomes_df.empty:
        outcomes_df = outcomes_df.copy()
        outcomes_df["iteration_id"] = outcomes_df["iteration_id"].astype(str)
        if "specific_oid" in outcomes_df.columns:
            outcomes_df["specific_oid"] = outcomes_df["specific_oid"].astype(str)
        if "oid" in outcomes_df.columns:
            outcomes_df["oid"] = outcomes_df["oid"].astype(str)
        join_keys = ["specific_oid", "iteration_id"] if "specific_oid" in outcomes_df.columns else ["oid", "iteration_id"]

        keep_cols = [
            col
            for col in [
                "oid",
                "specific_oid",
                "iteration_id",
                "is_fixed",
                "line_is_clean",
                "line_specific_error_fixed",
                "module_fix_introduced_errors",
                "module_original_errors_remaining",
                "block_fix_introduced_errors",
                "block_original_errors_remaining",
            ]
            if col in outcomes_df.columns
        ]
        fixes_df = fixes_df.merge(
            outcomes_df[keep_cols],
            on=join_keys,
            how="left",
            suffixes=("", "_outcome"),
        )

    diagnostics_df = pd.DataFrame()
    if diagnostics_csv and os.path.exists(diagnostics_csv):
        diagnostics_df = pd.read_csv(diagnostics_csv)
        if not diagnostics_df.empty:
            diagnostics_df = diagnostics_df.copy()
            diagnostics_df["iteration_id"] = diagnostics_df["iteration_id"].astype(str)
            if "specific_oid" not in diagnostics_df.columns:
                diagnostics_df = _ensure_specific_oid(diagnostics_df)
            diagnostics_df["specific_oid"] = diagnostics_df["specific_oid"].astype(str)
            if "original_problem_specific_oid" in diagnostics_df.columns:
                diagnostics_df["original_problem_specific_oid"] = diagnostics_df["original_problem_specific_oid"].astype(str)
            if "original_problem_oid" in diagnostics_df.columns:
                diagnostics_df["original_problem_oid"] = diagnostics_df["original_problem_oid"].astype(str)
            diagnostics_df["introduced_in_this_iteration"] = (
                diagnostics_df["introduced_in_this_iteration"]
                if "introduced_in_this_iteration" in diagnostics_df.columns
                else pd.Series(False, index=diagnostics_df.index)
            ).apply(_coerce_bool)
            diagnostics_df["is_new_to_dataset"] = (
                diagnostics_df["is_new_to_dataset"]
                if "is_new_to_dataset" in diagnostics_df.columns
                else pd.Series(False, index=diagnostics_df.index)
            ).apply(_coerce_bool)
            diagnostics_df["summary"] = (
                diagnostics_df["summary"] if "summary" in diagnostics_df.columns else pd.Series("", index=diagnostics_df.index)
            ).apply(_safe_text)
            diagnostics_df["severity"] = (
                diagnostics_df["severity"] if "severity" in diagnostics_df.columns else pd.Series("", index=diagnostics_df.index)
            ).apply(_safe_text)
            diagnostics_df["block_type"] = (
                diagnostics_df["block_type"] if "block_type" in diagnostics_df.columns else pd.Series("", index=diagnostics_df.index)
            ).apply(_safe_text)

    attempts_df = fixes_df.copy()
    attempts_df["iteration_id"] = attempts_df["iteration_id"].astype(str)
    attempts_df["original_problem_key"] = attempts_df["specific_oid"].astype(str)
    attempts_df["original_problem_specific_key"] = attempts_df["specific_oid"].astype(str)
    attempts_df["original_problem_location_key"] = (
        attempts_df["oid"] if "oid" in attempts_df.columns else attempts_df["specific_oid"]
    ).astype(str)
    attempts_df["original_block_type"] = (
        attempts_df["block_type"] if "block_type" in attempts_df.columns else pd.Series("", index=attempts_df.index)
    ).apply(_safe_text)
    attempts_df["original_block_identifiers"] = (
        attempts_df["block_identifiers"] if "block_identifiers" in attempts_df.columns else pd.Series("", index=attempts_df.index)
    ).apply(_safe_text)
    attempts_df["original_block_start_line"] = (
        attempts_df["impacted_block_start_line"] if "impacted_block_start_line" in attempts_df.columns else pd.Series(-1, index=attempts_df.index)
    ).apply(_coerce_int)
    attempts_df["original_block_end_line"] = (
        attempts_df["impacted_block_end_line"] if "impacted_block_end_line" in attempts_df.columns else pd.Series(-1, index=attempts_df.index)
    ).apply(_coerce_int)
    is_fixed_source = attempts_df["is_fixed"] if "is_fixed" in attempts_df.columns else pd.Series(pd.NA, index=attempts_df.index)
    attempts_df["has_outcome_row"] = is_fixed_source.notna()
    attempts_df["is_fixed"] = is_fixed_source.apply(_coerce_bool)
    attempts_df["line_is_clean"] = (
        attempts_df["line_is_clean"] if "line_is_clean" in attempts_df.columns else pd.Series(False, index=attempts_df.index)
    ).apply(_coerce_bool)
    attempts_df["line_specific_error_fixed"] = (
        attempts_df["line_specific_error_fixed"]
        if "line_specific_error_fixed" in attempts_df.columns
        else pd.Series(False, index=attempts_df.index)
    ).apply(_coerce_bool)
    attempts_df["module_fix_introduced_errors"] = (
        attempts_df["module_fix_introduced_errors"]
        if "module_fix_introduced_errors" in attempts_df.columns
        else pd.Series(0, index=attempts_df.index)
    ).apply(_coerce_int)
    attempts_df["module_fix_introduced_errors_outcome_raw"] = attempts_df["module_fix_introduced_errors"]
    attempts_df["module_original_errors_remaining"] = (
        attempts_df["module_original_errors_remaining"]
        if "module_original_errors_remaining" in attempts_df.columns
        else pd.Series(0, index=attempts_df.index)
    ).apply(_coerce_int)
    attempts_df["problem_type_label"] = attempts_df.apply(
        lambda row: _build_problem_type_label(
            row.get("original_summary"),
            row.get("original_block_type"),
            row.get("original_severity"),
        ),
        axis=1,
    )

    if not diagnostics_df.empty:
        def _has_nonempty_column(df: pd.DataFrame, column: str) -> bool:
            if column not in df.columns:
                return False
            series = df[column].fillna("").astype(str).str.strip()
            return (series != "").any()

        origin_specific_col = "original_problem_specific_oid"
        origin_location_col = "original_problem_oid"

        # Prefer diagnostic-granularity origin keys when available; otherwise infer them from attempts.
        origin_col = origin_specific_col if _has_nonempty_column(diagnostics_df, origin_specific_col) else origin_location_col
        origin_join_column = "original_problem_specific_key" if origin_col == origin_specific_col else "original_problem_location_key"

        if origin_col == origin_location_col and origin_location_col in diagnostics_df.columns:
            mapping_df = (
                attempts_df[["iteration_id", "original_problem_location_key", "original_problem_specific_key"]]
                .drop_duplicates()
                .rename(
                    columns={
                        "original_problem_location_key": origin_location_col,
                        "original_problem_specific_key": origin_specific_col,
                    }
                )
            )
            collision_counts = mapping_df.groupby(["iteration_id", origin_location_col])[origin_specific_col].nunique()
            ambiguous = collision_counts[collision_counts > 1]
            if not ambiguous.empty:
                sample = ambiguous.reset_index().head(5).to_dict("records")
                raise ValueError(
                    "Ambiguous origin join detected: multiple specific problems share the same (iteration_id, original_problem_oid).\n"
                    "Introduced-diagnostic attribution is invalid without `original_problem_specific_oid` in the diagnostics CSV.\n"
                    f"Examples: {sample}\n"
                    "Fix: regenerate diagnostics with `original_problem_specific_oid` populated, or ensure (iteration_id, original_problem_oid) is unique."
                )

            # Avoid pandas creating suffixed columns if the diagnostics file already has an empty
            # `original_problem_specific_oid` column (common in older CSV schemas).
            if origin_specific_col in diagnostics_df.columns and not _has_nonempty_column(diagnostics_df, origin_specific_col):
                diagnostics_df = diagnostics_df.drop(columns=[origin_specific_col])

            diagnostics_df = diagnostics_df.merge(mapping_df, on=["iteration_id", origin_location_col], how="left")
            missing = diagnostics_df.loc[
                diagnostics_df["introduced_in_this_iteration"] & diagnostics_df[origin_specific_col].isna(),
                ["iteration_id", origin_location_col],
            ]
            if not missing.empty:
                sample = missing.drop_duplicates().head(5).to_dict("records")
                raise ValueError(
                    "Failed to infer `original_problem_specific_oid` for some introduced diagnostics.\n"
                    f"Examples: {sample}\n"
                    "Fix: ensure diagnostics include `original_problem_specific_oid`, or that all (iteration_id, original_problem_oid) pairs exist in the fixes/outcomes inputs."
                )

            # Switch downstream logic to use the inferred specific key.
            origin_col = origin_specific_col
            origin_join_column = "original_problem_specific_key"
        introduced_counts = (
            diagnostics_df[diagnostics_df["introduced_in_this_iteration"]]
            .groupby([origin_col, "iteration_id"])
            .size()
            .rename("introduced_diagnostics_from_csv")
            .reset_index()
        )
        attempts_df = attempts_df.merge(
            introduced_counts,
            left_on=[origin_join_column, "iteration_id"],
            right_on=[origin_col, "iteration_id"],
            how="left",
        )
        attempts_df["introduced_diagnostics_from_csv"] = attempts_df["introduced_diagnostics_from_csv"].fillna(0).astype(int)
        attempts_df["module_fix_introduced_errors"] = attempts_df["module_fix_introduced_errors"].where(
            attempts_df["module_fix_introduced_errors"] > 0,
            attempts_df["introduced_diagnostics_from_csv"],
        )
        attempts_df.drop(columns=[origin_col], inplace=True, errors="ignore")
    else:
        attempts_df["introduced_diagnostics_from_csv"] = 0

    attempts_df["has_introduced_diagnostics"] = attempts_df["module_fix_introduced_errors"] > 0
    attempts_df["strict_success"] = attempts_df["is_fixed"] & ~attempts_df["has_introduced_diagnostics"]
    attempts_df["introduced_count_gap_raw_minus_classified"] = (
        attempts_df["module_fix_introduced_errors_outcome_raw"] - attempts_df["introduced_diagnostics_from_csv"]
    )
    attempts_df["introduced_count_match"] = (
        attempts_df["has_outcome_row"]
        & (attempts_df["module_fix_introduced_errors_outcome_raw"] == attempts_df["introduced_diagnostics_from_csv"])
    )
    attempts_df["strict_success_from_outcome_raw"] = (
        attempts_df["is_fixed"] & (attempts_df["module_fix_introduced_errors_outcome_raw"] == 0)
    )
    attempts_df["strict_success_from_classified_diagnostics"] = (
        attempts_df["is_fixed"] & (attempts_df["introduced_diagnostics_from_csv"] == 0)
    )
    attempts_df["strict_success_agreement"] = (
        attempts_df["strict_success_from_outcome_raw"] == attempts_df["strict_success_from_classified_diagnostics"]
    )

    iteration_order = sorted(attempts_df["iteration_id"].dropna().astype(str).unique(), key=_iteration_sort_key)
    order_map = {iteration: idx for idx, iteration in enumerate(iteration_order, start=1)}
    attempts_df["iteration_order"] = attempts_df["iteration_id"].map(order_map)

    if not diagnostics_df.empty:
        diagnostics_df["iteration_order"] = diagnostics_df["iteration_id"].map(order_map)
        diagnostics_df["working_directory"] = (
            diagnostics_df["working_directory"]
            if "working_directory" in diagnostics_df.columns
            else pd.Series("", index=diagnostics_df.index)
        ).apply(_normalize_path_text)
        diagnostics_df["filename"] = (
            diagnostics_df["filename"] if "filename" in diagnostics_df.columns else pd.Series("", index=diagnostics_df.index)
        ).apply(_normalize_path_text)
        diagnostics_df["block_identifiers"] = (
            diagnostics_df["block_identifiers"]
            if "block_identifiers" in diagnostics_df.columns
            else pd.Series("", index=diagnostics_df.index)
        ).apply(_safe_text)
        diagnostics_df["project_name"] = (
            diagnostics_df["project_name"] if "project_name" in diagnostics_df.columns else pd.Series("", index=diagnostics_df.index)
        ).apply(_safe_text)

        origin_specific_col = "original_problem_specific_oid"
        origin_location_col = "original_problem_oid"

        if origin_specific_col in diagnostics_df.columns and _has_nonempty_column(diagnostics_df, origin_specific_col):
            diagnostics_df["origin_problem_key"] = diagnostics_df[origin_specific_col].astype(str)
            origin_join_column = "original_problem_specific_key"
        elif origin_location_col in diagnostics_df.columns:
            diagnostics_df["origin_problem_key"] = diagnostics_df[origin_location_col].astype(str)
            origin_join_column = "original_problem_location_key"
        else:
            diagnostics_df["origin_problem_key"] = ""
            origin_join_column = "original_problem_specific_key"
        diagnostics_df = diagnostics_df.merge(
            attempts_df[
                [
                    origin_join_column,
                    "iteration_id",
                    "original_project_name",
                    "original_working_directory",
                    "original_filename",
                    "original_block_type",
                    "original_block_identifiers",
                    "original_block_start_line",
                    "original_block_end_line",
                    "problem_type_label",
                ]
            ].drop_duplicates(),
            left_on=["origin_problem_key", "iteration_id"],
            right_on=[origin_join_column, "iteration_id"],
            how="left",
        )
        diagnostics_df["scope_granularity"] = diagnostics_df.apply(_classify_scope_granularity, axis=1)
        for scope_name in SCOPE_LEVELS:
            diagnostics_df[f"scope_{scope_name}"] = diagnostics_df["scope_granularity"] == scope_name

    return attempts_df, diagnostics_df, problems_df
