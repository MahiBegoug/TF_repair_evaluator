import os
import hashlib
import re


def _find_hcl_block(file_lines, target_line_1indexed):
    """
    Pure-Python HCL block finder.
    
    Walks from target_line upward to find the nearest enclosing block header
    (a line matching `type "label" "label" {`), then walks forward to find
    the matching closing brace using bracket counting.
    
    Returns a dict with:
        block_type, block_identifiers, start_line, end_line, content
    or None if no block found.
    """
    # HCL block header pattern: word optional-labels? {
    BLOCK_HEADER = re.compile(
        r'^\s*(resource|data|variable|output|locals|module|provider|terraform)\s*(.*?)\s*\{?\s*$'
    )
    
    idx = target_line_1indexed - 1  # 0-indexed
    if idx < 0 or idx >= len(file_lines):
        return None

    # Walk upward from target line to find the enclosing block header
    block_start_idx = None
    block_type = ""
    block_identifiers = ""

    for i in range(idx, -1, -1):
        line = file_lines[i]
        m = BLOCK_HEADER.match(line)
        if m:
            block_type = m.group(1).strip()
            raw_labels = m.group(2).strip()
            # Extract quoted labels (e.g. "aws_s3_bucket" "my_bucket")
            labels = re.findall(r'"([^"]+)"', raw_labels)
            block_identifiers = " ".join(labels)
            block_start_idx = i
            break

    if block_start_idx is None:
        return None

    # Walk forward from block_start_idx to find the matching closing brace
    depth = 0
    block_end_idx = None
    for i in range(block_start_idx, len(file_lines)):
        depth += file_lines[i].count("{") - file_lines[i].count("}")
        if depth == 0 and i > block_start_idx:
            block_end_idx = i
            break
    
    # Fallback: if depth never closes, just capture to end
    if block_end_idx is None:
        block_end_idx = len(file_lines) - 1

    content = "\n".join(file_lines[block_start_idx:block_end_idx + 1])

    return {
        "block_type": block_type,
        "block_identifiers": f"{block_type} {block_identifiers}".strip(),
        "start_line": block_start_idx + 1,   # 1-indexed
        "end_line": block_end_idx + 1,        # 1-indexed
        "content": content
    }


