# Manual Inspection Case 2: `b6afb35dd38f`

## Why this case

- selected because the project has a very small benchmark baseline, which makes before/after inspection manageable
- selected only from cases where `module_fix_introduced_errors > 0`

## Benchmark problem

- project: `databrickslabs__overwatch`
- file: `clones/databrickslabs__overwatch/terraform/modules/azure-workspace-diag/diagnostic.tf`
- summary: `Unsupported block type`
- detail: `Blocks of type "log" are not expected here.`
- provider: `azurerm`
- block_type: `resource`
- file_loc: `18`
- metrics_depth: `15`
- project_problem_count in benchmark: `1`

## Baseline diagnostics for this project in the benchmark

| specific_oid   | filename                                                                              | summary                | detail                                      |   line_start | block_type   | block_identifiers                            |
|:---------------|:--------------------------------------------------------------------------------------|:-----------------------|:--------------------------------------------|-------------:|:-------------|:---------------------------------------------|
| b6afb35dd38f   | clones/databrickslabs__overwatch/terraform/modules/azure-workspace-diag/diagnostic.tf | Unsupported block type | Blocks of type "log" are not expected here. |           15 | resource     | azurerm_monitor_diagnostic_setting overwatch |

## Runs selected for inspection

| model                              |   iteration |   module_fix_introduced_errors |   block_fix_introduced_errors | line_specific_error_fixed   | line_is_clean   |
|:-----------------------------------|------------:|-------------------------------:|------------------------------:|:----------------------------|:----------------|
| CodeLlama_34b_Instruct_hf [docs]   |           1 |                              1 |                             1 | True                        | True            |
| Codestral_22B_v0.1 [docs]          |           1 |                              1 |                             1 | True                        | True            |
| Codestral_22B_v0.1                 |           3 |                              1 |                             1 | False                       | False           |
| deepseek_coder_33b_instruct [docs] |           1 |                              1 |                             1 | True                        | True            |
| deepseek_coder_33b_instruct        |           2 |                              1 |                             0 | True                        | True            |
| gpt_oss_20b [docs]                 |           1 |                              1 |                             1 | True                        | True            |
| gpt_oss_20b                        |           2 |                              3 |                             3 | True                        | True            |

## CodeLlama_34b_Instruct_hf [docs]

- iteration: `1`
- module_fix_introduced_errors: `1`
- block_fix_introduced_errors: `1`
- line_specific_error_fixed: `True`
- line_is_clean: `True`

### Fixed block content
```hcl

resource "azurerm_monitor_diagnostic_setting" "overwatch" {
  name               = "overwatch"
  target_resource_id = data.azurerm_databricks_workspace.example.id
  eventhub_authorization_rule_id = data.azurerm_eventhub_namespace_authorization_rule.overwatch.id
  eventhub_name = var.evhub_name

  dynamic "enabled_log" {
    for_each = var.enabled_log_types
    content {
      category = enabled_log.value
      enabled = true
    }
  }
  
}
```

### Raw LLM output
```
  <fixed_block_content><![CDATA[
resource "azurerm_monitor_diagnostic_setting" "overwatch" {
  name               = "overwatch"
  target_resource_id = data.azurerm_databricks_workspace.example.id
  eventhub_authorization_rule_id = data.azurerm_eventhub_namespace_authorization_rule.overwatch.id
  eventhub_name = var.evhub_name

  dynamic "enabled_log" {
    for_each = var.enabled_log_types
    content {
      category = enabled_log.value
      enabled = true
    }
  }
  
}
]]></fixed_block_content>
```

### Introduced diagnostics after validation
| severity   | summary              | detail                                            | filename                                                                              |   line_start | block_type   | block_identifiers                            |
|:-----------|:---------------------|:--------------------------------------------------|:--------------------------------------------------------------------------------------|-------------:|:-------------|:---------------------------------------------|
| error      | Unsupported argument | An argument named "enabled" is not expected here. | clones/databrickslabs__overwatch/terraform/modules/azure-workspace-diag/diagnostic.tf |           19 | resource     | azurerm_monitor_diagnostic_setting overwatch |

### Remaining baseline diagnostics after validation
_none_

