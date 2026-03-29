"""
Fix OID mismatches in diagnostics CSVs.

Why this exists:
- The benchmark problems dataset (`problems/problems.csv`) uses an OID scheme based on:
  normalized filename + block_identifiers + normalized(summary) + normalized(detail)
- Some previously generated diagnostics CSVs used a location-based OID (filename + line range),
  causing pass@k/evaluation joins against `problems.csv` to fail.

This script rewrites the `oid` column to match the benchmark scheme.
"""

import argparse
import hashlib
import os
import sys
from pathlib import Path

import pandas as pd

# Ensure project root is importable when invoked as `python scripts/...`.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from repair_pipeline.file_resolver import FileCoordinateResolver
from terraform_validation.extractor import DiagnosticsExtractor


def _sha1_12(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def compute_benchmark_oid(df: pd.DataFrame) -> pd.Series:
    filename = df.get("filename", "").fillna("").astype(str).map(FileCoordinateResolver.normalize_path)
    block_identifiers = df.get("block_identifiers", "").fillna("").astype(str).str.strip()
    summary = df.get("summary", "").fillna("").astype(str).map(DiagnosticsExtractor.normalize_for_oid)
    detail = df.get("detail", "").fillna("").astype(str).map(DiagnosticsExtractor.normalize_for_oid)

    base = filename + "|" + block_identifiers + "|" + summary + "|" + detail
    return base.map(_sha1_12)


def main() -> int:
    ap = argparse.ArgumentParser(description="Rewrite diagnostics CSV OIDs to match problems/problems.csv scheme")
    ap.add_argument("--in", dest="in_csv", required=True, help="Input diagnostics CSV")
    ap.add_argument("--out", dest="out_csv", help="Output CSV (default: <in>_oidfixed.csv)")
    ap.add_argument(
        "--problems-csv",
        help=(
            "Optional problems CSV. If provided, original-error rows will have their oid remapped via "
            "specific_oid -> oid when possible (helps when block_identifiers differ)."
        ),
    )
    ap.add_argument(
        "--keep-old",
        action="store_true",
        help="Keep the old oid values in a new column named oid_old",
    )
    args = ap.parse_args()

    in_path = Path(args.in_csv)
    if not in_path.exists():
        raise SystemExit(f"Input not found: {in_path}")

    out_path = Path(args.out_csv) if args.out_csv else in_path.with_name(in_path.stem + "_oidfixed.csv")

    df = pd.read_csv(in_path, dtype=str)
    if "oid" not in df.columns:
        raise SystemExit("Input CSV has no 'oid' column.")

    if args.keep_old:
        df.insert(df.columns.get_loc("oid") + 1, "oid_old", df["oid"])

    df["oid"] = compute_benchmark_oid(df)

    # Optional: ensure original-error rows match the problems dataset exactly when specific_oid matches.
    if args.problems_csv and "specific_oid" in df.columns and "is_original_error" in df.columns:
        probs = pd.read_csv(args.problems_csv, dtype=str)
        if "specific_oid" in probs.columns and "oid" in probs.columns:
            spec_to_oid = dict(
                zip(
                    probs["specific_oid"].fillna("").astype(str),
                    probs["oid"].fillna("").astype(str),
                )
            )

            mask = df["is_original_error"].fillna("").astype(str).str.lower().isin(["true", "1", "yes"])
            specs = df.loc[mask, "specific_oid"].fillna("").astype(str)
            mapped = specs.map(lambda s: spec_to_oid.get(s))
            df.loc[mask, "oid"] = mapped.where(mapped.notna() & (mapped != ""), other=df.loc[mask, "oid"])
    df.to_csv(out_path, index=False, encoding="utf-8")

    print(f"Wrote {len(df)} rows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
