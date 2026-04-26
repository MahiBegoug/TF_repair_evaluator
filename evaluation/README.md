# Evaluation

This directory is organized by evaluation task. Run scripts from the project root
(`C:\Users\Admin\PycharmProjects\TFRepair`) unless a script says otherwise.

## Layout

- `passk/`: pass@k estimators, strict pass@k export, synthetic outcome generation, and the end-to-end evaluator.
- `prompt_context/`: prompt-size, token/character, and docs-vs-snippet analyses.
- `statistics/`: paired model/significance tests and compatibility analysis wrappers.
- `tables/`: LaTeX/table/figure helper generators.
- `config/`: evaluation configuration files.
- `data/`: small input/output CSVs that are not generated result bundles.
- `results/`: generated result CSVs, reports, figures, and test outputs.

## Common Commands

Generate synthetic outcomes:

```bash
python evaluation/passk/generate_synthetic_outcomes.py
```

Calculate pass@k:

```bash
python evaluation/passk/calculate_pass_at_k.py --problems-csv evaluation/data/problems.csv --fixes-csv evaluation/data/gemini_synthetic_fixes.csv --k-values 1 5 10
```

Evaluate all configured models:

```bash
python evaluation/passk/evaluate_all_models.py --config evaluation/config/evaluation_config.json
```

Export block/module strict pass@k files:

```bash
python evaluation/passk/export_strict_passk_results.py
```

Run the paired docs-vs-snippet block-strict test:

```bash
python evaluation/prompt_context/analyze_docs_vs_snippet_block_strict_pairs.py
```

Run the rigorous iteration-1 docs-vs-snippet analysis with corrected per-model tests:

```bash
python evaluation/prompt_context/analyze_docs_vs_snippet_block_strict_rigorous.py
```

Run prompt-character analyses:

```bash
python evaluation/prompt_context/analyze_docs_prompt_chars_block_strict_iter1.py
python evaluation/prompt_context/analyze_docs_prompt_chars_block_strict_by_iteration.py
```

## Main Result Locations

- `results/tests/docs_vs_snippet_block_strict_paired/`: realistic paired docs-vs-snippet McNemar tests.
- `results/tests/docs_prompt_chars_block_strict_iter1/`: iteration-1 prompt-char correlation tests.
- `results/tests/docs_prompt_chars_block_strict_by_iteration/`: per-iteration prompt-char correlation tests.
- `results/eval_1_completed_from_prior/`: completed eval-1 strict pass@k tables and figures.

## Pass@k Definition

For `n` generated samples and `c` correct samples:

```text
pass@k = 1 - E [ combination(n-c, k) / combination(n, k) ]
```

This is the unbiased estimator from Chen et al. (2021).
