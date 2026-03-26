import os
import hashlib
import re


def count_hcl_loc(content: str) -> int:
    """Counts non-blank, non-comment lines of HCL code."""
    lines = content.splitlines()
    loc = 0
    in_block_comment = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if in_block_comment:
            if "*/" in line:
                in_block_comment = False
                rest = line.split("*/", 1)[1].strip()
                if rest and not rest.startswith("#") and not rest.startswith("//"):
                    loc += 1
            continue
            
        if line.startswith("/*"):
            if "*/" in line:
                rest = line.split("*/", 1)[1].strip()
                if rest and not rest.startswith("#") and not rest.startswith("//"):
                    loc += 1
            else:
                in_block_comment = True
            continue
            
        if line.startswith("#") or line.startswith("//"):
            continue
            
        loc += 1
        
    return loc


def _find_hcl_block(file_lines, target_line_1indexed):
    """
    Pure-Python HCL block finder (Fallback tier).
    Walks from target_line upward to find the nearest enclosing block header.
    """
    BLOCK_HEADER = re.compile(
        r'^\s*\b(resource|data|variable|output|locals|module|provider|terraform)\b\s*(.*?)\s*\{?\s*$'
    )
    
    idx = target_line_1indexed - 1
    if idx < 0 or idx >= len(file_lines):
        return None

    block_start_idx = None
    block_type = ""
    block_identifiers = ""

    for i in range(idx, -1, -1):
        line = file_lines[i]
        m = BLOCK_HEADER.match(line)
        if m:
            block_type = m.group(1).strip()
            raw_labels = m.group(2).strip()
            labels = re.findall(r'"([^"]+)"', raw_labels)
            block_identifiers = " ".join(labels)
            block_start_idx = i
            break

    if block_start_idx is None:
        return None

    # Matching brace logic
    depth = 0
    block_end_idx = None
    for i in range(block_start_idx, len(file_lines)):
        depth += file_lines[i].count("{") - file_lines[i].count("}")
        if depth == 0 and i > block_start_idx:
            block_end_idx = i
            break
    
    if block_end_idx is None:
        block_end_idx = len(file_lines) - 1

    return {
        "block_type": block_type,
        "identifiers": block_identifiers,
        "start_line": block_start_idx + 1,
        "end_line": block_end_idx + 1
    }


