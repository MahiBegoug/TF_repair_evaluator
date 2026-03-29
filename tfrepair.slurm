#!/bin/bash
# Usage:
#   sbatch tfrepair.slurm
#   sbatch tfrepair.slurm repair_config.json
#
# Logs:
#   slurm-<jobid>.out / slurm-<jobid>.err in the submit directory.

#SBATCH --job-name=tfrepair
#SBATCH --cpus-per-task=12
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH -o slurm-%j.out
#SBATCH -e slurm-%j.err

set -euo pipefail

CONFIG_PATH="${1:-repair_config.json}"

cd "${SLURM_SUBMIT_DIR:-$PWD}"
export PYTHONUNBUFFERED=1

echo "[SLURM] job_id=${SLURM_JOB_ID:-N/A}"
echo "[SLURM] host=$(hostname)"
echo "[SLURM] pwd=$PWD"
echo "[SLURM] start=$(date -Is)"
echo "[SLURM] config=${CONFIG_PATH}"

# Optional: activate local venv if present.
if [[ -f "venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "venv/bin/activate"
fi

python3 run_repair_pipeline.py --config "${CONFIG_PATH}"

echo "[SLURM] end=$(date -Is)"

