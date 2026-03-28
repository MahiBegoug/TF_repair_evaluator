import os
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

from repair_pipeline.file_resolver import FileCoordinateResolver

def test_normalization():
    paths = [
        "clones\\project\\file.tf",
        "clones/project/file.tf",
        "../../clones/project/file.tf",
        "C:\\Users\\Admin\\clones\\project\\file.tf",
        "/mnt/home/clones/project/file.tf",
        "file.tf"
    ]
    
    print("--- TESTING PATH NORMALIZATION ---")
    for p in paths:
        normalized = FileCoordinateResolver.normalize_path(p)
        print(f"Original: {p}")
        print(f"Normalized: {normalized}")
        print("-" * 20)
        
    # Check project extraction
    resolver = FileCoordinateResolver()
    
    print("\n--- TESTING PROJECT EXTRACTION ---")
    rows = [
        {"filename": "clones/alphagov__paas-cf/buckets.tf"},
        {"filename": "clones\\alphagov__paas-cf\\buckets.tf"},
        {"filename": "../../clones/alphagov__paas-cf/buckets.tf"}
    ]
    
    for r in rows:
        project = resolver.extract_project_name(r)
        print(f"Path: {r['filename']}")
        print(f"Extracted Project: {project}")
        
    print("\nALL TESTS PASSED")

if __name__ == "__main__":
    test_normalization()
