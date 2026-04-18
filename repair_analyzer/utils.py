from pathlib import Path

import pandas as pd

from terraform_validation.extractor import DiagnosticsExtractor


def _coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "t", "yes", "y"}


def _coerce_int(value, default=0) -> int:
    if pd.isna(value):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_text(value, default="Unknown"):
    if pd.isna(value):
        return default
    text = str(value).strip()
    return text or default


def _iteration_sort_key(value):
    text = _safe_text(value, default="")
    try:
        return (0, int(float(text)))
    except (TypeError, ValueError):
        return (1, text)


def _ensure_specific_oid(df: pd.DataFrame) -> pd.DataFrame:
    if "specific_oid" in df.columns:
        filled = df["specific_oid"].fillna("").astype(str).str.strip()
        if (filled != "").all():
            df = df.copy()
            df["specific_oid"] = filled
            return df

    df = df.copy()
    df["specific_oid"] = df.apply(
        lambda row: DiagnosticsExtractor.compute_specific_oid(row.to_dict()),
        axis=1,
    )
    return df


def _format_pct(value) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value) * 100:.1f}%"


def _build_problem_type_label(summary, block_type, severity) -> str:
    summary_text = _safe_text(summary, default="Unknown diagnostic")
    extras = []
    block_text = _safe_text(block_type, default="")
    severity_text = _safe_text(severity, default="")
    if block_text:
        extras.append(block_text)
    if severity_text:
        extras.append(severity_text)
    if extras:
        return f"{summary_text} [{', '.join(extras)}]"
    return summary_text


def _normalize_path_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().replace("\\", "/")


def _pick_writable_path(path: str) -> str:
    target = Path(path)
    if not target.exists():
        return str(target)
    try:
        with open(target, "wb"):
            pass
        return str(target)
    except PermissionError:
        for idx in range(2, 20):
            candidate = target.with_name(f"{target.stem}_v{idx}{target.suffix}")
            if not candidate.exists():
                return str(candidate)
            try:
                with open(candidate, "wb"):
                    pass
                return str(candidate)
            except PermissionError:
                continue
    return str(target)
