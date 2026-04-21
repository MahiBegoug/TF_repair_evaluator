import difflib
import html
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "evaluation" / "results" / "docs_fail_snippet_success"
CASES_CSV = RESULTS_DIR / "all_models_cases.csv"
OUTPUT_HTML = RESULTS_DIR / "inspector.html"

MODEL_FILES = {
    "CodeLlama_34b_Instruct_hf": {
        "docs": "CodeLlama_34b_Instruct_hf_docs_snippet_marked_code_only_xml",
        "snippet": "CodeLlama_34b_Instruct_hf_snippet_marked_code_only_xml",
    },
    "Codestral_22B_v0.1": {
        "docs": "Codestral_22B_v0.1_docs_snippet_marked_code_only_xml",
        "snippet": "Codestral_22B_v0.1_snippet_marked_code_only_xml",
    },
    "deepseek_coder_33b_instruct": {
        "docs": "deepseek_coder_33b_instruct_docs_snippet_marked_code_only_xml",
        "snippet": "deepseek_coder_33b_instruct_snippet_marked_code_only_xml",
    },
    "gpt_oss_20b": {
        "docs": "gpt_oss_20b_docs_snippet_marked_code_only_xml",
        "snippet": "gpt_oss_20b_snippet_marked_code_only_xml",
    },
}


def _text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() == "true"


def _float_or_none(value):
    if pd.isna(value):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _int_or_none(value):
    if pd.isna(value):
        return None
    try:
        return int(value)
    except Exception:
        return None


def _ratio(left: str, right: str) -> float:
    return round(difflib.SequenceMatcher(None, left, right).ratio(), 4)


def _unified_diff(left: str, right: str, left_name: str, right_name: str) -> str:
    diff = difflib.unified_diff(
        left.splitlines(),
        right.splitlines(),
        fromfile=left_name,
        tofile=right_name,
        lineterm="",
    )
    return "\n".join(diff)


def _load_raw_variant(model_file: str) -> pd.DataFrame:
    path = ROOT / "llm_responses" / f"{model_file}.csv"
    raw = pd.read_csv(path)
    keep = [
        "specific_oid",
        "iteration_id",
        "fixed_block_content",
        "raw_llm_output",
        "prompt_content",
    ]
    raw = raw[keep].copy()
    raw["specific_oid"] = raw["specific_oid"].astype(str)
    raw["iteration_id"] = raw["iteration_id"].astype(int)
    return raw


def _load_cases() -> pd.DataFrame:
    cases = pd.read_csv(CASES_CSV)
    cases["specific_oid"] = cases["specific_oid"].astype(str)
    cases["iteration_id"] = cases["iteration_id"].astype(int)
    return cases