## Codestral_22B_v0.1 [docs]

- iteration: `1`
- module_fix_introduced_errors: `1`
- block_fix_introduced_errors: `1`
- line_specific_error_fixed: `True`
- line_is_clean: `True`

### Fixed block content
```hcl

resource "azurerm_monitor_diagnostic_setting" "overwatch" {
  name               = "overwatch"
  target_resource_id = data.azurerm_databricks_workspace.example.id
  eventhub_authorization_rule_id = data.azurerm_eventhub_namespace_authorization_rule.overwatch.id
  eventhub_name = var.evhub_name

  dynamic "enabled_log" {
    for_each = var.enabled_log_types
    content {
      category = enabled_log.value
      enabled = true
    }
  }
}
```

### Raw LLM output
```
 <fixed_block_content><![CDATA[
resource "azurerm_monitor_diagnostic_setting" "overwatch" {
  name               = "overwatch"
  target_resource_id = data.azurerm_databricks_workspace.example.id
  eventhub_authorization_rule_id = data.azurerm_eventhub_namespace_authorization_rule.overwatch.id
  eventhub_name = var.evhub_name

  dynamic "enabled_log" {
    for_each = var.enabled_log_types
    content {
      category = enabled_log.value
      enabled = true
    }
  }
}
]]></fixed_block_content>
```

### Introduced diagnostics after validation
| severity   | summary              | detail                                            | filename                                                                              |   line_start | block_type   | block_identifiers                            |
|:-----------|:---------------------|:--------------------------------------------------|:--------------------------------------------------------------------------------------|-------------:|:-------------|:---------------------------------------------|
| error      | Unsupported argument | An argument named "enabled" is not expected here. | clones/databrickslabs__overwatch/terraform/modules/azure-workspace-diag/diagnostic.tf |           19 | resource     | azurerm_monitor_diagnostic_setting overwatch |

### Remaining baseline diagnostics after validation
_none_

## Codestral_22B_v0.1

- iteration: `3`
- module_fix_introduced_errors: `1`
- block_fix_introduced_errors: `1`
- line_specific_error_fixed: `False`
- line_is_clean: `False`

### Fixed block content
```hcl

resource "azurerm_monitor_diagnostic_setting" "overwatch" {
  name               = "overwatch"
  target_resource_id = data.azurerm_databricks_workspace.example.id
  eventhub_authorization_rule_id = data.azurerm_eventhub_namespace_authorization_rule.overwatch.id
  eventhub_name = var.evhub_name

  dynamic "log" {
    for_each = var.enabled_log_categories
    content {
      category = log.value
      enabled  = true

      retention_policy {
        enabled = false
      }
    }
  }
}
```

### Raw LLM output
```
 <fixed_block_content><![CDATA[
resource "azurerm_monitor_diagnostic_setting" "overwatch" {
  name               = "overwatch"
  target_resource_id = data.azurerm_databricks_workspace.example.id
  eventhub_authorization_rule_id = data.azurerm_eventhub_namespace_authorization_rule.overwatch.id
  eventhub_name = var.evhub_name

  dynamic "log" {
    for_each = var.enabled_log_categories
    content {
      category = log.value
      enabled  = true

      retention_policy {
        enabled = false
      }
    }
  }
}
]]></fixed_block_content>
```

### Introduced diagnostics after validation
| severity   | summary                                | detail                                                                                                                                                           | filename                                                                              |   line_start | block_type   | block_identifiers                            |
|:-----------|:---------------------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------------------------------------------------------------------------------------|-------------:|:-------------|:---------------------------------------------|
| error      | Reference to undeclared input variable | An input variable with the name "enabled_log_categories" has not been declared. This variable can be declared with a variable "enabled_log_categories" {} block. | clones/databrickslabs__overwatch/terraform/modules/azure-workspace-diag/diagnostic.tf |           16 | resource     | azurerm_monitor_diagnostic_setting overwatch |

