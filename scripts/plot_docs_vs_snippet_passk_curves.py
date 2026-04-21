"""
Plot pass@k evolution curves for docs vs snippet prompting.

Supports standard pass@k and strict variants from the aggregated result CSVs.

Examples:
    python scripts/plot_docs_vs_snippet_passk_curves.py
    python scripts/plot_docs_vs_snippet_passk_curves.py --metric block_strict
"""

import argparse
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "evaluation" / "results"

MODEL_FILES = {
    "CodeLlama_34b_Instruct_hf": {
        "label": "CodeLlama",
        "color": "#2b6cb0",
        "marker": "o",
        "docs": "CodeLlama_34b_Instruct_hf_docs_snippet_marked_code_only_xml_pass_at_k_1_to_11.csv",
        "snippet": "CodeLlama_34b_Instruct_hf_snippet_marked_code_only_xml_pass_at_k_1_to_11.csv",
    },
    "Codestral_22B_v0.1": {
        "label": "Codestral",
        "color": "#dd6b20",
        "marker": "s",
        "docs": "Codestral_22B_v0.1_docs_snippet_marked_code_only_xml_pass_at_k_1_to_11.csv",
        "snippet": "Codestral_22B_v0.1_snippet_marked_code_only_xml_pass_at_k_1_to_11.csv",
    },
    "deepseek_coder_33b_instruct": {
        "label": "DeepSeek-Coder",
        "color": "#2f855a",
        "marker": "^",
        "docs": "deepseek_coder_33b_instruct_docs_snippet_marked_code_only_xml_pass_at_k_1_to_11.csv",
        "snippet": "deepseek_coder_33b_instruct_snippet_marked_code_only_xml_pass_at_k_1_to_11.csv",
    },
    "gpt_oss_20b": {
        "label": "gpt-oss",
        "color": "#805ad5",
        "marker": "D",
        "docs": "gpt_oss_20b_docs_snippet_marked_code_only_xml_pass_at_k_1_to_11.csv",
        "snippet": "gpt_oss_20b_snippet_marked_code_only_xml_pass_at_k_1_to_11.csv",
    },
}

METRIC_PREFIX = {
    "pass": "pass@",
    "block_strict": "block_strict_pass@",
    "module_strict": "module_strict_pass@",
}

METRIC_TITLE = {
    "pass": "pass@k",
    "block_strict": "block_strict_pass@k",
    "module_strict": "module_strict_pass@k",
}

DISPLAY_TITLE = {
    "pass": "pass@k",
    "block_strict": "pass@k",
    "module_strict": "pass@k",
}


def lighten(color: str, amount: float = 0.22) -> tuple[float, float, float]:
    rgb = mcolors.to_rgb(color)
    return tuple(1 - (1 - channel) * (1 - amount) for channel in rgb)


def load_series(csv_name: str, metric: str) -> pd.DataFrame:
    prefix = METRIC_PREFIX[metric]
    row = pd.read_csv(RESULTS_DIR / csv_name).iloc[0]
    points = []
    for k in range(1, 12):
        col = f"{prefix}{k}"
        points.append({"k": k, "value": float(row[col]) * 100.0})
    return pd.DataFrame(points)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot docs vs snippet pass@k curves")
    parser.add_argument(
        "--metric",
        choices=sorted(METRIC_PREFIX),
        default="pass",
        help="Metric family to plot",
    )
    parser.add_argument(
        "--hide-title",
        action="store_true",
        help="Do not render a chart title",
    )
    args = parser.parse_args()

    metric = args.metric
    out_base = RESULTS_DIR / f"docs_vs_snippet_{metric}_curves"

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(10.8, 6.6), constrained_layout=True)

    for model_key, style in MODEL_FILES.items():
        docs = load_series(style["docs"], metric)
        snippet = load_series(style["snippet"], metric)

        ax.plot(
            docs["k"],
            docs["value"],
            color=lighten(style["color"], 0.22),
            linestyle="--",
            linewidth=2.3,
            marker=style["marker"],
            markersize=5.8,
            alpha=1.0,
        )
        ax.plot(
            snippet["k"],
            snippet["value"],
            color=style["color"],
            linestyle="-",
            linewidth=2.8,
            marker=style["marker"],
            markersize=5.8,
            alpha=1.0,
        )

    if not args.hide_title:
        ax.set_title(
            f"{DISPLAY_TITLE[metric]} Evolution by Model and Prompt Variant",
            fontsize=20,
            fontweight="bold",
            pad=14,
        )
    ax.set_xlabel("k", fontsize=18, fontweight="bold")
    ax.set_ylabel(f"{DISPLAY_TITLE[metric]} (%)", fontsize=18, fontweight="bold")
    ax.set_xticks(list(range(1, 12)))
    ax.set_ylim(0, 100)
    ax.tick_params(axis="both", labelsize=18, width=1.4)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontweight("bold")

    ax.grid(axis="y", linestyle=":", linewidth=1.0, color="#9aa7b3")
    ax.grid(axis="x", visible=False)

    model_handles = [
        mlines.Line2D(
            [],
            [],
            color=style["color"],
            marker=style["marker"],
            linestyle="-",
            linewidth=2.4,
            markersize=6,
            label=style["label"],
        )
        for style in MODEL_FILES.values()
    ]
    variant_handles = [
        mlines.Line2D([], [], color="#444444", linestyle="-", linewidth=2.6, label="snippet-only"),
        mlines.Line2D([], [], color="#888888", linestyle="--", linewidth=2.1, label="with docs"),
    ]

    legend_models = ax.legend(
        handles=model_handles,
        loc="lower right",
        ncol=2,
        frameon=True,
        title="Models",
        fontsize=14,
        title_fontsize=16,
    )
    ax.add_artist(legend_models)
    ax.legend(
        handles=variant_handles,
        loc="lower left",
        frameon=True,
        title="Variant",
        fontsize=14,
        title_fontsize=16,
    )

    fig.savefig(out_base.with_suffix(".svg"), format="svg")
    fig.savefig(out_base.with_suffix(".png"), format="png", dpi=180)
    plt.close(fig)

    print(f"[OK] Wrote {out_base.with_suffix('.svg')}")
    print(f"[OK] Wrote {out_base.with_suffix('.png')}")


if __name__ == "__main__":
    main()
