import os
import pandas as pd
from repair_pipeline.error_categorizer import ErrorCategorizer

# Mock data
clones_root = "clones"
problems_csv = "problems/problems.csv"

# 1. Initialize Categorizer
categorizer = ErrorCategorizer(clones_root=clones_root, problems_dataset=pd.read_csv(problems_csv))

# 2. Test project: alphagov__paas-cf
# OID from baseline: 77d14c70e421
# Specific OID from baseline: 37bef82e270b
# Filename: clones/alphagov__paas-cf/terraform/cloudfoundry/buckets.tf

test_error = {
    'filename': 'clones/alphagov__paas-cf/terraform/cloudfoundry/buckets.tf',
    'block_identifiers': 'aws_s3_bucket_lifecycle_configuration buildpacks-s3',
    'summary': 'Argument is deprecated ', # Note the trailing space
    'detail': 'Use filter instead\n',      # Note the newline
    'specific_oid': '37bef82e270b',
    'line_start': 10
}

print(f"Testing categorization for specific_oid: {test_error['specific_oid']}")

# Invoke categorization
results = categorizer.categorize_errors([test_error], test_error['filename'], iteration_id="test", project="alphagov__paas-cf")

res = results[0]
print(f"IS_ORIGINAL_ERROR: {res.get('is_original_error')}")
print(f"INTRODUCED_IN_THIS_ITERATION: {res.get('introduced_in_this_iteration')}")

if res.get('is_original_error') == True and res.get('introduced_in_this_iteration') == False:
    print("\nSUCCESS: Baseline error correctly identified despite formatting differences!")
else:
    print("\nFAILURE: Baseline error misclassified.")
