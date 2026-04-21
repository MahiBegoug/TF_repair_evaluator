"""
Plot docs-vs-snippet pass@k deltas for each model family.

Reads evaluation/results/docs_vs_snippet_perturbation_by_k.csv and generates
an evolution chart where each line is:

    delta(k) = pass@k_docs - pass@k_snippet

Positive values mean documentation helped. Negative values mean snippet-only
performed better.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT / "evaluation" / "results" / "docs_vs_snippet_perturbation_by_k.csv"
OUT_SVG = ROOT / "evaluation" / "results" / "docs_vs_snippet_passk_delta.svg"
OUT_PNG = ROOT / "evaluation" / "results" / "docs_vs_snippet_passk_delta.png"

MODEL_STYLE = {
    "CodeLlama_34b_Instruct_hf": {"label": "CodeLlama", "color": "#b33c2f"},
    "Codestral_22B_v0.1": {"label": "Codestral", "color": "#1d6996"},
    "deepseek_coder_33b_instruct": {"label": "DeepSeek-Coder", "color": "#2d936c"},
    "gpt_oss_20b": {"label": "gpt-oss", "color": "#8a5cf6"},
}


def main() -> None:
    df = pd.read_csv(INPUT_CSV)
    df["delta_pp"] = df["delta_docs_minus_snippet"] * 100.0

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(10.5, 6.5), constrained_layout=True)

    for model, group in df.groupby("model", sort=False):
        style = MODEL_STYLE.get(model, {"label": model, "color": None})
        ordered = group.sort_values("k")
        ax.plot(
            ordered["k"],
            ordered["delta_pp"],
            marker="o",
            linewidth=2.4,
            markersize=6,
            label=style["label"],
            color=style["color"],
        )

    ax.axhline(0.0, color="#444444", linewidth=1.1, linestyle="--")
    ax.set_title("Documentation Impact on pass@k by Model", fontsize=16, pad=14)
    ax.set_xlabel("k", fontsize=12)
    ax.set_ylabel("Docs - Snippet (percentage points)", fontsize=12)
    ax.set_xticks(sorted(df["k"].unique()))
    ax.legend(title="Model", frameon=True)

    ax.text(
        0.99,
        0.02,
        "positive: docs better | negative: snippet better",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=10,
        color="#555555",
    )

    fig.savefig(OUT_SVG, format="svg")
    fig.savefig(OUT_PNG, format="png", dpi=180)
    plt.close(fig)

    print(f"[OK] Wrote {OUT_SVG}")
    print(f"[OK] Wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
