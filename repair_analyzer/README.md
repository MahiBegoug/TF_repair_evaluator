# Repair Analyzer

This directory is the standalone repair-analysis component for TFRepair.

It contains:
- `repair_analysis.py`: thin public facade and CLI
- `loader.py`: input loading and scope-aware joins
- `summaries.py`: iteration/type aggregation logic
- `renderers.py`: figure and PDF/SVG rendering
- `report.py`: HTML dashboard rendering
- `pipeline.py`: artifact generation workflow
- `utils.py` and `constants.py`: shared helpers
- `generated/`: exported analysis bundles

Each generated analysis bundle is structured as:
- `csv/`: tabular summaries and detailed exports
- `figures/svg/`: vector SVG figures
- `figures/pdf/`: paper-ready PDF figures
- `reports/`: HTML report

Example:

```bash
python -m repair_analyzer.repair_analysis \
  --fixes-csv llm_responses\\CodeLlama_34b_Instruct_hf_docs_snippet_marked_code_only_xml.csv \
  --outcomes-csv llms_fixes_results\\CodeLlama_34b_Instruct_hf_docs_snippet_marked_code_only_xml_repair_results.csv \
  --diagnostics-csv llms_fixes_results\\CodeLlama_34b_Instruct_hf_docs_snippet_marked_code_only_xml_new_diagnostics_after_validation.csv \
  --problems-csv problems\\problems.csv
```

If `--analysis-dir` is omitted, outputs are written under `repair_analyzer/generated/`.
