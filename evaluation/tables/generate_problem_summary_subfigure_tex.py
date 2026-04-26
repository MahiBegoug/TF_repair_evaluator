"""
Generate Overleaf-ready LaTeX snippets that combine the per-model summary
repair-rate PDFs into a single figure with subfigures.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "evaluation" / "results" / "eval_1_completed_from_prior" / "figures" / "problem_summary" / "per_model"
OUT_DIR = ROOT / "evaluation" / "results" / "eval_1_completed_from_prior" / "tables"

MODELS = [
    ("codellama_summary_fixrate.pdf", "CodeLlama"),
    ("codestral_summary_fixrate.pdf", "Codestral"),
    ("deepseek_coder_summary_fixrate.pdf", "DeepSeek-Coder"),
    ("gpt_oss_summary_fixrate.pdf", "GPT-OSS"),
]


def render(metric: str, caption: str, label: str) -> str:
    lines = [
        "% Requires: \\usepackage{graphicx}",
        "% Requires: \\usepackage{subcaption}",
        "\\begin{figure*}[t]",
        "\\centering",
    ]

    for idx, (filename, model_label) in enumerate(MODELS, start=1):
        path = f"figures/problem_summary/per_model/{metric}/{filename}".replace("\\", "/")
        lines.extend(
            [
                "\\begin{subfigure}[t]{0.48\\textwidth}",
                "\\centering",
                f"\\includegraphics[width=\\linewidth]{{{path}}}",
                f"\\caption{{{model_label}}}",
                "\\end{subfigure}",
            ]
        )
        if idx % 2 == 1:
            lines.append("\\hfill")
        elif idx != len(MODELS):
            lines.append("\\vspace{0.6em}")

    lines.extend(
        [
            f"\\caption{{{caption}}}",
            f"\\label{{{label}}}",
            "\\end{figure*}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    block_tex = render(
        "block_strict",
        "Block-level repair rate (\\%) across the most frequent validation summaries for local context and local context augmented with schema prompting, shown separately for each model.",
        "fig:block_strict_summary_fixrate_per_model",
    )
    module_tex = render(
        "module_strict",
        "Module-level repair rate (\\%) across the most frequent validation summaries for local context and local context augmented with schema prompting, shown separately for each model.",
        "fig:module_strict_summary_fixrate_per_model",
    )

    block_path = OUT_DIR / "block_strict_summary_fixrate_subfigures.tex"
    module_path = OUT_DIR / "module_strict_summary_fixrate_subfigures.tex"

    block_path.write_text(block_tex, encoding="utf-8")
    module_path.write_text(module_tex, encoding="utf-8")

    print(f"[OK] wrote {block_path}")
    print(f"[OK] wrote {module_path}")


if __name__ == "__main__":
    main()
