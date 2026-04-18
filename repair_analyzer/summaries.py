import pandas as pd

from repair_analyzer.constants import SCOPE_LEVELS
from repair_analyzer.utils import _build_problem_type_label, _safe_text


def build_iteration_summary(attempts_df: pd.DataFrame) -> pd.DataFrame:
    summary_df = (
        attempts_df.groupby(["iteration_id", "iteration_order"], as_index=False)
        .agg(
            repairs_attempted=("original_problem_key", "size"),
            unique_problems=("original_problem_key", "nunique"),
            fixed_repairs=("is_fixed", "sum"),
            strict_fixed_repairs=("strict_success", "sum"),
            repairs_with_introduced_diagnostics=("has_introduced_diagnostics", "sum"),
            introduced_diagnostics=("module_fix_introduced_errors", "sum"),
            avg_original_errors_remaining=("module_original_errors_remaining", "mean"),
        )
        .sort_values("iteration_order")
    )
    summary_df["fix_rate"] = summary_df["fixed_repairs"] / summary_df["repairs_attempted"]
    summary_df["strict_fix_rate"] = summary_df["strict_fixed_repairs"] / summary_df["repairs_attempted"]
    summary_df["introduction_rate"] = summary_df["repairs_with_introduced_diagnostics"] / summary_df["repairs_attempted"]
    summary_df["avg_introduced_diagnostics"] = summary_df["introduced_diagnostics"] / summary_df["repairs_attempted"]

    first_fix_df = (
        attempts_df[attempts_df["is_fixed"]]
        .groupby("original_problem_key", as_index=False)["iteration_order"]
        .min()
        .rename(columns={"iteration_order": "first_fixed_iteration_order"})
    )
    first_fix_counts = (
        first_fix_df.groupby("first_fixed_iteration_order")
        .size()
        .rename("new_problems_fixed")
        .reset_index()
    )
    summary_df = summary_df.merge(
        first_fix_counts,
        left_on="iteration_order",
        right_on="first_fixed_iteration_order",
        how="left",
    )
    summary_df["new_problems_fixed"] = summary_df["new_problems_fixed"].fillna(0).astype(int)
    total_problems = max(int(attempts_df["original_problem_key"].nunique()), 1)
    summary_df["cumulative_problems_fixed"] = summary_df["new_problems_fixed"].cumsum()
    summary_df["cumulative_fix_coverage"] = summary_df["cumulative_problems_fixed"] / total_problems
    summary_df.drop(columns=["first_fixed_iteration_order"], inplace=True, errors="ignore")
    return summary_df


def build_problem_lifecycle(attempts_df: pd.DataFrame) -> pd.DataFrame:
    lifecycle_df = (
        attempts_df.groupby(
            [
                "original_problem_key",
                "original_filename",
                "original_summary",
                "original_severity",
                "original_block_type",
                "problem_type_label",
            ],
            as_index=False,
        )
        .agg(
            attempts=("iteration_id", "size"),
            fixes=("is_fixed", "sum"),
            strict_fixes=("strict_success", "sum"),
            introduced_diagnostics=("module_fix_introduced_errors", "sum"),
            ever_fixed=("is_fixed", "max"),
            ever_strict_fixed=("strict_success", "max"),
        )
    )

    fixed_first = (
        attempts_df[attempts_df["is_fixed"]]
        .groupby("original_problem_key", as_index=False)
        .agg(first_fixed_iteration_order=("iteration_order", "min"))
    )
    strict_first = (
        attempts_df[attempts_df["strict_success"]]
        .groupby("original_problem_key", as_index=False)
        .agg(first_strict_fixed_iteration_order=("iteration_order", "min"))
    )
    order_map = (
        attempts_df[["iteration_id", "iteration_order"]]
        .drop_duplicates()
        .set_index("iteration_order")["iteration_id"]
        .to_dict()
    )
    lifecycle_df = lifecycle_df.merge(fixed_first, on="original_problem_key", how="left")
    lifecycle_df = lifecycle_df.merge(strict_first, on="original_problem_key", how="left")
    lifecycle_df["first_fixed_iteration"] = lifecycle_df["first_fixed_iteration_order"].map(order_map)
    lifecycle_df["first_strict_fixed_iteration"] = lifecycle_df["first_strict_fixed_iteration_order"].map(order_map)
    return lifecycle_df.sort_values(
        ["ever_strict_fixed", "ever_fixed", "introduced_diagnostics", "problem_type_label"],
        ascending=[True, True, False, True],
    )