def build_records() -> list[dict]:
    cases = _load_cases()
    merged_frames = []

    for model_label, pair in MODEL_FILES.items():
        model_cases = cases[cases["model"] == model_label].copy()
        if model_cases.empty:
            continue

        docs_raw = _load_raw_variant(pair["docs"]).rename(
            columns={
                "fixed_block_content": "docs_fixed_block_content",
                "raw_llm_output": "docs_raw_llm_output",
                "prompt_content": "docs_prompt_content",
            }
        )
        snippet_raw = _load_raw_variant(pair["snippet"]).rename(
            columns={
                "fixed_block_content": "snippet_fixed_block_content",
                "raw_llm_output": "snippet_raw_llm_output",
                "prompt_content": "snippet_prompt_content",
            }
        )

        model_cases = model_cases.merge(
            docs_raw,
            on=["specific_oid", "iteration_id"],
            how="left",
        ).merge(
            snippet_raw,
            on=["specific_oid", "iteration_id"],
            how="left",
        )
        merged_frames.append(model_cases)

    merged = pd.concat(merged_frames, ignore_index=True)
    records = []

    for row in merged.to_dict("records"):
        docs_fix = _text(row.get("docs_fixed_block_content"))
        snippet_fix = _text(row.get("snippet_fixed_block_content"))
        docs_raw = _text(row.get("docs_raw_llm_output"))
        snippet_raw = _text(row.get("snippet_raw_llm_output"))

        records.append(
            {
                "case_id": f"{row['model']}::{row['specific_oid']}::{row['iteration_id']}",
                "model": _text(row.get("model")),
                "specific_oid": _text(row.get("specific_oid")),
                "iteration_id": _int_or_none(row.get("iteration_id")),
                "project_name": _text(row.get("project_name")),
                "filename": _text(row.get("filename")),
                "line_start": _int_or_none(row.get("line_start")),
                "line_end": _int_or_none(row.get("line_end")),
                "provider_name": _text(row.get("provider_name")),
                "block_type": _text(row.get("block_type")),
                "summary": _text(row.get("summary")),
                "detail": _text(row.get("detail")),
                "severity": _text(row.get("severity")),
                "problem_class": _text(row.get("problem_class")),
                "problem_category": _text(row.get("problem_category")),
                "metrics_depth": _float_or_none(row.get("metrics_depth")),
                "metrics_loc": _float_or_none(row.get("metrics_loc")),
                "metrics_nloc": _float_or_none(row.get("metrics_nloc")),
                "metrics_nested_block_count": _float_or_none(row.get("metrics_nested_block_count")),
                "metrics_template_expressions": _float_or_none(row.get("metrics_template_expressions")),
                "metrics_references": _float_or_none(row.get("metrics_references")),
                "metrics_attributes": _float_or_none(row.get("metrics_attributes")),
                "file_loc": _float_or_none(row.get("file_loc")),
                "fan_in_count": _float_or_none(row.get("fan_in_count")),
                "fan_out_count": _float_or_none(row.get("fan_out_count")),
                "docs_fixed": _bool(row.get("line_specific_error_fixed_docs")),
                "snippet_fixed": _bool(row.get("line_specific_error_fixed_snippet")),
                "docs_is_fixed": _bool(row.get("is_fixed_docs")),
                "snippet_is_fixed": _bool(row.get("is_fixed_snippet")),
                "docs_module_fix_introduced_errors": _int_or_none(row.get("module_fix_introduced_errors_docs")),
                "snippet_module_fix_introduced_errors": _int_or_none(row.get("module_fix_introduced_errors_snippet")),
                "docs_block_fix_introduced_errors": _int_or_none(row.get("block_fix_introduced_errors_docs")),
                "snippet_block_fix_introduced_errors": _int_or_none(row.get("block_fix_introduced_errors_snippet")),
                "docs_empty": _bool(row.get("fixed_docs_empty")),
                "snippet_empty": _bool(row.get("fixed_snippet_empty")),
                "docs_fix_len": _int_or_none(row.get("docs_fix_len")),
                "snippet_fix_len": _int_or_none(row.get("snippet_fix_len")),
                "docs_raw_len": _int_or_none(row.get("docs_raw_len")),
                "snippet_raw_len": _int_or_none(row.get("snippet_raw_len")),
                "docs_fix": docs_fix,
                "snippet_fix": snippet_fix,
                "docs_raw_output": docs_raw,
                "snippet_raw_output": snippet_raw,
                "docs_prompt_content": _text(row.get("docs_prompt_content")),
                "snippet_prompt_content": _text(row.get("snippet_prompt_content")),
                "fix_similarity": _ratio(docs_fix, snippet_fix),
                "raw_similarity": _ratio(docs_raw, snippet_raw),
                "fix_diff": _unified_diff(docs_fix, snippet_fix, "docs_fix", "snippet_fix"),
                "raw_diff": _unified_diff(docs_raw, snippet_raw, "docs_raw", "snippet_raw"),
            }
        )

    records.sort(key=lambda r: (r["model"], r["summary"], r["provider_name"], r["specific_oid"], r["iteration_id"]))
    return records


