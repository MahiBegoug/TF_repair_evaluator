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

        for diag in diagnostics:

            drange = diag.get("range", {}) or {}
            start = drange.get("start", {}) or {}
            end = drange.get("end", {}) or {}
            filename_raw = drange.get("filename", "")

            row = {
                "project_name": project_name,
                "working_directory": working_dir,
                "severity": diag.get("severity", ""),
                "summary": diag.get("summary", ""),
                "detail": diag.get("detail", ""),
                "filename": "",
                "line_start": start.get("line", ""),
                "col_start": start.get("column", ""),
                "line_end": end.get("line", ""),
                "col_end": end.get("column", ""),
                "file_content": "",
            }

            # Case 1: Specific file
            if filename_raw:
                system_path = os.path.join(module_path, filename_raw)

                repo_clone_root = f"clones/{project_name}"
                relative_path = f"{working_dir}/{filename_raw}".lstrip("/")
                row["filename"] = f"{repo_clone_root}/{relative_path}".replace("\\", "/")

                row["file_content"] = tf_cache.get(system_path, "[FILE NOT FOUND]")

            # Case 2: No file → include all TF files
            else:
                content = []
                for fp, c in tf_cache.items():
                    posix_fp = fp.replace("\\", "/")
                    content.append(f"\n##### FILE: {posix_fp}\n{c}")
                row["file_content"] = "\n".join(content)

            rows.append(row)

        return rows
