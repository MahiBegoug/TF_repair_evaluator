import os

class DiagnosticsExtractor:

    @staticmethod
    def load_tf_files(module_path):
        cache = {}
        for root, dirs, files in os.walk(module_path):
            for fn in files:
                if fn.endswith(".tf"):
                    fp = os.path.join(root, fn)
                    try:
                        with open(fp, "r", encoding="utf-8") as f:
                            cache[fp] = f.read()
                    except Exception as e:
                        cache[fp] = f"[ERROR reading file: {e}]"
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
    def extract_rows(project_name, result, project_root):
        module_path = result["path"]
        rows = []

        try:
            working_dir = os.path.relpath(module_path, project_root).replace("\\", "/")
        except:
            working_dir = ""

        tf_cache = DiagnosticsExtractor.load_tf_files(module_path)
        diagnostics = DiagnosticsExtractor.normalize(result.get("diagnostics"))
        
        # Initialize StaticAnalyzer for the module
        try:
            from tf_dependency_analyzer.static.static_analyzer import StaticAnalyzer
            analyzer = StaticAnalyzer(module_path)
        except Exception as e:
            print(f"Warning: Failed to initialize StaticAnalyzer: {e}")
            analyzer = None

        for diag in diagnostics:

            drange = diag.get("range", {}) or {}
            start = drange.get("start", {}) or {}
            end = drange.get("end", {}) or {}
            filename_raw = drange.get("filename", "")
            
            line_start = start.get("line")
            
            row = {
                "project_name": project_name,
                "working_directory": working_dir,
                "severity": diag.get("severity", ""),
                "summary": diag.get("summary", ""),
                "detail": diag.get("detail", ""),
                "address": diag.get("address", ""), # Added address field
                "filename": "",
                "line_start": line_start,
                "col_start": start.get("column", ""),
                "line_end": end.get("line", ""),
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
                system_path = os.path.join(module_path, filename_raw)

                repo_clone_root = f"clones/{project_name}"
                relative_path = f"{working_dir}/{filename_raw}".lstrip("/")
                row["filename"] = f"{repo_clone_root}/{relative_path}".replace("\\", "/")

                row["file_content"] = tf_cache.get(system_path, "[FILE NOT FOUND]")
                
                # Attempt to identify block details
                if analyzer and line_start:
                    try:
                        # Use valid method get_block_details_by_location
                        details = analyzer.get_block_details_by_location(system_path, line_start)
                        
                        if details:
                            # Method typically returns a dict. Use safe get.
                            def get_val(obj, key):
                                if isinstance(obj, dict):
                                    return obj.get(key, "")
                                return getattr(obj, key, "")

                            b_type = get_val(details, "block_type")
                            identifiers = get_val(details, "identifiers")
                            
                            row["block_type"] = b_type
                            # Format must match problems dataset: "block_type identifiers"
                            row["block_identifiers"] = f"{b_type} {identifiers}".strip()
                            row["impacted_block_start_line"] = get_val(details, "start_line")
                            row["impacted_block_end_line"] = get_val(details, "end_line")
                            row["impacted_block_content"] = get_val(details, "content")
                    except Exception as e:
                        print(f"Failed to identify block at {filename_raw}:{line_start}: {e}")


            # Case 2: No file → include all TF files
            else:
                content = []
                for fp, c in tf_cache.items():
                    posix_fp = fp.replace("\\", "/")
                    # content.append(f"\n##### FILE: {posix_fp}\n{c}")
                    content.append(f"{c}")
                row["file_content"] = "\n".join(content)

            rows.append(row)

        return rows