def build_fixed_types_by_iteration(attempts_df: pd.DataFrame) -> pd.DataFrame:
    fixed_types_df = (
        attempts_df.groupby(
            [
                "iteration_id",
                "iteration_order",
                "original_summary",
                "original_severity",
                "original_block_type",
                "problem_type_label",
            ],
            as_index=False,
        )
        .agg(
            repairs_attempted=("original_problem_key", "size"),
            unique_problems=("original_problem_key", "nunique"),
            fixed_repairs=("is_fixed", "sum"),
            strict_fixed_repairs=("strict_success", "sum"),
            repairs_with_introduced_diagnostics=("has_introduced_diagnostics", "sum"),
        )
    )
    fixed_types_df["fix_rate"] = fixed_types_df["fixed_repairs"] / fixed_types_df["repairs_attempted"]
    fixed_types_df["strict_fix_rate"] = fixed_types_df["strict_fixed_repairs"] / fixed_types_df["repairs_attempted"]
    return fixed_types_df.sort_values(
        ["iteration_order", "fixed_repairs", "strict_fix_rate", "problem_type_label"],
        ascending=[True, False, False, True],
    )


def build_fixed_types_overall(attempts_df: pd.DataFrame) -> pd.DataFrame:
    overall_df = (
        attempts_df.groupby(
            [
                "original_summary",
                "original_severity",
                "original_block_type",
                "problem_type_label",
            ],
            as_index=False,
        )
        .agg(
            repairs_attempted=("original_problem_key", "size"),
            unique_problems=("original_problem_key", "nunique"),
            fixed_repairs=("is_fixed", "sum"),
            strict_fixed_repairs=("strict_success", "sum"),
            repairs_with_introduced_diagnostics=("has_introduced_diagnostics", "sum"),
        )
    )
    overall_df["fix_rate"] = overall_df["fixed_repairs"] / overall_df["repairs_attempted"]
    overall_df["strict_fix_rate"] = overall_df["strict_fixed_repairs"] / overall_df["repairs_attempted"]
    return overall_df.sort_values(
        ["strict_fixed_repairs", "strict_fix_rate", "fixed_repairs", "problem_type_label"],
        ascending=[False, False, False, True],
    )