def build_html(records: list[dict]) -> str:
    payload = json.dumps(records, ensure_ascii=False)
    payload = payload.replace("</", "<\\/")
    title = "Docs Fail / Snippet Succeed Inspector"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {{
      --bg: #f4efe7;
      --panel: #fffdf8;
      --ink: #1f1a17;
      --muted: #6f6358;
      --line: #d8cbbd;
      --accent: #9e3d22;
      --accent-2: #275d63;
      --bad: #9b2226;
      --good: #2a6f4f;
      --warn: #b7791f;
      --code-bg: #f8f4ee;
      --shadow: 0 10px 30px rgba(31, 26, 23, 0.08);
      --radius: 16px;
      --mono: "Cascadia Code", "SFMono-Regular", Consolas, monospace;
      --sans: "Segoe UI", system-ui, sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: var(--sans);
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(158, 61, 34, 0.09), transparent 24rem),
        radial-gradient(circle at right, rgba(39, 93, 99, 0.08), transparent 22rem),
        var(--bg);
    }}
    .app {{
      display: grid;
      grid-template-columns: 360px 1fr;
      min-height: 100vh;
      gap: 0;
    }}
    .sidebar {{
      border-right: 1px solid var(--line);
      background: rgba(255, 253, 248, 0.92);
      backdrop-filter: blur(12px);
      padding: 20px;
      overflow: auto;
    }}
    .content {{
      padding: 24px;
      overflow: auto;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 28px;
      line-height: 1.1;
    }}
    .subtitle {{
      color: var(--muted);
      margin: 0 0 18px;
    }}
    .filters {{
      display: grid;
      gap: 10px;
      margin-bottom: 16px;
    }}
    .quick-models {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 14px;
    }}
    .quick-model {{
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      border-radius: 999px;
      padding: 7px 10px;
      font: inherit;
      font-size: 12px;
      cursor: pointer;
    }}
    .quick-model.active {{
      border-color: var(--accent);
      color: var(--accent);
      box-shadow: 0 0 0 2px rgba(158, 61, 34, 0.12);
    }}
    label {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      display: grid;
      gap: 6px;
    }}
    input, select {{
      width: 100%;
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 10px;
      padding: 10px 12px;
      color: var(--ink);
      font: inherit;
    }}
    .checkbox-row {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: var(--muted);
      margin: 6px 0 12px;
    }}
    .checkbox-row input {{
      width: auto;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }}
    .stat {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
      box-shadow: var(--shadow);
    }}
    .stat .k {{
      display: block;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 4px;
    }}
    .stat .v {{
      font-size: 20px;
      font-weight: 700;
    }}
    .case-list {{
      display: grid;
      gap: 10px;
    }}
    .list-toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      margin-bottom: 12px;
      color: var(--muted);
      font-size: 12px;
    }}
    .case-item {{
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      background: var(--panel);
      cursor: pointer;
      box-shadow: var(--shadow);
    }}
    .case-item.active {{
      border-color: var(--accent);
      box-shadow: 0 0 0 2px rgba(158, 61, 34, 0.15), var(--shadow);
    }}
    .case-item .top {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      align-items: baseline;
    }}
    .case-item .title {{
      font-weight: 700;
      font-size: 14px;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 12px;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--muted);
    }}
    .pill.good {{ color: var(--good); border-color: rgba(42, 111, 79, 0.25); }}
    .pill.bad {{ color: var(--bad); border-color: rgba(155, 34, 38, 0.25); }}
    .case-meta {{
      margin-top: 8px;
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
    }}
    .empty {{
      color: var(--muted);
      font-style: italic;
      padding: 24px;
      border: 1px dashed var(--line);
      border-radius: 16px;
      background: rgba(255, 253, 248, 0.6);
    }}
    .hero {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: start;
      margin-bottom: 16px;
    }}
    .hero-tools {{
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 8px;
    }}
    .tool-btn {{
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      border-radius: 999px;
      padding: 8px 12px;
      font: inherit;
      font-size: 12px;
      cursor: pointer;
    }}
    .hero-card {{
      flex: 1;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      box-shadow: var(--shadow);
    }}
    .hero-title {{
      font-size: 28px;
      line-height: 1.1;
      margin: 0 0 10px;
    }}
    .hero-sub {{
      color: var(--muted);
      margin: 0;
    }}
    .badge-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }}
    .grid {{
      display: grid;
      gap: 16px;
    }}
    .grid.two {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      box-shadow: var(--shadow);
    }}
    .panel h2 {{
      margin: 0 0 12px;
      font-size: 18px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th, td {{
      text-align: left;
      padding: 8px 0;
      border-bottom: 1px solid rgba(216, 203, 189, 0.6);
      vertical-align: top;
      font-size: 14px;
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
      width: 34%;
      padding-right: 16px;
    }}
    .code-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }}
    .code-box {{
      border: 1px solid var(--line);
      border-radius: 14px;
      overflow: hidden;
      background: #fff;
    }}
    .code-box header {{
      padding: 10px 12px;
      background: linear-gradient(90deg, rgba(158, 61, 34, 0.08), rgba(39, 93, 99, 0.08));
      border-bottom: 1px solid var(--line);
      font-size: 13px;
      font-weight: 700;
    }}
    pre {{
      margin: 0;
      padding: 14px;
      background: var(--code-bg);
      color: var(--ink);
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 12px;
      line-height: 1.45;
      font-family: var(--mono);
      min-height: 180px;
    }}
    .diff pre {{
      min-height: 220px;
    }}
    .note {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 8px;
    }}
    .big-stat-row {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    .big-stat {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px;
      box-shadow: var(--shadow);
    }}
    .big-stat .label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      display: block;
      margin-bottom: 6px;
    }}
    .big-stat .value {{
      font-size: 22px;
      font-weight: 700;
    }}
    @media (max-width: 1180px) {{
      .app {{ grid-template-columns: 1fr; }}
      .sidebar {{ border-right: 0; border-bottom: 1px solid var(--line); max-height: 48vh; }}
      .grid.two, .code-grid, .big-stat-row {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <h1>Docs vs Snippet</h1>
      <p class="subtitle">Inspect same-instance cases where documentation failed but snippet-only succeeded.</p>
      <div id="quickModels" class="quick-models"></div>
      <div class="filters">
        <label>Search
          <input id="search" type="search" placeholder="specific_oid, file, summary, provider">
        </label>
        <label>Model
          <select id="modelFilter"></select>
        </label>
        <label>Summary
          <select id="summaryFilter"></select>
        </label>
        <label>Provider
          <select id="providerFilter"></select>
        </label>
      </div>
      <label class="checkbox-row"><input id="docsEmptyOnly" type="checkbox"> Only docs-empty cases</label>
      <div class="stats">
        <div class="stat"><span class="k">Visible Cases</span><span class="v" id="visibleCount">0</span></div>
        <div class="stat"><span class="k">Models</span><span class="v" id="visibleModels">0</span></div>
      </div>
      <div class="list-toolbar">
        <span id="selectionInfo">Select a case</span>
        <button id="clearFilters" class="tool-btn" type="button">Reset</button>
      </div>
      <div id="caseList" class="case-list"></div>
    </aside>
    <main class="content">
      <div id="emptyState" class="empty">No case selected.</div>
      <div id="detail" hidden>
        <section class="hero">
          <div class="hero-card">
            <p class="pill bad">Docs failed</p>
            <p class="pill good">Snippet succeeded</p>
            <h2 id="heroTitle" class="hero-title"></h2>
            <p id="heroSub" class="hero-sub"></p>
            <div id="heroBadges" class="badge-row"></div>
            <div class="hero-tools">
              <button id="prevCase" class="tool-btn" type="button">Previous</button>
              <button id="nextCase" class="tool-btn" type="button">Next</button>
              <button id="randomCase" class="tool-btn" type="button">Random</button>
            </div>
          </div>
        </section>
        <section class="big-stat-row">
          <div class="big-stat"><span class="label">Fix Similarity</span><span id="fixSimilarity" class="value"></span></div>
          <div class="big-stat"><span class="label">Raw Similarity</span><span id="rawSimilarity" class="value"></span></div>
          <div class="big-stat"><span class="label">Docs Fix Length</span><span id="docsFixLen" class="value"></span></div>
          <div class="big-stat"><span class="label">Snippet Fix Length</span><span id="snippetFixLen" class="value"></span></div>
        </section>
        <section class="grid two">
          <div class="panel">
            <h2>Benchmark Metadata</h2>
            <table id="metaTable"></table>
          </div>
          <div class="panel">
            <h2>Outcome Contrast</h2>
            <table id="outcomeTable"></table>
            <p class="note">These values come from the matched `*_repair_results.csv` rows for the same `specific_oid` and `iteration_id`.</p>
          </div>
        </section>
        <section class="panel diff">
          <h2>Fixed Block Diff</h2>
          <pre id="fixDiff"></pre>
        </section>
        <section class="code-grid">
          <div class="code-box">
            <header>Docs: fixed_block_content</header>
            <pre id="docsFix"></pre>
          </div>
          <div class="code-box">
            <header>Snippet: fixed_block_content</header>
            <pre id="snippetFix"></pre>
          </div>
        </section>
        <section class="panel diff">
          <h2>Raw LLM Output Diff</h2>
          <pre id="rawDiff"></pre>
        </section>
        <section class="code-grid">
          <div class="code-box">
            <header>Docs: raw_llm_output</header>
            <pre id="docsRaw"></pre>
          </div>
          <div class="code-box">
            <header>Snippet: raw_llm_output</header>
            <pre id="snippetRaw"></pre>
          </div>
        </section>
      </div>
    </main>
  </div>

  <script id="records" type="application/json">{payload}</script>
  <script>
    const records = JSON.parse(document.getElementById('records').textContent);
    const state = {{
      selectedId: null,
      search: '',
      model: 'All',
      summary: 'All',
      provider: 'All',
      docsEmptyOnly: false,
      filtered: [],
    }};

    const els = {{
      search: document.getElementById('search'),
      modelFilter: document.getElementById('modelFilter'),
      summaryFilter: document.getElementById('summaryFilter'),
      providerFilter: document.getElementById('providerFilter'),
      docsEmptyOnly: document.getElementById('docsEmptyOnly'),
      quickModels: document.getElementById('quickModels'),
      visibleCount: document.getElementById('visibleCount'),
      visibleModels: document.getElementById('visibleModels'),
      selectionInfo: document.getElementById('selectionInfo'),
      clearFilters: document.getElementById('clearFilters'),
      caseList: document.getElementById('caseList'),
      emptyState: document.getElementById('emptyState'),
      detail: document.getElementById('detail'),
      heroTitle: document.getElementById('heroTitle'),
      heroSub: document.getElementById('heroSub'),
      heroBadges: document.getElementById('heroBadges'),
      fixSimilarity: document.getElementById('fixSimilarity'),
      rawSimilarity: document.getElementById('rawSimilarity'),
      docsFixLen: document.getElementById('docsFixLen'),
      snippetFixLen: document.getElementById('snippetFixLen'),
      metaTable: document.getElementById('metaTable'),
      outcomeTable: document.getElementById('outcomeTable'),
      fixDiff: document.getElementById('fixDiff'),
      docsFix: document.getElementById('docsFix'),
      snippetFix: document.getElementById('snippetFix'),
      rawDiff: document.getElementById('rawDiff'),
      docsRaw: document.getElementById('docsRaw'),
      snippetRaw: document.getElementById('snippetRaw'),
      prevCase: document.getElementById('prevCase'),
      nextCase: document.getElementById('nextCase'),
      randomCase: document.getElementById('randomCase'),
    }};

    function uniqueValues(key) {{
      return ['All', ...new Set(records.map(r => r[key]).filter(Boolean))].sort();
    }}

    function populateSelect(el, values) {{
      el.innerHTML = values.map(v => `<option value="${{escapeHtml(String(v))}}">${{escapeHtml(String(v))}}</option>`).join('');
    }}

    function escapeHtml(value) {{
      return value
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');
    }}

    function filteredRecords() {{
      const q = state.search.trim().toLowerCase();
      return records.filter(r => {{
        if (state.model !== 'All' && r.model !== state.model) return false;
        if (state.summary !== 'All' && r.summary !== state.summary) return false;
        if (state.provider !== 'All' && r.provider_name !== state.provider) return false;
        if (state.docsEmptyOnly && !r.docs_empty) return false;
        if (!q) return true;
        const hay = [
          r.specific_oid,
          r.project_name,
          r.filename,
          r.summary,
          r.provider_name,
          r.problem_category,
          r.problem_class,
          r.docs_fix,
          r.snippet_fix,
          r.docs_raw_output,
          r.snippet_raw_output,
        ].join('\\n').toLowerCase();
        return hay.includes(q);
      }});
    }}

    function renderQuickModels() {{
      const models = uniqueValues('model').filter(v => v !== 'All');
      const buttons = [
        {{ label: 'All Models', value: 'All' }},
        ...models.map(model => ({{ label: model, value: model }})),
      ];
      els.quickModels.innerHTML = buttons.map(btn => {{
        const active = state.model === btn.value ? ' active' : '';
        return `<button class="quick-model${{active}}" data-value="${{escapeHtml(btn.value)}}">${{escapeHtml(btn.label)}}</button>`;
      }}).join('');
      els.quickModels.querySelectorAll('.quick-model').forEach(node => {{
        node.addEventListener('click', () => {{
          state.model = node.dataset.value;
          els.modelFilter.value = state.model;
          render();
        }});
      }});
    }}

    function selectedIndex(items) {{
      return items.findIndex(i => i.case_id === state.selectedId);
    }}

    function stepSelection(delta) {{
      const items = state.filtered;
      if (!items.length) return;
      const idx = selectedIndex(items);
      const next = idx < 0 ? 0 : (idx + delta + items.length) % items.length;
      state.selectedId = items[next].case_id;
      render();
    }}

    function selectRandom() {{
      const items = state.filtered;
      if (!items.length) return;
      const next = Math.floor(Math.random() * items.length);
      state.selectedId = items[next].case_id;
      render();
    }}

    function resetFilters() {{
      state.search = '';
      state.model = uniqueValues('model').find(v => v !== 'All') || 'All';
      state.summary = 'All';
      state.provider = 'All';
      state.docsEmptyOnly = false;
      els.search.value = '';
      els.modelFilter.value = state.model;
      els.summaryFilter.value = state.summary;
      els.providerFilter.value = state.provider;
      els.docsEmptyOnly.checked = false;
      state.selectedId = null;
      render();
    }}

    function renderList(items) {{
      state.filtered = items;
      els.visibleCount.textContent = String(items.length);
      els.visibleModels.textContent = String(new Set(items.map(i => i.model)).size);

      if (!items.length) {{
        els.caseList.innerHTML = '<div class="empty">No cases match the current filters.</div>';
        els.selectionInfo.textContent = '0 / 0';
        els.emptyState.hidden = false;
        els.detail.hidden = true;
        return;
      }}

      if (!state.selectedId || !items.some(i => i.case_id === state.selectedId)) {{
        state.selectedId = items[0].case_id;
      }}

      const idx = selectedIndex(items);
      els.selectionInfo.textContent = `${{idx + 1}} / ${{items.length}}`;

      els.caseList.innerHTML = items.map(item => {{
        const active = item.case_id === state.selectedId ? ' active' : '';
        const docsBadge = item.docs_empty ? '<span class="pill bad">docs empty</span>' : '';
        return `
          <div class="case-item${{active}}" data-id="${{escapeHtml(item.case_id)}}">
            <div class="top">
              <div class="title">${{escapeHtml(item.summary)}}</div>
              <span class="pill">${{escapeHtml(item.specific_oid)}} · #${{item.iteration_id}}</span>
            </div>
            <div class="case-meta">
              <span>${{escapeHtml(item.model)}}</span>
              <span>${{escapeHtml(item.provider_name || 'unknown provider')}}</span>
              <span>${{escapeHtml(item.block_type || 'unknown block')}}</span>
              ${{docsBadge}}
            </div>
            <div class="case-meta">
              <span>${{escapeHtml(item.project_name)}}</span>
            </div>
          </div>
        `;
      }}).join('');

      els.caseList.querySelectorAll('.case-item').forEach(node => {{
        node.addEventListener('click', () => {{
          state.selectedId = node.dataset.id;
          render();
        }});
      }});

      const selected = items.find(i => i.case_id === state.selectedId);
      renderDetail(selected);
    }}

    function tableRows(rows) {{
      return rows.map(([k, v]) => `
        <tr>
          <th>${{escapeHtml(k)}}</th>
          <td>${{escapeHtml(v == null ? '' : String(v))}}</td>
        </tr>
      `).join('');
    }}

    function renderDetail(item) {{
      if (!item) {{
        els.emptyState.hidden = false;
        els.detail.hidden = true;
        return;
      }}

      els.emptyState.hidden = true;
      els.detail.hidden = false;

      els.heroTitle.textContent = `${{item.summary}} · ${{item.specific_oid}} · #${{item.iteration_id}}`;
      els.heroSub.textContent = `${{item.model}} · ${{item.project_name}} · ${{item.filename}}`;
      els.heroBadges.innerHTML = [
        item.provider_name ? `<span class="pill">${{escapeHtml(item.provider_name)}}</span>` : '',
        item.block_type ? `<span class="pill">${{escapeHtml(item.block_type)}}</span>` : '',
        item.problem_category ? `<span class="pill">${{escapeHtml(item.problem_category)}}</span>` : '',
        item.problem_class ? `<span class="pill">${{escapeHtml(item.problem_class)}}</span>` : '',
        item.docs_empty ? '<span class="pill bad">Docs fix empty</span>' : '<span class="pill">Docs fix present</span>',
      ].join('');

      els.fixSimilarity.textContent = `${{(item.fix_similarity * 100).toFixed(1)}}%`;
      els.rawSimilarity.textContent = `${{(item.raw_similarity * 100).toFixed(1)}}%`;
      els.docsFixLen.textContent = String(item.docs_fix_len ?? 0);
      els.snippetFixLen.textContent = String(item.snippet_fix_len ?? 0);

      els.metaTable.innerHTML = tableRows([
        ['Provider', item.provider_name],
        ['Severity', item.severity],
        ['Problem Category', item.problem_category],
        ['Problem Class', item.problem_class],
        ['Block Type', item.block_type],
        ['Lines', `${{item.line_start}}-${{item.line_end}}`],
        ['metrics_depth', item.metrics_depth],
        ['metrics_loc', item.metrics_loc],
        ['metrics_nloc', item.metrics_nloc],
        ['metrics_nested_block_count', item.metrics_nested_block_count],
        ['metrics_template_expressions', item.metrics_template_expressions],
        ['metrics_references', item.metrics_references],
        ['metrics_attributes', item.metrics_attributes],
        ['file_loc', item.file_loc],
        ['fan_in_count', item.fan_in_count],
        ['fan_out_count', item.fan_out_count],
      ]);

      els.outcomeTable.innerHTML = tableRows([
        ['Docs line_specific_error_fixed', item.docs_fixed],
        ['Snippet line_specific_error_fixed', item.snippet_fixed],
        ['Docs is_fixed', item.docs_is_fixed],
        ['Snippet is_fixed', item.snippet_is_fixed],
        ['Docs module introduced errors', item.docs_module_fix_introduced_errors],
        ['Snippet module introduced errors', item.snippet_module_fix_introduced_errors],
        ['Docs block introduced errors', item.docs_block_fix_introduced_errors],
        ['Snippet block introduced errors', item.snippet_block_fix_introduced_errors],
      ]);

      els.fixDiff.textContent = item.fix_diff || '(No diff: texts are identical or empty)';
      els.docsFix.textContent = item.docs_fix || '(empty)';
      els.snippetFix.textContent = item.snippet_fix || '(empty)';
      els.rawDiff.textContent = item.raw_diff || '(No diff: texts are identical or empty)';
      els.docsRaw.textContent = item.docs_raw_output || '(empty)';
      els.snippetRaw.textContent = item.snippet_raw_output || '(empty)';
    }}

    function render() {{
      const items = filteredRecords();
      renderList(items);
    }}

    populateSelect(els.modelFilter, uniqueValues('model'));
    populateSelect(els.summaryFilter, uniqueValues('summary'));
    populateSelect(els.providerFilter, uniqueValues('provider_name'));
    state.model = uniqueValues('model').find(v => v !== 'All') || 'All';
    els.modelFilter.value = state.model;
    renderQuickModels();

    els.search.addEventListener('input', e => {{
      state.search = e.target.value;
      render();
    }});
    els.modelFilter.addEventListener('change', e => {{
      state.model = e.target.value;
      render();
    }});
    els.summaryFilter.addEventListener('change', e => {{
      state.summary = e.target.value;
      render();
    }});
    els.providerFilter.addEventListener('change', e => {{
      state.provider = e.target.value;
      render();
    }});
    els.docsEmptyOnly.addEventListener('change', e => {{
      state.docsEmptyOnly = e.target.checked;
      render();
    }});
    els.clearFilters.addEventListener('click', resetFilters);
    els.prevCase.addEventListener('click', () => stepSelection(-1));
    els.nextCase.addEventListener('click', () => stepSelection(1));
    els.randomCase.addEventListener('click', selectRandom);

    render();
  </script>
</body>
</html>
"""


def main():
    records = build_records()
    OUTPUT_HTML.write_text(build_html(records), encoding="utf-8")
    print(f"Wrote {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
