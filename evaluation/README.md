# Pass@k Evaluation

This directory contains scripts to evaluate the performance of LLM repairs using the **pass@k** metric.

## How it Works

**pass@k** measures the probability that *at least one* out of $k$ generated samples is correct (or in our case, a "plausible fix" that passes `terraform validate`).

Instead of just checking if the "best" sample works, we generate $n$ samples for each problem and estimate the probability that a user would find a working solution within their first $k$ attempts.

We use the **unbiased estimator** proposed by [Chen et al. (2021)](https://arxiv.org/abs/2107.03374):

```
pass@k = 1 - E [ combination(n-c, k) / combination(n, k) ]
```

Where:
- `n`: Total number of samples generated per problem.
- `c`: Number of plausible fixes found among the `n` samples.
- `k`: The budget of attempts (e.g., k=1, 5, 10).

### Synthetic Data Format

The evaluation uses two CSV files:

1.  **Problems CSV** (`problems.csv`): Defines the problems to be evaluated.
    - `oid`: Unique identifier for the problem.
    - `filename`: The file being repaired.

2.  **Fixes CSV** (`<model>_fixes.csv`): Contains the repair outcomes for a specific model.
    - `oid`: Unique identifier for the problem (must match `problems.csv`).
    - `iteration_id`: The attempt number.
    - `plausible_fix`: Boolean indicating if the fix was syntactically valid.

### Usage

### 1. Generate Synthetic Data (Testing)
To test the metric, you can generate synthetic data:

```bash
python evaluation/generate_synthetic_outcomes.py
```
This creates `evaluation/data/problems.csv` and separate fix files like `evaluation/data/gemini_synthetic_fixes.csv`.

### 2. Calculate pass@k
Run the calculation script specifying the problems file and the fixes file for a specific model:

```bash
python evaluation/calculate_pass_at_k.py --problems-csv evaluation/data/problems.csv --fixes-csv evaluation/data/gemini_synthetic_fixes.csv --k-values 1 5 10
```

### Example Output

```text
      LLM  pass@1    pass@5   pass@10
0  gemini   0.770  0.999678  1.000000
```

- **pass@10**: Probability that at least one correct solution is found within 10 attempts.

### 3. Evaluate Real LLM Fixes (End-to-End)

To evaluate all LLM fixes located in the `llms_fixes_results` directory, you can use the `evaluate_all_models.py` script.

#### Configuration

The evaluation is controlled by `evaluation_config.json`. You can modify this file to change directories or `k` values:

```json
{
    "fixes_dir": "llms_fixes_results",
    "output_dir": "evaluation/data",
    "clones_dir": "../TFReproducer/clones",
    "k_values": [1, 5, 10],
    "models": ["gemini", "chatgpt4.1"],
    "generate_synthetic_data": false,
    "data_type": "all"
}
```

- **models**: List of model names to evaluate (substring match). Leave empty `[]` to evaluate all.
- **generate_synthetic_data**: If `true`, generates synthetic data into `fixes_dir` before evaluation.
- **data_type**: Filter for input files:
    - `"all"`: Process all CSVs.
    - `"synthetic"`: Process only files with "synthetic" in the name.
    - `"real"`: Process only files WITHOUT "synthetic" in the name.

#### Running the Evaluation

Simply run the script:

```bash
python evaluate_all_models.py
```

This script will:
1.  Read settings from `evaluation_config.json`.
2.  Iterate through each CSV file in `fixes_dir`.
3.  Run `main.py` to apply fixes and validate them (if outcomes are not pre-computed).
4.  Generate outcome files in `output_dir`.
5.  Calculate `pass@k` metrics for each model and save them to `output_dir`.
6.  Save an aggregated summary to `output_dir/summary_pass_at_k.csv`.
