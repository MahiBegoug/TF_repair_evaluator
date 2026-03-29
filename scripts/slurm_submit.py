import argparse
import datetime as _dt
import json
import os
import shlex
import shutil
import subprocess
import sys


def _q(s: str) -> str:
    return shlex.quote(str(s))


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _infer_job_name(config: dict) -> str:
    slurm_cfg = config.get("slurm") or {}
    if slurm_cfg.get("job_name"):
        return str(slurm_cfg["job_name"])

    # Prefer a stable, informative name from the selected model(s) if present.
    models = (config.get("responses") or {}).get("models") or []
    if isinstance(models, list) and len(models) == 1:
        base = os.path.basename(str(models[0]))
        base = base.replace(".csv", "")
        return f"tfrepair_{base}"
    return "tfrepair"


def _build_sbatch_script(
    *,
    config_path: str,
    workdir: str | None,
    job_name: str,
    log_dir: str,
    python_bin: str,
    clear_existing: bool,
    debug_matching: bool,
    slurm: dict,
) -> str:
    """
    Create an sbatch script that runs:
      python run_repair_pipeline.py --config <config_path> [--clear-existing] [--debug-matching]
    """
    lines: list[str] = ["#!/bin/bash", "set -euo pipefail", ""]

    # SBATCH directives
    # Slurm runs on Linux; ensure paths in SBATCH directives use forward slashes
    # even if the submit helper is run on Windows.
    log_dir_posix = str(log_dir).replace("\\", "/")

    lines.append(f"#SBATCH --job-name={job_name}")
    lines.append(f"#SBATCH --output={_q('/'.join([log_dir_posix.rstrip('/'), '%x-%j.out']))}")
    lines.append(f"#SBATCH --error={_q('/'.join([log_dir_posix.rstrip('/'), '%x-%j.err']))}")

    # Optional resource directives
    # Use config-specified values if present; otherwise rely on cluster defaults.
    for key, flag in [
        ("partition", "--partition"),
        ("account", "--account"),
        ("qos", "--qos"),
        ("constraint", "--constraint"),
        ("time", "--time"),
        ("mem", "--mem"),
        ("nodes", "--nodes"),
        ("ntasks", "--ntasks"),
        ("cpus_per_task", "--cpus-per-task"),
        ("gpus", "--gpus"),
    ]:
        val = slurm.get(key)
        if val is None or val == "" or val is False:
            continue
        lines.append(f"#SBATCH {flag}={val}")

    lines.extend(["", "echo \"[SLURM] job_id=${SLURM_JOB_ID:-N/A}\"", "echo \"[SLURM] host=$(hostname)\""])
    lines.append("echo \"[SLURM] start=$(date -Is)\"")
    lines.append("")

    # Working directory: default to submit dir to make relative paths work.
    if workdir:
        lines.append(f"cd {_q(workdir)}")
    else:
        lines.append("cd \"${SLURM_SUBMIT_DIR:-$PWD}\"")
    lines.append("")

    # Make python output unbuffered so logs are live in .out/.err
    lines.append("export PYTHONUNBUFFERED=1")
    lines.append("")

    cmd = [python_bin, "run_repair_pipeline.py", "--config", config_path]
    if clear_existing:
        cmd.append("--clear-existing")
    if debug_matching:
        cmd.append("--debug-matching")

    lines.append("echo \"[SLURM] cmd: " + " ".join(_q(c) for c in cmd) + "\"")
    lines.append(" ".join(_q(c) for c in cmd))
    lines.append("")
    lines.append("echo \"[SLURM] end=$(date -Is)\"")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate and submit a Slurm sbatch job for TFRepair.")
    ap.add_argument("--config", default="repair_config.json", help="Path to repair_config.json")
    ap.add_argument("--workdir", default=None, help="Working directory for the job (default: SLURM_SUBMIT_DIR)")
    ap.add_argument("--job-name", default=None, help="Override Slurm job name")
    ap.add_argument("--log-dir", default="slurm_logs", help="Directory for Slurm stdout/stderr logs")
    ap.add_argument("--jobs-dir", default="slurm_jobs", help="Directory to write generated sbatch scripts")
    ap.add_argument("--python", dest="python_bin", default="python", help="Python executable on the cluster (e.g. python3)")
    ap.add_argument("--submit", action="store_true", help="Submit via sbatch after generating the script")
    ap.add_argument("--dry-run", action="store_true", help="Print the sbatch script to stdout and exit")
    ap.add_argument("--clear-existing", action="store_true", help="Forward --clear-existing to run_repair_pipeline.py")
    ap.add_argument("--debug-matching", action="store_true", help="Force --debug-matching for the run")

    # Resource overrides (optional). These override config['slurm'] entries.
    ap.add_argument("--partition", default=None)
    ap.add_argument("--account", default=None)
    ap.add_argument("--qos", default=None)
    ap.add_argument("--constraint", default=None)
    ap.add_argument("--time", default=None, help="e.g. 02:00:00")
    ap.add_argument("--mem", default=None, help="e.g. 16G")
    ap.add_argument("--cpus-per-task", type=int, default=None)
    ap.add_argument("--gpus", default=None, help="e.g. 1 or gpu:1 depending on your cluster")

    args = ap.parse_args()

    config = _load_json(args.config)
    slurm_cfg = dict(config.get("slurm") or {})

    # Apply CLI overrides
    for k in ["partition", "account", "qos", "constraint", "time", "mem", "gpus"]:
        v = getattr(args, k)
        if v is not None:
            slurm_cfg[k] = v
    if args.cpus_per_task is not None:
        slurm_cfg["cpus_per_task"] = int(args.cpus_per_task)

    job_name = args.job_name or _infer_job_name(config)
    log_dir = args.log_dir
    jobs_dir = args.jobs_dir

    # Sensible default: if user didn't specify cpus_per_task, try to align with parallel_workers.
    if not slurm_cfg.get("cpus_per_task"):
        pw = config.get("parallel_workers")
        if isinstance(pw, int) and pw > 0:
            slurm_cfg["cpus_per_task"] = pw

    # Write script
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(jobs_dir, exist_ok=True)

    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    script_path = os.path.join(jobs_dir, f"{job_name}_{ts}.sbatch")

    debug_matching = bool(args.debug_matching or config.get("debug_matching", False))
    script_text = _build_sbatch_script(
        config_path=args.config,
        workdir=args.workdir,
        job_name=job_name,
        log_dir=log_dir,
        python_bin=args.python_bin,
        clear_existing=bool(args.clear_existing),
        debug_matching=debug_matching,
        slurm=slurm_cfg,
    )

    if args.dry_run:
        sys.stdout.write(script_text)
        return 0

    with open(script_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(script_text)

    print(f"[SLURM] wrote: {script_path}")

    if not args.submit:
        print("[SLURM] not submitted (pass --submit to call sbatch)")
        return 0

    if shutil.which("sbatch") is None:
        print("[SLURM] error: sbatch not found on PATH (generate-only mode succeeded).", file=sys.stderr)
        return 2

    proc = subprocess.run(["sbatch", script_path], text=True, capture_output=True)
    if proc.returncode != 0:
        print(proc.stdout, end="")
        print(proc.stderr, end="", file=sys.stderr)
        return proc.returncode

    # Typical output: "Submitted batch job 12345"
    print(proc.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
