# or via DependencyExtractor: extractor.analyzer.get_block_details_by_location(...)
import json

from tf_dependency_analyzer.static.static_analyzer import StaticAnalyzer

analyzer = StaticAnalyzer(".")

# Find block details for a specific line (e.g., error location)
details = analyzer.get_block_details_by_location(
    file_path="./main.tf",
    start_line=1
)

if __name__ == '__main__':
    print(details)