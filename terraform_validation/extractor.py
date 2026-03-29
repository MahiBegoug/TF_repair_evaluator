import os
import hashlib
import re
from repair_pipeline.file_resolver import FileCoordinateResolver


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
            
            # Use robust normalization
            info["filename"] = FileCoordinateResolver.normalize_path(abs_fp)

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
                "working_directory": FileCoordinateResolver.normalize_path(module_path),
                "severity": diag.get("severity", ""),
                "summary": diag.get("summary", ""),
                "detail": diag.get("detail", ""),
                "address": diag.get("address", ""),
                "filename": "", "line_start": "", "col_start": "", "line_end": "", "col_end": "",
                "block_type": "", "block_type_full": "", "impacted_block_type": "", "impacted_block_content": "", "block_identifiers": "",
                "impacted_block_start_line": "", "impacted_block_end_line": "",
                "file_content": "", "file_loc": ""
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
                        }
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
    def normalize_for_oid(text: str) -> str:
        """
        Normalize text for consistent hashing.

        Important: This MUST match the baseline dataset's OID/specific_oid generation.
        The benchmark/baseline hashes keep quotes/backticks as part of the diagnostic
        message text. We lowercase + trim, and collapse all whitespace runs to a
        single space to avoid spurious mismatches from formatting/newlines.
        """
        import re
        if not text:
            return ""
        return re.sub(r"\s+", " ", str(text).lower().strip())

    @staticmethod
    def compute_oid(r: dict) -> str:
        """
        Location-based OID: groups all diagnostics at the same physical file
        location (filename, start line, end line).

        Note: This OID is used for "what terraform validate reported at a location"
        and is not guaranteed to match the benchmark problems dataset's OID scheme.
        """
        from repair_pipeline.file_resolver import FileCoordinateResolver
        filename = FileCoordinateResolver.normalize_path(r.get('filename', ''))
        line_start = str(r.get('line_start', '')).strip()
        line_end = str(r.get('line_end', '')).strip()

        base = f"{filename}|{line_start}|{line_end}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def compute_specific_oid(r: dict) -> str:
        """
        Specific OID: uniquely identifies the exact diagnostic
        by combining file location with the summary and detail text.
        Matches original benchmark logic.
        """
        import re
        from repair_pipeline.file_resolver import FileCoordinateResolver
        
        filename = FileCoordinateResolver.normalize_path(r.get('filename', ''))
        line_start = str(r.get('line_start', '')).strip()
        line_end = str(r.get('line_end', '')).strip()
        
        # Consistent normalization for all components
        summary = DiagnosticsExtractor.normalize_for_oid(r.get("summary", ""))
        detail = DiagnosticsExtractor.normalize_for_oid(r.get("detail", ""))
        
        base = f"{filename}|{line_start}|{line_end}|{summary}|{detail}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]
