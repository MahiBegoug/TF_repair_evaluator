#!/bin/bash
# Usage:
#   sbatch tfrepair.slurm
#   sbatch tfrepair.slurm repair_config.json
#
# Logs:
#   slurm-<jobid>.out / slurm-<jobid>.err in the submit directory.

#SBATCH --job-name=tfrepair
#SBATCH --cpus-per-task=64
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH -o slurm-%j.out
#SBATCH -e slurm-%j.err

set -euo pipefail

# IMPORTANT:
# On many clusters, SLURM copies the batch script to something like:
#   /var/spool/slurmd/job<id>/slurm_script
# before executing it. In that case, using BASH_SOURCE[0] to locate the repo
# root will point at the spool directory, not your repository.
#
# The most reliable "repo root" is the directory you submitted from.
SUBMIT_DIR="${SLURM_SUBMIT_DIR:-$PWD}"
cd "${SUBMIT_DIR}"
REPO_DIR="$PWD"

# Resolve config path:
# - If arg is absolute, use it.
# - If relative, resolve from SUBMIT_DIR (the directory you submitted the job from).
CONFIG_ARG="${1:-repair_config.json}"
if [[ "${CONFIG_ARG}" = /* ]]; then
  CONFIG_PATH="${CONFIG_ARG}"
elif [[ -f "${SUBMIT_DIR}/${CONFIG_ARG}" ]]; then
  CONFIG_PATH="${SUBMIT_DIR}/${CONFIG_ARG}"
else
  echo "[SLURM] error: config not found: ${CONFIG_ARG}" >&2
  echo "[SLURM] looked in: ${SUBMIT_DIR}/${CONFIG_ARG}" >&2
  exit 2
fi

# We are already running from the repo root (SUBMIT_DIR), so relative paths are stable.
export PYTHONUNBUFFERED=1

echo "[SLURM] job_id=${SLURM_JOB_ID:-N/A}"
echo "[SLURM] host=$(hostname)"
echo "[SLURM] submit_dir=${SUBMIT_DIR}"
echo "[SLURM] repo_dir=${REPO_DIR}"
echo "[SLURM] pwd=$PWD"
echo "[SLURM] start=$(date -Is)"
echo "[SLURM] config=${CONFIG_PATH}"

# Optional: activate local venv if present.
if [[ -f "venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "venv/bin/activate"
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "[SLURM] error: python not found (tried python3 then python)" >&2
  exit 3
fi

if [[ ! -f "run_repair_pipeline.py" ]]; then
  echo "[SLURM] error: run_repair_pipeline.py not found in repo_dir=${REPO_DIR}" >&2
  exit 4
fi

echo "[SLURM] python=$(${PYTHON_BIN} --version 2>&1 | head -n 1)"
echo "[SLURM] cmd: ${PYTHON_BIN} run_repair_pipeline.py --config ${CONFIG_PATH}"
${PYTHON_BIN} run_repair_pipeline.py --config "${CONFIG_PATH}"

echo "[SLURM] end=$(date -Is)"