class DiagnosticsExtractor:
    """
    Extracts diagnostics rows from terraform validate output.
    Alinged with TFReproducer's validation logic for OID and block parity.
    """

    @staticmethod
    def load_tf_files(module_path):
        cache = {}
        for root, dirs, files in os.walk(module_path):
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
        if diags is None: return []
        if isinstance(diags, dict): return [diags]
        if isinstance(diags, list): return [d for d in diags if isinstance(d, dict)]
        return []

    @staticmethod
    def _resolve_file_info(diag, module_path, project_root, tf_cache):
        """Replicates TFReproducer's _resolve_file_info logic."""
        drange = diag.get("range", {}) or {}
        start = drange.get("start", {}) or {}
        end = drange.get("end", {}) or {}
        filename_raw = drange.get("filename", "")

        info = {
            "filename": "",
            "absolute_filename": "",
            "line_start": start.get("line", ""),
            "col_start": start.get("column", ""),
            "line_end": end.get("line", ""),
            "col_end": end.get("column", ""),
            "file_content": "",
            "file_loc": ""
        }

        if filename_raw:
            if os.path.isabs(filename_raw):
                system_path = filename_raw
            else:
                system_path = os.path.join(module_path, filename_raw)
            
            abs_fp = os.path.abspath(system_path).replace("\\", "/")
            info["absolute_filename"] = abs_fp
            
            # Normalize filename to matches baseline OID format (clones/project/path)
            # This handles cases where clones_dir is ../ or absolute.
            if "/clones/" in abs_fp:
                rel_path = "clones/" + abs_fp.split("/clones/")[1]
            elif "\\clones\\" in abs_fp.lower():
                # Handle Windows-style and mixed paths
                parts = re.split(r'[\\/]clones[\\/]', abs_fp, flags=re.IGNORECASE)
                rel_path = "clones/" + parts[-1].replace("\\", "/")
            else:
                try:
                    rel_path = os.path.relpath(system_path, os.getcwd()).replace("\\", "/")
                except (ValueError, OSError):
                    rel_path = abs_fp
            
            info["filename"] = rel_path

            content = tf_cache.get(abs_fp, "[FILE NOT FOUND]")
            if content == "[FILE NOT FOUND]" and os.path.exists(abs_fp):
                try:
                    with open(abs_fp, "r", encoding="utf-8") as f:
                        content = f.read()
                except: pass
            
            info["file_content"] = content
            info["file_loc"] = count_hcl_loc(content) if content != "[FILE NOT FOUND]" else 0
        else:
            # Fallback
            if tf_cache:
                abs_fp = sorted(tf_cache.keys())[0]
                info["absolute_filename"] = abs_fp
                try:
                    info["filename"] = os.path.relpath(abs_fp, os.getcwd()).replace("\\", "/")
                except: info["filename"] = abs_fp
            
            combined = "\n".join(tf_cache.values())
            info["file_content"] = combined
            info["file_loc"] = count_hcl_loc(combined)
            info["line_start"] = -1
            info["line_end"] = -1

        return info

    @staticmethod
    def _add_block_content(row, block, tf_cache):
        """Replicates TFReproducer's _add_block_content logic (Line Slicing)."""
        start_line = block.get("start_line")
        end_line = block.get("end_line")
        abs_fn = row.get("absolute_filename")
        
        if not (start_line and end_line and abs_fn):
            return

        try:
            if abs_fn in tf_cache:
                file_lines = tf_cache[abs_fn].splitlines()
            elif os.path.exists(abs_fn):
                with open(abs_fn, "r", encoding="utf-8") as f:
                    file_lines = f.read().splitlines()
            else:
                return

            block_lines = file_lines[int(start_line) - 1:int(end_line)]
            row["impacted_block_content"] = "\n".join(block_lines)
        except Exception:
            row["impacted_block_content"] = ""

    @staticmethod
    def extract_rows(project_name, result, project_root, latest_commit="") -> list:
        module_path = result["path"]
        rows = []
        
        tf_cache = DiagnosticsExtractor.load_tf_files(module_path)
        diagnostics = DiagnosticsExtractor.normalize(result.get("diagnostics"))

        # Initialize StaticAnalyzer (optional tier)
        try:
            from tf_dependency_analyzer.static.static_analyzer import StaticAnalyzer
            analyzer = StaticAnalyzer(module_path)
        except Exception:
            analyzer = None

        for diag in diagnostics:
            # 1. Initialize full row structure
            row = {
                "project_name": project_name,
                "latest_commit": latest_commit,
                "working_directory": os.path.relpath(module_path, os.getcwd()).replace("\\", "/"),
                "severity": diag.get("severity", ""),
                "summary": diag.get("summary", ""),
                "detail": diag.get("detail", ""),
                "address": diag.get("address", ""),
                "filename": "", "line_start": "", "col_start": "", "line_end": "", "col_end": "",
                "block_type": "", "block_type_full": "", "impacted_block_type": "", "impacted_block_content": "", "block_identifiers": "",
                "impacted_block_start_line": "", "impacted_block_end_line": "",
                "file_content": "", "file_loc": "",
                "metrics_nloc": 0, "metrics_depth": 0, "metrics_attributes": 0, "metrics_references": 0
            }

            # 2. Resolve file info
            file_info = DiagnosticsExtractor._resolve_file_info(diag, module_path, project_root, tf_cache)
            row.update(file_info)

            # Skip .terraform/modules/
            if ".terraform/modules/" in row["filename"] or ".terraform\\modules\\" in row["filename"]:
                continue

            # 3. Two-tier block enrichment
            line_start = row.get("line_start")
            if line_start and str(line_start) != "-1":
                TOP_LEVEL_BLOCK_TYPES = {"resource", "data", "variable", "output", "locals", "module", "provider", "terraform"}
                details = None
                
                # Tier 1: Try StandaloneBlockFinder (Parity with TFReproducer's list_blocks approach)
                try:
                    from quality_metrics.block_finder import StandaloneBlockFinder
                    finder = StandaloneBlockFinder(row["absolute_filename"])
                    block = finder.find_with_upward_scan(int(line_start))
                    if block:
                        details = {
                            "block_type": block.get("block_type"),
                            "identifiers": block.get("identifiers") or block.get("address", ""),
                            "start_line": block.get("start_line"),
                            "end_line": block.get("end_line"),
                            "metrics": block.get("metrics", {})
                        }
                        # Add metrics to the row
                        metrics = details.get("metrics", {})
                        row["metrics_nloc"] = metrics.get("nloc", 0)
                        row["metrics_depth"] = metrics.get("depth", 0)
                        row["metrics_attributes"] = metrics.get("attribute_count", 0)
                        row["metrics_references"] = metrics.get("reference_count", 0)
                except Exception as e:
                    print(f"[DEBUG] StandaloneBlockFinder failed: {e}")

                # Tier 2: Fallback (Pure-Python Regex)
                if not details:
                    try:
                        file_lines = row["file_content"].splitlines()
                        details = _find_hcl_block(file_lines, int(line_start))
                    except: pass

                if details:
                    b_type = details.get("block_type", "")
                    idents = details.get("identifiers", "")
                    if isinstance(idents, list):
                        idents = " ".join(str(i) for i in idents)
                    
                    row["block_type"] = b_type
                    row["impacted_block_type"] = b_type
                    row["block_identifiers"] = idents
                    row["impacted_block_start_line"] = details.get("start_line")
                    row["impacted_block_end_line"] = details.get("end_line")
                    
                    # USE LINE SLICING LOGIC
                    DiagnosticsExtractor._add_block_content(row, details, tf_cache)

            # 4. Finalize block_type_full
            b_type = row.get("block_type", "").strip()
            idents = row.get("block_identifiers", "").strip()
            if idents:
                first_ident = idents.split()[0]
                row["block_type_full"] = f"{b_type} {first_ident}".strip()
            else:
                row["block_type_full"] = b_type

            # 5. Compute OIDs
            row["oid"] = DiagnosticsExtractor.compute_oid(row)
            row["specific_oid"] = DiagnosticsExtractor.compute_specific_oid(row)

            rows.append(row)

        return rows

    @staticmethod
    def compute_oid(r: dict) -> str:
        base = f"{r['filename']}|{r['line_start']}|{r['line_end']}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def compute_specific_oid(r: dict) -> str:
        def _normalize(text: str) -> str:
            return re.sub(r"\s+", " ", str(text).lower().strip())
        base = f"{r['filename']}|{r['line_start']}|{r['line_end']}|{_normalize(r['summary'])}|{_normalize(r['detail'])}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]
