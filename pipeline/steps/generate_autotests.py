import json
import os

def run(ctx):
    output_dir = os.path.join("tests", "generated")
    os.makedirs(output_dir, exist_ok=True)

    data = json.loads(ctx["testcases_json"])
    testcases = data.get("testcases", [])
    
    if not isinstance(testcases, list):
        testcases = [testcases]

    autotest_files = []
    for testcase in testcases:
        test_id = testcase.get("test_id", "NO_ID")
        file_name = f"Test_{test_id}.py"
        file_path = os.path.join(output_dir, file_name)

        with open(file_path, "w") as f:
            f.write(f"# Test Case: {testcase.get('title', 'No Title')}\n")
            f.write(f"# Requirement ID: {testcase.get('requirement_id', 'N/A')}\n")
            f.write(f"# Severity: {testcase.get('severity', 'N/A')}\n")
            f.write(f"# Type: {testcase.get('type', 'N/A')}\n\n")
            f.write("import pytest\n\n")
            f.write(f"def test_{test_id.lower()}():\n")
            f.write("    # Steps:\n")
            for step in testcase.get("steps", []):
                f.write(f"    # - {step}\n")
            f.write("\n")
            f.write(f"    # Expected Result: {testcase.get('expected_result', 'N/A')}\n")
            f.write("    pytest.skip('Not implemented yet')\n")
        autotest_files.append(file_path)
    
    ctx["autotest_files"] = autotest_files
