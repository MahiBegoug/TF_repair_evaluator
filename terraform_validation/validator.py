import subprocess
import json

class TerraformValidator:
    """
    Runs terraform validate -json only.
    Safe to call repeatedly (after terraform init is done).
    """

    @staticmethod
    def validate(tf_dir: str) -> dict:
        print(f"[INFO] Validating module: {tf_dir}")

        result = {
            "path": tf_dir,
            "validate_success": False,
            "diagnostics": [],
            "validate_json": None
        }

        proc = subprocess.run(
            ["terraform", "validate", "-no-color", "-json"],
            cwd=tf_dir,
            capture_output=True,
            text=True
        )

        result["validate_success"] = (proc.returncode == 0)

        try:
            data = json.loads(proc.stdout)
            result["validate_json"] = data
            result["diagnostics"] = data.get("diagnostics", [])
            print(f"[✓] validate JSON parsed for {tf_dir}")

        except json.JSONDecodeError:
            print("[ERROR] Could not decode terraform validate JSON")

        return result
