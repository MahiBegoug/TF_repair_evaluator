This directory contains raw LLM-response inspection notes for instances where the raw response CSV has 11 samples, but the corresponding `_repair_results.csv` output is missing one evaluated row.

Purpose:
- Separate evaluator-output gaps from model-output gaps.
- Show whether `fixed_block_content` was already empty before evaluation.

Files:
- `codestral_22b_docs_missing_eval_instances.md`
- `deepseek_coder_33b_docs_missing_eval_instances.md`

Conclusion from these files:
- The affected rows already have empty `fixed_block_content` in `llm_responses/*.csv`.
- The missing `_repair_results.csv` rows are therefore consistent with the evaluator skipping rows that contain no usable patch content.