### Remaining baseline diagnostics after validation
| severity   | summary                | detail                                      | filename                                                                              |   line_start | block_type   | block_identifiers                            |
|:-----------|:-----------------------|:--------------------------------------------|:--------------------------------------------------------------------------------------|-------------:|:-------------|:---------------------------------------------|
| error      | Unsupported block type | Blocks of type "log" are not expected here. | clones/databrickslabs__overwatch/terraform/modules/azure-workspace-diag/diagnostic.tf |           15 | resource     | azurerm_monitor_diagnostic_setting overwatch |

## deepseek_coder_33b_instruct [docs]

- iteration: `1`
- module_fix_introduced_errors: `1`
- block_fix_introduced_errors: `1`
- line_specific_error_fixed: `True`
- line_is_clean: `True`

### Fixed block content
```hcl
resource "azurerm_monitor_diagnostic_setting" "overwatch" {
  name               = "overwatch"
  target_resource_id = data.azurerm_databricks_workspace.example.id
  eventhub_authorization_rule_id = data.azurerm_eventhub_namespace_authorization_rule.overwatch.id
  eventhub_name = var.evhub_name

  dynamic "enabled_log" {
    for_each = var.enabled_log_types
    content {
      category = enabled_log.value
      enabled = true
    }
  }
  
}
```

### Raw LLM output
```
The problematic block contains a nested block of type "log" which is not expected in the "azurerm_monitor_diagnostic_setting" resource. The resource expects nested blocks of type "enabled_log" and "metric".

The corrected version of the block is as follows:

```hcl
resource "azurerm_monitor_diagnostic_setting" "overwatch" {
  name               = "overwatch"
  target_resource_id = data.azurerm_databricks_workspace.example.id
  eventhub_authorization_rule_id = data.azurerm_eventhub_namespace_authorization_rule.overwatch.id
  eventhub_name = var.evhub_name

  dynamic "enabled_log" {
    for_each = var.enabled_log_types
    content {
      category = enabled_log.value
      enabled = true
    }
  }
  
}
```

Please note that the diagnostic indicates an error with the block type "log". However, the corrected version uses the correct block type "enabled_log" to achieve the desired functionality.
```

### Introduced diagnostics after validation
| severity   | summary              | detail                                            | filename                                                                              |   line_start | block_type   | block_identifiers                            |
|:-----------|:---------------------|:--------------------------------------------------|:--------------------------------------------------------------------------------------|-------------:|:-------------|:---------------------------------------------|
| error      | Unsupported argument | An argument named "enabled" is not expected here. | clones/databrickslabs__overwatch/terraform/modules/azure-workspace-diag/diagnostic.tf |           19 | resource     | azurerm_monitor_diagnostic_setting overwatch |

### Remaining baseline diagnostics after validation
_none_

## deepseek_coder_33b_instruct

- iteration: `2`
- module_fix_introduced_errors: `1`
- block_fix_introduced_errors: `0`
- line_specific_error_fixed: `True`
- line_is_clean: `True`

### Fixed block content
```hcl

resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  tags = {
    Name = "main-vpc"
  }
}
```

### Raw LLM output
```
The diagnostic information suggests that the block type "log" is not expected in the provided Terraform configuration block. According to the AWS documentation, the "log" block is used for configuring CloudWatch log options, which is not relevant to the AWS VPC resource.

Instead, AWS VPC resource requires a "tags" block. Here is the corrected version of the block:

<fixed_block_content><![CDATA[
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  tags = {
    Name = "main-vpc"
  }
}
]]></fixed_block_content>

Please replace "tag" with "tags" in the block.
```

### Introduced diagnostics after validation
| severity   | summary                   | detail                                                                                                                                                               | filename                                                                                                        |   line_start |   block_type |   block_identifiers |
|:-----------|:--------------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------|:----------------------------------------------------------------------------------------------------------------|-------------:|-------------:|--------------------:|
| error      | Missing required provider | This configuration requires provider registry.terraform.io/hashicorp/aws, but that provider isn't available. You may be able to install it automatically by running: | ../TF_validation_reproducer/clones/databrickslabs__overwatch/terraform/modules/azure-workspace-diag/clusters.tf |           -1 |          nan |                 nan |
|            |                           |   terraform init                                                                                                                                                     |                                                                                                                 |              |              |                     |

### Remaining baseline diagnostics after validation
_none_

