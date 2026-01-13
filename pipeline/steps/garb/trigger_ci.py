import os
import subprocess
from logs.logger import log_error

def run(ctx):
    """
    Simulates a CI trigger by committing the generated tests to a local git repository.
    """
    run_id = ctx["run_id"]
    test_dir = os.path.join("tests", "generated")

    if not os.path.exists(test_dir):
        log_error(f"Test directory {test_dir} not found for CI trigger.")
        ctx["ci_triggered"] = False
        return

    try:
        # Initialize git repo if it doesn't exist
        if not os.path.exists(os.path.join(test_dir, ".git")):
            subprocess.run(["git", "init"], cwd=test_dir, check=True, capture_output=True, text=True)

        # Check git config
        user_name = subprocess.run(["git", "config", "user.name"], cwd=test_dir, capture_output=True, text=True)
        user_email = subprocess.run(["git", "config", "user.email"], cwd=test_dir, capture_output=True, text=True)
        if not user_name.stdout.strip() or not user_email.stdout.strip():
            raise Exception("Git user.name and user.email are not configured. Please configure them to proceed.")

        # Add all generated files
        subprocess.run(["git", "add", "."], cwd=test_dir, check=True, capture_output=True, text=True)

        # Commit the files with the run_id
        commit_message = f"feat: Add generated tests for run_id {run_id}"
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", commit_message], 
            cwd=test_dir, 
            check=True, 
            capture_output=True, 
            text=True
        )
        
        print(f"Committed generated tests to local git repo in {test_dir}")
        ctx["ci_triggered"] = True

    except subprocess.CalledProcessError as e:
        error_message = f"Failed to trigger CI (git commit). Error: {e.stderr}"
        log_error(error_message)
        # Re-raise or handle as a pipeline failure
        raise Exception(error_message)
    except FileNotFoundError:
        error_message = "Git command not found. Please ensure git is installed and in your PATH."
        log_error(error_message)
        raise Exception(error_message)