def _add_scope_count_columns(grouped_df: pd.DataFrame, source_df: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if source_df.empty:
        for scope_name in SCOPE_LEVELS:
            grouped_df[f"{scope_name}_diagnostics"] = 0
        return grouped_df

    for scope_name in SCOPE_LEVELS:
        scope_counts = (
            source_df[source_df["scope_granularity"] == scope_name]
            .groupby(group_columns)
            .size()
            .rename(f"{scope_name}_diagnostics")
            .reset_index()
        )
        grouped_df = grouped_df.merge(scope_counts, on=group_columns, how="left")
        grouped_df[f"{scope_name}_diagnostics"] = grouped_df[f"{scope_name}_diagnostics"].fillna(0).astype(int)
    return grouped_df


def build_introduced_scope_summary(diagnostics_df: pd.DataFrame) -> pd.DataFrame:
    columns = ["scope_granularity", "introduced_diagnostics", "affected_repairs"]
    if diagnostics_df.empty:
        return pd.DataFrame(columns=columns)

    introduced_df = diagnostics_df[diagnostics_df["introduced_in_this_iteration"]].copy()
    if introduced_df.empty:
        return pd.DataFrame(columns=columns)

    introduced_df["repair_key"] = introduced_df["origin_problem_key"].astype(str) + "::" + introduced_df["iteration_id"].astype(str)
    summary_df = (
        introduced_df.groupby("scope_granularity", as_index=False)
        .agg(
            introduced_diagnostics=("specific_oid", "size"),
            affected_repairs=("repair_key", "nunique"),
        )
    )
    summary_df["scope_granularity"] = pd.Categorical(summary_df["scope_granularity"], categories=SCOPE_LEVELS, ordered=True)
    return summary_df.sort_values("scope_granularity").reset_index(drop=True)


def build_introduced_scope_by_iteration(diagnostics_df: pd.DataFrame) -> pd.DataFrame:
    columns = ["iteration_id", "iteration_order", "scope_granularity", "introduced_diagnostics", "affected_repairs"]
    if diagnostics_df.empty:
        return pd.DataFrame(columns=columns)

    introduced_df = diagnostics_df[diagnostics_df["introduced_in_this_iteration"]].copy()
    if introduced_df.empty:
        return pd.DataFrame(columns=columns)

    introduced_df["repair_key"] = introduced_df["origin_problem_key"].astype(str) + "::" + introduced_df["iteration_id"].astype(str)
    grouped_df = (
        introduced_df.groupby(["iteration_id", "iteration_order", "scope_granularity"], as_index=False)
        .agg(
            introduced_diagnostics=("specific_oid", "size"),
            affected_repairs=("repair_key", "nunique"),
        )
    )
    grouped_df["scope_granularity"] = pd.Categorical(grouped_df["scope_granularity"], categories=SCOPE_LEVELS, ordered=True)
    return grouped_df.sort_values(["iteration_order", "scope_granularity"]).reset_index(drop=True)


def build_introduced_diagnostics_detail(diagnostics_df: pd.DataFrame) -> pd.DataFrame:
    if diagnostics_df.empty:
        return pd.DataFrame()

    introduced_df = diagnostics_df[diagnostics_df["introduced_in_this_iteration"]].copy()
    if introduced_df.empty:
        return pd.DataFrame()

    detail_columns = [
        "iteration_id",
        "scope_granularity",
        "project_name",
        "working_directory",
        "origin_problem_key",
        "problem_type_label",
        "original_filename",
        "original_block_type",
        "original_block_identifiers",
        "filename",
        "block_type",
        "block_identifiers",
        "line_start",
        "line_end",
        "severity",
        "summary",
        "detail",
        "is_new_to_dataset",
        "first_seen_in",
        "exists_in_iterations",
    ]
    available_columns = [column for column in detail_columns if column in introduced_df.columns]
    return introduced_df[available_columns].sort_values(
        ["scope_granularity", "iteration_id", "project_name", "filename", "line_start", "summary"],
        ascending=[True, True, True, True, True, True],
    )


def build_introduced_types_by_iteration(attempts_df: pd.DataFrame, diagnostics_df: pd.DataFrame) -> pd.DataFrame:
    empty_columns = [
        "iteration_id",
        "iteration_order",
        "introduced_summary",
        "introduced_severity",
        "introduced_block_type",
        "introduced_type_label",
        "introduced_diagnostics",
        "affected_repairs",
        "truly_new_diagnostics",
        "cross_iteration_repeats",
        "same_block_diagnostics",
        "same_file_other_block_diagnostics",
        "same_module_other_file_diagnostics",
        "outside_original_module_diagnostics",
    ]
    if diagnostics_df.empty:
        return pd.DataFrame(columns=empty_columns)

    introduced_df = diagnostics_df[diagnostics_df["introduced_in_this_iteration"]].copy()
    if introduced_df.empty:
        return pd.DataFrame(columns=empty_columns)

    introduced_df["origin_problem_key"] = introduced_df["origin_problem_key"].astype(str)
    introduced_df["introduced_summary"] = introduced_df["summary"].apply(_safe_text)
    introduced_df["introduced_severity"] = introduced_df["severity"].apply(_safe_text)
    introduced_df["introduced_block_type"] = introduced_df["block_type"].apply(_safe_text)
    introduced_df["introduced_type_label"] = introduced_df.apply(
        lambda row: _build_problem_type_label(
            row.get("introduced_summary"),
            row.get("introduced_block_type"),
            row.get("introduced_severity"),
        ),
        axis=1,
    )
    introduced_df["cross_iteration_repeat"] = introduced_df.get("exists_in_iterations", "").fillna("").astype(str).str.strip() != ""

    group_columns = [
        "iteration_id",
        "iteration_order",
        "introduced_summary",
        "introduced_severity",
        "introduced_block_type",
        "introduced_type_label",
    ]
    grouped_df = (
        introduced_df.groupby(group_columns, as_index=False)
        .agg(
            introduced_diagnostics=("specific_oid", "size"),
            affected_repairs=("origin_problem_key", "nunique"),
            truly_new_diagnostics=("is_new_to_dataset", "sum"),
            cross_iteration_repeats=("cross_iteration_repeat", "sum"),
        )
    )
    grouped_df = _add_scope_count_columns(grouped_df, introduced_df, group_columns)
    return grouped_df.sort_values(
        ["iteration_order", "introduced_diagnostics", "affected_repairs", "introduced_type_label"],
        ascending=[True, False, False, True],
    )


def build_introduced_types_overall(attempts_df: pd.DataFrame, diagnostics_df: pd.DataFrame) -> pd.DataFrame:
    introduced_by_iteration_df = build_introduced_types_by_iteration(attempts_df, diagnostics_df)
    if introduced_by_iteration_df.empty:
        return introduced_by_iteration_df
    overall_df = (
        introduced_by_iteration_df.groupby(
            [
                "introduced_summary",
                "introduced_severity",
                "introduced_block_type",
                "introduced_type_label",
            ],
            as_index=False,
        )
        .agg(
            introduced_diagnostics=("introduced_diagnostics", "sum"),
            affected_repairs=("affected_repairs", "sum"),
            truly_new_diagnostics=("truly_new_diagnostics", "sum"),
            cross_iteration_repeats=("cross_iteration_repeats", "sum"),
            same_block_diagnostics=("same_block_diagnostics", "sum"),
            same_file_other_block_diagnostics=("same_file_other_block_diagnostics", "sum"),
            same_module_other_file_diagnostics=("same_module_other_file_diagnostics", "sum"),
            outside_original_module_diagnostics=("outside_original_module_diagnostics", "sum"),
        )
    )
    return overall_df.sort_values(
        ["introduced_diagnostics", "affected_repairs", "introduced_type_label"],
        ascending=[False, False, True],
    )


def build_transition_summary(attempts_df: pd.DataFrame, diagnostics_df: pd.DataFrame) -> pd.DataFrame:
    empty_columns = [
        "iteration_id",
        "iteration_order",
        "problem_type_label",
        "introduced_type_label",
        "scope_granularity",
        "transition_count",
        "affected_repairs",
    ]
    if diagnostics_df.empty:
        return pd.DataFrame(columns=empty_columns)

    introduced_df = diagnostics_df[diagnostics_df["introduced_in_this_iteration"]].copy()
    if introduced_df.empty:
        return pd.DataFrame(columns=empty_columns)

    introduced_df["introduced_type_label"] = introduced_df.apply(
        lambda row: _build_problem_type_label(
            row.get("summary"),
            row.get("block_type"),
            row.get("severity"),
        ),
        axis=1,
    )
    transition_df = introduced_df.copy()
    transition_df["problem_type_label"] = transition_df["problem_type_label"].fillna("Unknown source problem")
    transition_df["scope_granularity"] = transition_df["scope_granularity"].fillna("outside_original_module")
    transition_df["repair_key"] = transition_df["origin_problem_key"].astype(str) + "::" + transition_df["iteration_id"].astype(str)

    grouped_df = (
        transition_df.groupby(
            ["iteration_id", "iteration_order", "problem_type_label", "introduced_type_label", "scope_granularity"],
            as_index=False,
        )
        .agg(
            transition_count=("specific_oid", "size"),
            affected_repairs=("repair_key", "nunique"),
        )
    )
    return grouped_df.sort_values(
        ["iteration_order", "transition_count", "affected_repairs"],
        ascending=[True, False, False],
    )


def build_introduced_error_audit(attempts_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "repairs_attempted",
        "repairs_with_outcomes",
        "repairs_missing_outcomes",
        "repairs_with_matching_introduced_counts",
        "repairs_with_mismatching_introduced_counts",
        "introduced_count_match_rate",
        "total_outcome_introduced_diagnostics_raw",
        "total_classified_introduced_diagnostics",
        "introduced_total_gap_raw_minus_classified",
        "introduced_total_abs_gap",
        "repairs_raw_positive_classified_zero",
        "repairs_raw_zero_classified_positive",
        "strict_success_agreement_repairs",
        "strict_success_disagreement_repairs",
        "strict_success_agreement_rate",
    ]
    if attempts_df.empty:
        return pd.DataFrame(columns=columns)

    audit_df = attempts_df.copy()
    audit_df["has_outcome_row"] = (
        audit_df["has_outcome_row"] if "has_outcome_row" in audit_df.columns else pd.Series(False, index=audit_df.index)
    ).fillna(False).astype(bool)
    audit_df["module_fix_introduced_errors_outcome_raw"] = (
        audit_df["module_fix_introduced_errors_outcome_raw"]
        if "module_fix_introduced_errors_outcome_raw" in audit_df.columns
        else pd.Series(0, index=audit_df.index)
    ).fillna(0).astype(int)
    audit_df["introduced_diagnostics_from_csv"] = (
        audit_df["introduced_diagnostics_from_csv"]
        if "introduced_diagnostics_from_csv" in audit_df.columns
        else pd.Series(0, index=audit_df.index)
    ).fillna(0).astype(int)

    compared_df = audit_df[audit_df["has_outcome_row"]].copy()
    repairs_attempted = int(len(audit_df))
    repairs_with_outcomes = int(len(compared_df))
    repairs_missing_outcomes = repairs_attempted - repairs_with_outcomes

    if compared_df.empty:
        row = {column: 0 for column in columns}
        row["repairs_attempted"] = repairs_attempted
        row["repairs_missing_outcomes"] = repairs_missing_outcomes
        return pd.DataFrame([row], columns=columns)

    compared_df["introduced_count_match"] = (
        compared_df["module_fix_introduced_errors_outcome_raw"]
        == compared_df["introduced_diagnostics_from_csv"]
    )
    compared_df["strict_success_from_outcome_raw"] = compared_df["is_fixed"] & (
        compared_df["module_fix_introduced_errors_outcome_raw"] == 0
    )
    compared_df["strict_success_from_classified_diagnostics"] = compared_df["is_fixed"] & (
        compared_df["introduced_diagnostics_from_csv"] == 0
    )
    compared_df["strict_success_agreement"] = (
        compared_df["strict_success_from_outcome_raw"]
        == compared_df["strict_success_from_classified_diagnostics"]
    )

    repairs_with_matching_introduced_counts = int(compared_df["introduced_count_match"].sum())
    repairs_with_mismatching_introduced_counts = repairs_with_outcomes - repairs_with_matching_introduced_counts
    strict_success_agreement_repairs = int(compared_df["strict_success_agreement"].sum())
    strict_success_disagreement_repairs = repairs_with_outcomes - strict_success_agreement_repairs

    row = {
        "repairs_attempted": repairs_attempted,
        "repairs_with_outcomes": repairs_with_outcomes,
        "repairs_missing_outcomes": repairs_missing_outcomes,
        "repairs_with_matching_introduced_counts": repairs_with_matching_introduced_counts,
        "repairs_with_mismatching_introduced_counts": repairs_with_mismatching_introduced_counts,
        "introduced_count_match_rate": repairs_with_matching_introduced_counts / max(repairs_with_outcomes, 1),
        "total_outcome_introduced_diagnostics_raw": int(compared_df["module_fix_introduced_errors_outcome_raw"].sum()),
        "total_classified_introduced_diagnostics": int(compared_df["introduced_diagnostics_from_csv"].sum()),
        "introduced_total_gap_raw_minus_classified": int(
            compared_df["module_fix_introduced_errors_outcome_raw"].sum()
            - compared_df["introduced_diagnostics_from_csv"].sum()
        ),
        "introduced_total_abs_gap": int(
            (
                compared_df["module_fix_introduced_errors_outcome_raw"]
                - compared_df["introduced_diagnostics_from_csv"]
            )
            .abs()
            .sum()
        ),
        "repairs_raw_positive_classified_zero": int(
            (
                (compared_df["module_fix_introduced_errors_outcome_raw"] > 0)
                & (compared_df["introduced_diagnostics_from_csv"] == 0)
            ).sum()
        ),
        "repairs_raw_zero_classified_positive": int(
            (
                (compared_df["module_fix_introduced_errors_outcome_raw"] == 0)
                & (compared_df["introduced_diagnostics_from_csv"] > 0)
            ).sum()
        ),
        "strict_success_agreement_repairs": strict_success_agreement_repairs,
        "strict_success_disagreement_repairs": strict_success_disagreement_repairs,
        "strict_success_agreement_rate": strict_success_agreement_repairs / max(repairs_with_outcomes, 1),
    }
    return pd.DataFrame([row], columns=columns)


def build_introduced_error_mismatch_detail(attempts_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "iteration_id",
        "iteration_order",
        "original_problem_key",
        "problem_type_label",
        "original_filename",
        "is_fixed",
        "module_fix_introduced_errors_outcome_raw",
        "introduced_diagnostics_from_csv",
        "introduced_count_gap_raw_minus_classified",
        "strict_success_from_outcome_raw",
        "strict_success_from_classified_diagnostics",
        "has_outcome_row",
    ]
    if attempts_df.empty:
        return pd.DataFrame(columns=columns)

    detail_df = attempts_df.copy()
    detail_df["has_outcome_row"] = (
        detail_df["has_outcome_row"] if "has_outcome_row" in detail_df.columns else pd.Series(False, index=detail_df.index)
    ).fillna(False).astype(bool)
    detail_df = detail_df[detail_df["has_outcome_row"]].copy()
    if detail_df.empty:
        return pd.DataFrame(columns=columns)

    detail_df["module_fix_introduced_errors_outcome_raw"] = (
        detail_df["module_fix_introduced_errors_outcome_raw"]
        if "module_fix_introduced_errors_outcome_raw" in detail_df.columns
        else pd.Series(0, index=detail_df.index)
    ).fillna(0).astype(int)
    detail_df["introduced_diagnostics_from_csv"] = (
        detail_df["introduced_diagnostics_from_csv"]
        if "introduced_diagnostics_from_csv" in detail_df.columns
        else pd.Series(0, index=detail_df.index)
    ).fillna(0).astype(int)
    detail_df["introduced_count_gap_raw_minus_classified"] = (
        detail_df["module_fix_introduced_errors_outcome_raw"] - detail_df["introduced_diagnostics_from_csv"]
    )
    detail_df["strict_success_from_outcome_raw"] = detail_df["is_fixed"] & (
        detail_df["module_fix_introduced_errors_outcome_raw"] == 0
    )
    detail_df["strict_success_from_classified_diagnostics"] = detail_df["is_fixed"] & (
        detail_df["introduced_diagnostics_from_csv"] == 0
    )
    detail_df = detail_df[
        (detail_df["introduced_count_gap_raw_minus_classified"] != 0)
        | (
            detail_df["strict_success_from_outcome_raw"]
            != detail_df["strict_success_from_classified_diagnostics"]
        )
    ]
    if detail_df.empty:
        return pd.DataFrame(columns=columns)

    available_columns = [column for column in columns if column in detail_df.columns]
    return detail_df[available_columns].sort_values(
        ["iteration_order", "introduced_count_gap_raw_minus_classified", "problem_type_label"],
        ascending=[True, False, True],
    )


def _summary_resolution_overall_df(fixed_types_overall_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "original_summary",
        "repairs_attempted",
        "unique_problems",
        "fixed_repairs",
        "strict_fixed_repairs",
        "fix_rate",
        "strict_fix_rate",
    ]
    if fixed_types_overall_df.empty:
        return pd.DataFrame(columns=columns)

    summary_df = (
        fixed_types_overall_df.groupby("original_summary", as_index=False)
        .agg(
            repairs_attempted=("repairs_attempted", "sum"),
            unique_problems=("unique_problems", "sum"),
            fixed_repairs=("fixed_repairs", "sum"),
            strict_fixed_repairs=("strict_fixed_repairs", "sum"),
        )
    )
    summary_df["fix_rate"] = summary_df["fixed_repairs"] / summary_df["repairs_attempted"]
    summary_df["strict_fix_rate"] = summary_df["strict_fixed_repairs"] / summary_df["repairs_attempted"]
    return summary_df.sort_values(
        ["repairs_attempted", "unique_problems", "strict_fix_rate", "original_summary"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)


def _summary_resolution_rows(fixed_types_overall_df: pd.DataFrame, limit: int = 8) -> list[dict]:
    summary_df = _summary_resolution_overall_df(fixed_types_overall_df)
    if summary_df.empty:
        return []
    return (
        summary_df.head(limit)[["original_summary", "strict_fix_rate", "repairs_attempted", "strict_fixed_repairs"]]
        .rename(columns={"original_summary": "label", "strict_fix_rate": "value"})
        .to_dict("records")
    )


def _fixed_message_distribution_rows(fixed_types_overall_df: pd.DataFrame, limit: int = 10) -> list[dict]:
    if fixed_types_overall_df.empty:
        return []
    grouped_df = (
        fixed_types_overall_df.groupby("original_summary", as_index=False)
        .agg(
            repairs_attempted=("repairs_attempted", "sum"),
            strict_fixed_repairs=("strict_fixed_repairs", "sum"),
        )
    )
    grouped_df["strict_fix_rate"] = grouped_df["strict_fixed_repairs"] / grouped_df["repairs_attempted"]
    grouped_df = grouped_df.sort_values(["strict_fix_rate", "strict_fixed_repairs"], ascending=[False, False]).head(limit)
    return grouped_df.rename(columns={"original_summary": "label", "strict_fix_rate": "value"})[["label", "value"]].to_dict("records")


def _introduced_message_distribution_rows(introduced_types_overall_df: pd.DataFrame, limit: int = 10) -> list[dict]:
    if introduced_types_overall_df.empty:
        return []
    grouped_df = (
        introduced_types_overall_df.groupby("introduced_summary", as_index=False)
        .agg(
            introduced_diagnostics=("introduced_diagnostics", "sum"),
        )
    )
    total_introduced = max(float(grouped_df["introduced_diagnostics"].sum()), 1.0)
    grouped_df["introduced_share"] = grouped_df["introduced_diagnostics"] / total_introduced
    grouped_df = grouped_df.sort_values(["introduced_share", "introduced_diagnostics"], ascending=[False, False]).head(limit)
    return grouped_df.rename(columns={"introduced_summary": "label", "introduced_share": "value"})[["label", "value"]].to_dict("records")
