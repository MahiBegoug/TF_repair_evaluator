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
    
    def get_block_coordinates_from_problems(self, oid):
        """
        Get block coordinates from problems dataset by OID.
        
        Args:
            oid: Object ID to look up
            
        Returns:
            tuple: (start_line, end_line) or (None, None) if not found
        """
        if self.problems is None or not oid:
            return None, None
        
        target_oid = str(oid)
        p_match = self.problems[self.problems["oid"].astype(str) == target_oid]
        
        if not p_match.empty:
            start = int(p_match.iloc[0]["impacted_block_start_line"])
            end = int(p_match.iloc[0]["impacted_block_end_line"])
            return start, end
        else:
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
            
            # Get coordinates from problems dataset or fallback to row
            if "oid" in row and pd.notna(row["oid"]):
                start_line, end_line = self.get_block_coordinates_from_problems(row["oid"])
            
            # Fallback to row's own coordinates
            if start_line is None:
                start_line = int(row["line_start"]) if "line_start" in row and pd.notna(row["line_start"]) else None
            if end_line is None:
                end_line = int(row["line_end"]) if "line_end" in row and pd.notna(row["line_end"]) else None
        
        return fixed_content, start_line, end_line
