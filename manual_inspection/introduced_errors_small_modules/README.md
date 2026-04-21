# Introduced Error Manual Inspection

These files are intended for manual validation of `introduced_in_this_iteration` and `module_fix_introduced_errors`.

Selection criteria:
- only cases with `module_fix_introduced_errors > 0`
- preference for projects with very small benchmark baselines
- one markdown file per selected `specific_oid`

Each file contains:
- the benchmark baseline diagnostics for the project
- one representative introduced-error run per model/variant when available
- the candidate patch
- the raw LLM output
- the introduced diagnostics after validation
- the remaining baseline diagnostics after validation

## Index

| specific_oid   | project_name                    | filename                                                                                              |   project_problem_count | output_file                                       |
|:---------------|:--------------------------------|:------------------------------------------------------------------------------------------------------|------------------------:|:--------------------------------------------------|
| e064de81f5a8   | ministryofjustice__opg-digideps | clones/ministryofjustice__opg-digideps/terraform/environment/region/modules/s3_bucket/data_sources.tf |                       1 | 01_e064de81f5a8_ministryofjustice_opg-digideps.md |
| b6afb35dd38f   | databrickslabs__overwatch       | clones/databrickslabs__overwatch/terraform/modules/azure-workspace-diag/diagnostic.tf                 |                       1 | 02_b6afb35dd38f_databrickslabs_overwatch.md       |
| ca09187e68fc   | dirien__quick-bites             | clones/dirien__quick-bites/goreleaser-blob/infrastructure/blob.tf                                     |                       1 | 03_ca09187e68fc_dirien_quick-bites.md             |
| 743c58e0c299   | weaveworks__build-tools         | clones/weaveworks__build-tools/provisioning/gcp/main.tf                                               |                       1 | 04_743c58e0c299_weaveworks_build-tools.md         |
