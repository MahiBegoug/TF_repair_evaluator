"""
File Coordinate Resolver

Handles file path resolution and block coordinate lookups for the repair pipeline.
"""
import os
import pandas as pd


class FileCoordinateResolver:
    """Resolves file paths and block coordinates for repairs."""
    
    def __init__(self, clones_root="clones", problems_dataset=None):
        """
        Initialize file coordinate resolver.
        
        Args:
            clones_root: Root directory for cloned repositories
            problems_dataset: DataFrame with problem information (optional)
        """
        self.clones_root = clones_root
        self.problems = problems_dataset
        # Build a composite index keyed by (project_name, oid, filename) for O(1) lookup.
        # Falls back gracefully to an oid-only index when the extra columns are absent.
        self._coord_index = {}      # (project_name, oid, filename) -> (start, end)
        self._coord_index_oid = {}  # oid -> (start, end)  – fallback
        if problems_dataset is not None:
            required_cols = {"oid", "impacted_block_start_line", "impacted_block_end_line"}
            has_composite = required_cols | {"project_name", "filename"} <= set(problems_dataset.columns)
            for _, row in problems_dataset.iterrows():
                oid_key = str(row["oid"])
                coords = (int(row["impacted_block_start_line"]), int(row["impacted_block_end_line"]))
                # Full composite key
                if has_composite:
                    composite_key = (str(row["project_name"]), oid_key, str(row["filename"]))
                    self._coord_index[composite_key] = coords
                # OID-only fallback (first match wins)
                if oid_key not in self._coord_index_oid:
                    self._coord_index_oid[oid_key] = coords
    
    def extract_project_name(self, row):
        """
        Extract project name from row, either directly or from filename.
        
        Args:
            row: Pandas Series or dict with row data
            
        Returns:
            str: Project name or None
        """
        if "project_name" in row:
            return row["project_name"]
        
        # Assumption: filename starts with clones/<project_name>/...
        parts = row["filename"].split("/")
        if len(parts) > 1 and parts[0] == "clones":
            return parts[1]
        
        return None
    
    def get_original_file_path(self, filename):
        """
        Convert relative filename to absolute path.
        
        Args:
            filename: Relative filename (may start with "clones/")
            
        Returns:
            str: Absolute file path
        """
        relative_path = filename
        if relative_path.startswith("clones/"):
            relative_path = relative_path[len("clones/"):]
        
        return os.path.normpath(os.path.join(self.clones_root, relative_path))
    
    def get_block_coordinates_from_problems(self, oid, project_name=None, filename=None):
        """
        Get block coordinates from problems dataset.

        Lookup strategy (most precise → least precise):
          1. Composite key  (project_name, oid, filename) – fastest & unambiguous.
          2. OID-only fallback – used when project_name / filename are not available.

        Args:
            oid:          Object ID to look up.
            project_name: (optional) Project name for composite lookup.
            filename:     (optional) Relative filename for composite lookup.

        Returns:
            tuple: (start_line, end_line) or (None, None) if not found.
        """
        if self.problems is None or not oid:
            return None, None

        target_oid = str(oid)

        # --- 1. Composite lookup (project_name + oid + filename) ---
        if project_name and filename:
            composite_key = (str(project_name), target_oid, str(filename))
            if composite_key in self._coord_index:
                return self._coord_index[composite_key]
            print(f"Warning: No composite match for project='{project_name}', "
                  f"oid='{target_oid}', filename='{filename}'. Falling back to OID-only.")

        # --- 2. OID-only fallback ---
        if target_oid in self._coord_index_oid:
            return self._coord_index_oid[target_oid]

        print(f"Warning: No match found in problems dataset for OID: {target_oid}")
        return None, None
    
    def get_fix_content_and_coordinates(self, row, repair_mode="auto"):
        """
        Extract fix content and line coordinates based on repair mode.
        
        Args:
            row: Pandas Series or dict with fix data
            repair_mode: "file", "block", or "auto"
            
        Returns:
            tuple: (fixed_content, start_line, end_line)
        """
        fixed_content = None
        start_line = None
        end_line = None
        
        # Try full file fix first
        if "fixed_file" in row and pd.notna(row["fixed_file"]):
            if repair_mode == "file" or repair_mode == "auto":
                return row["fixed_file"], None, None
        
        # Otherwise, try block fix
        if repair_mode == "block" or repair_mode == "auto":
            fixed_content = row.get("fixed_block_content")
            if pd.isna(fixed_content):
                fixed_content = row.get("fixed_code")  # fallback
            
            # Get coordinates from problems dataset or fallback to row.
            # Pass project_name + filename alongside OID for the most precise lookup.
            if "oid" in row and pd.notna(row["oid"]):
                project_name = row.get("project_name") if "project_name" in row else None
                filename = row.get("filename") if "filename" in row else None
                start_line, end_line = self.get_block_coordinates_from_problems(
                    row["oid"],
                    project_name=project_name if project_name and pd.notna(project_name) else None,
                    filename=filename if filename and pd.notna(filename) else None,
                )
            
            # Fallback to row's own coordinates
            if start_line is None:
                start_line = int(row["line_start"]) if "line_start" in row and pd.notna(row["line_start"]) else None
            if end_line is None:
                end_line = int(row["line_end"]) if "line_end" in row and pd.notna(row["line_end"]) else None
        
        return fixed_content, start_line, end_line
