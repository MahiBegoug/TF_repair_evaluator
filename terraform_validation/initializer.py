import subprocess

class TerraformInitializer:
    """
    Run terraform init once per module.
    """

    @staticmethod
    def init_module(tf_dir: str) -> bool:
        print(f"[INFO] Initializing module: {tf_dir}")

        proc = subprocess.run(
            ["terraform", "init", "-input=false", "-backend=false", "-no-color"],
            cwd=tf_dir,
            capture_output=True,
            text=True
        )

        if proc.returncode != 0:
            print(f"[ERROR] terraform init FAILED in {tf_dir}")
            print(proc.stderr.strip())
            return False

        print(f"[✓] terraform init successful for {tf_dir}")
        return True