class DiagnosticsExtractor:
    """
    Extracts diagnostics rows from terraform validate output.
    
    Implements the same OID computation strategy as TFReproducer's DiagnosticsExtractor,
    ensuring that post-fix diagnostics can be matched against problems.csv by OID.
    """

    @staticmethod
    def load_tf_files(module_path):
        cache = {}
        for root, dirs, files in os.walk(module_path):
            # Skip .terraform provider/module cache directories
            dirs[:] = [d for d in dirs if d != ".terraform"]
            for fn in files:
                if fn.endswith(".tf"):
                    fp = os.path.join(root, fn)
                    try:
                        abs_fp = os.path.abspath(fp).replace("\\", "/")
                        with open(fp, "r", encoding="utf-8") as f:
                            cache[abs_fp] = f.read()
                    except Exception as e:
                        abs_fp = os.path.abspath(fp).replace("\\", "/")
                        cache[abs_fp] = f"[ERROR reading file: {e}]"
        return cache

    @staticmethod
    def normalize(diags):
        """Ensure diagnostics is always a list of dicts."""
        if diags is None:
            return []
        if isinstance(diags, dict):
            return [diags]
        if isinstance(diags, list):
            return [d for d in diags if isinstance(d, dict)]
        return []

    @staticmethod
    def compute_oid(r: dict) -> str:
        """
        Location-based OID matching TFReproducer's compute_oid exactly.
        Groups all diagnostics at the same physical file location (filename, start line, end line).
        This is the key lookup used by MetricsCalculator to match against problems.csv.
        """
        base = f"{r['filename']}|{r['line_start']}|{r['line_end']}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def extract_rows(project_name, result, project_root):
        module_path = result["path"]
        rows = []

        try:
            working_dir = os.path.relpath(module_path, project_root).replace("\\", "/")
        except:
            working_dir = ""

        tf_cache = DiagnosticsExtractor.load_tf_files(module_path)
        diagnostics = DiagnosticsExtractor.normalize(result.get("diagnostics"))

        # Initialize StaticAnalyzer for block enrichment (from tf_dependency_analyzer in requirements.txt)
        try:
            from tf_dependency_analyzer.static.static_analyzer import StaticAnalyzer
            analyzer = StaticAnalyzer(module_path)
        except Exception:
            analyzer = None

        for diag in diagnostics:

            drange = diag.get("range", {}) or {}
            start = drange.get("start", {}) or {}
            end = drange.get("end", {}) or {}
            filename_raw = drange.get("filename", "")

            line_start = start.get("line", "")
            line_end = end.get("line", "")

            row = {
                "project_name": project_name,
                "working_directory": working_dir,
                "severity": diag.get("severity", ""),
                "summary": diag.get("summary", ""),
                "detail": diag.get("detail", ""),
                "address": diag.get("address", ""),
                "filename": "",
                "line_start": line_start,
                "col_start": start.get("column", ""),
                "line_end": line_end,
                "col_end": end.get("column", ""),
                "file_content": "",
                # Enriched Block Details
                "block_type": "",
                "block_identifiers": "",
                "impacted_block_start_line": "",
                "impacted_block_end_line": "",
                "impacted_block_content": ""
            }

            # Case 1: Specific file
            if filename_raw:
                # Handle both absolute and relative filenames from terraform
                if os.path.isabs(filename_raw):
                    system_path = filename_raw
                else:
                    system_path = os.path.join(module_path, filename_raw)

                # Use the same clones/project/... format as problems.csv
                repo_clone_root = f"clones/{project_name}"
                relative_path = f"{working_dir}/{filename_raw}".lstrip("/")
                row["filename"] = f"{repo_clone_root}/{relative_path}".replace("\\", "/")

                # Skip diagnostics from third-party .terraform/modules/ cache
                if ".terraform/modules/" in row["filename"] or ".terraform\\modules\\" in row["filename"]:
                    continue

                abs_fp = os.path.abspath(system_path).replace("\\", "/")
                row["file_content"] = tf_cache.get(abs_fp, tf_cache.get(system_path, "[FILE NOT FOUND]"))

                # Two-tier block enrichment:
                # 1st: StaticAnalyzer (tree-sitter, most accurate)
                # 2nd: Pure-Python bracket matching (fallback if StaticAnalyzer unavailable)
                if line_start:
                    details = None
                    if analyzer:
                        try:
                            details = analyzer.get_block_details_by_location(system_path, int(line_start))
                        except Exception as e:
                            print(f"[BLOCK] StaticAnalyzer failed at {filename_raw}:{line_start}: {e}")

                    if details:
                        # StaticAnalyzer returns: block_type, identifiers (str), start_line, end_line, content
                        b_type = details.get("block_type", "")
                        identifiers = details.get("identifiers", "")
                        if isinstance(identifiers, list):
                            identifiers = " ".join(str(i) for i in identifiers)
                        row["block_type"] = b_type
                        row["block_identifiers"] = f"{b_type} {identifiers}".strip()
                        row["impacted_block_start_line"] = details.get("start_line", "")
                        row["impacted_block_end_line"] = details.get("end_line", "")
                        row["impacted_block_content"] = details.get("content", "")
                    else:
                        # Fallback: pure-Python HCL bracket matching
                        file_content_str = row.get("file_content", "")
                        if file_content_str and file_content_str != "[FILE NOT FOUND]":
                            try:
                                file_lines = file_content_str.splitlines()
                                fb = _find_hcl_block(file_lines, int(line_start))
                                if fb:
                                    row["block_type"] = fb["block_type"]
                                    row["block_identifiers"] = fb["block_identifiers"]
                                    row["impacted_block_start_line"] = fb["start_line"]
                                    row["impacted_block_end_line"] = fb["end_line"]
                                    row["impacted_block_content"] = fb["content"]
                                else:
                                    print(f"[BLOCK] No enclosing block found at {filename_raw}:{line_start}")
                            except Exception as e:
                                print(f"[BLOCK] Fallback block extraction failed at {filename_raw}:{line_start}: {e}")

            # Case 2: No file → include all TF files
            else:
                content = []
                for fp, c in tf_cache.items():
                    content.append(c)
                row["file_content"] = "\n".join(content)

            # Compute OID using exact same formula as TFReproducer (for problems.csv matching)
            row["oid"] = DiagnosticsExtractor.compute_oid(row)

            rows.append(row)

        return rows
