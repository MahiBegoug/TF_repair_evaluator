import os
from tf_dependency_analyzer.static.static_analyzer import StaticAnalyzer


class StandaloneBlockFinder:
    """
    A standalone class to identify a Terraform block containing a specific line
    using direct range detection.
    """

    def __init__(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        self.file_path = file_path
        self.directory = os.path.dirname(file_path)
        # Initialize the static analyzer for the directory
        self.analyzer = StaticAnalyzer(self.directory)
        # Pre-fetch all blocks for this file
        self.blocks = self.analyzer.list_blocks(self.file_path, include_metrics=True)

    def find_block_at_line(self, line_number):
        """
        Finds the most specific block (smallest range) that contains the given line.
        """
        matches = []
        for b in self.blocks:
            if b['start_line'] <= line_number <= b['end_line']:
                matches.append(b)

        if not matches:
            return None

        # If multiple blocks contain the line (e.g. parent/child), 
        # return the one with the largest range (the wrapper / parent block).
        return max(matches, key=lambda x: x['end_line'] - x['start_line'])

    def find_with_upward_scan(self, line_number, limit=50):
        """
        Scans upward from the given line until a block is found.
        Useful when a diagnostic points to an attribute inside a block.
        """
        for l in range(line_number, max(0, line_number - limit) - 1, -1):
            block = self.find_block_at_line(l)
            if block:
                return block
        return None
