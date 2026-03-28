import os
import pandas as pd
from repair_pipeline.file_resolver import FileCoordinateResolver
from repair_pipeline.error_categorizer import ErrorCategorizer

# 1. Setup Resolver
resolver = FileCoordinateResolver(clones_root="clones")

# 2. Test Path with ../ prefix
path_with_prefix = "../TF_validation_reproducer/clones/alphagov__paas-cf/terraform/cloudfoundry/nat.tf"
row = {"filename": path_with_prefix}

project_name = resolver.extract_project_name(row)
print(f"Extracted Project: {project_name}")

if project_name == "alphagov__paas-cf":
    print("SUCCESS: Project name correctly extracted from relative path!")
else:
    print("FAILURE: Project name extraction failed.")

# 3. Test baseline matching with project name
problems_csv = "problems/problems.csv"
categorizer = ErrorCategorizer(clones_root="clones", problems_dataset=pd.read_csv(problems_csv))

# This is a REAL error from paas-cf buckets.tf
test_error = {
    'filename': '../TF_validation_reproducer/clones/alphagov__paas-cf/terraform/cloudfoundry/buckets.tf',
    'block_identifiers': 'aws_s3_bucket_lifecycle_configuration buildpacks-s3',
    'summary': 'Argument is deprecated',
    'detail': 'Use filter instead',
    'specific_oid': '37bef82e270b',
    'line_start': 1
}

# Normalize original_file to absolute form like the evaluator does
original_file = os.path.normpath(os.path.join(os.getcwd(), "clones/alphagov__paas-cf/terraform/cloudfoundry/buckets.tf"))

results = categorizer.categorize_errors([test_error], original_file, iteration_id="test", project=project_name)

res = results[0]
print(f"\nMatching Diagnostic for OID: {res.get('specific_oid')}")
print(f"IS_ORIGINAL_ERROR: {res.get('is_original_error')}")
print(f"INTRODUCED_IN_THIS_ITERATION: {res.get('introduced_in_this_iteration')}")

if res.get('is_original_error') == True and res.get('introduced_in_this_iteration') == False:
    print("\nFINAL SUCCESS: Robust baseline matching is now WORKING!")
else:
    print("\nFINAL FAILURE: Baseline matching failed.")