## gpt_oss_20b [docs]

- iteration: `1`
- module_fix_introduced_errors: `1`
- block_fix_introduced_errors: `1`
- line_specific_error_fixed: `True`
- line_is_clean: `True`

### Fixed block content
```hcl

resource "azurerm_monitor_diagnostic_setting" "overwatch" {
  name               = "overwatch"
  target_resource_id = data.azurerm_databricks_workspace.example.id
  eventhub_authorization_rule_id = data.azurerm_eventhub_namespace_authorization_rule.overwatch.id
  eventhub_name = var.evhub_name

  dynamic "enabled_log" {
    for_each = var.enabled_log_types
    content {
      category = enabled_log.value
      enabled = true
    }
  }
  
}
```

### Raw LLM output
```
<fixed_block_content><![CDATA[
resource "azurerm_monitor_diagnostic_setting" "overwatch" {
  name               = "overwatch"
  target_resource_id = data.azurerm_databricks_workspace.example.id
  eventhub_authorization_rule_id = data.azurerm_eventhub_namespace_authorization_rule.overwatch.id
  eventhub_name = var.evhub_name

  dynamic "enabled_log" {
    for_each = var.enabled_log_types
    content {
      category = enabled_log.value
      enabled = true
    }
  }
  
}
]]></fixed_block_content>
```

### Introduced diagnostics after validation
| severity   | summary              | detail                                            | filename                                                                              |   line_start | block_type   | block_identifiers                            |
|:-----------|:---------------------|:--------------------------------------------------|:--------------------------------------------------------------------------------------|-------------:|:-------------|:---------------------------------------------|
| error      | Unsupported argument | An argument named "enabled" is not expected here. | clones/databrickslabs__overwatch/terraform/modules/azure-workspace-diag/diagnostic.tf |           19 | resource     | azurerm_monitor_diagnostic_setting overwatch |

### Remaining baseline diagnostics after validation
_none_

## gpt_oss_20b

- iteration: `2`
- module_fix_introduced_errors: `3`
- block_fix_introduced_errors: `3`
- line_specific_error_fixed: `True`
- line_is_clean: `True`

### Fixed block content
```hcl

resource "azurerm_monitor_diagnostic_setting" "overwatch" {
  name               = "overwatch"
  target_resource_id = data.azurerm_databricks_workspace.example.id
  eventhub_authorization_rule_id = data.azurerm_eventhub_namespace_authorization_rule.overwatch.id
  eventhub_name = var.evhub_name

}
```

### Raw LLM output
```
<fixed_block_content><![CDATA[
resource "azurerm_monitor_diagnostic_setting" "overwatch" {
  name               = "overwatch"
  target_resource_id = data.azurerm_databricks_workspace.example.id
  eventhub_authorization_rule_id = data.azurerm_eventhub_namespace_authorization_rule.overwatch.id
  eventhub_name = var.evhub_name

}
]]></fixed_block_content>
```

### Introduced diagnostics after validation
| severity   | summary                   | detail                                                                         | filename                                                                              |   line_start | block_type   | block_identifiers                            |
|:-----------|:--------------------------|:-------------------------------------------------------------------------------|:--------------------------------------------------------------------------------------|-------------:|:-------------|:---------------------------------------------|
| error      | Missing required argument | "enabled_log": one of `enabled_log,enabled_metric,metric` must be specified    | clones/databrickslabs__overwatch/terraform/modules/azure-workspace-diag/diagnostic.tf |            9 | resource     | azurerm_monitor_diagnostic_setting overwatch |
| error      | Missing required argument | "enabled_metric": one of `enabled_log,enabled_metric,metric` must be specified | clones/databrickslabs__overwatch/terraform/modules/azure-workspace-diag/diagnostic.tf |            9 | resource     | azurerm_monitor_diagnostic_setting overwatch |
| error      | Missing required argument | "metric": one of `enabled_log,enabled_metric,metric` must be specified         | clones/databrickslabs__overwatch/terraform/modules/azure-workspace-diag/diagnostic.tf |            9 | resource     | azurerm_monitor_diagnostic_setting overwatch |

### Remaining baseline diagnostics after validation
_none_
