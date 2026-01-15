"""
This module is responsible for generating Python Pytest autotests based on a list of test cases.
It specifically targets the SauceDemo login functionality, incorporating dynamic credential
selection and assertion generation based on test case details.
"""
import os
import re
import textwrap
from typing import List, Dict, Any

def _get_saucedemo_credentials(test_type: str, step_descriptions: List[str]) -> Dict[str, str]:
    """
    Determines the appropriate username and password to use for a SauceDemo login test
    based on the test's type (positive/negative) and the descriptions of its steps.

    Args:
        test_type (str): The type of the test case (e.g., "positive", "negative").
        step_descriptions (List[str]): A list of strings describing the steps of the test case.

    Returns:
        Dict[str, str]: A dictionary containing the "username" and "password" to be used in the test.
                        Examples: {"username": "standard_user", "password": "secret_sauce"}
    """
    # Standard SauceDemo credentials
    creds = {
        "valid_username": "standard_user",
        "valid_password": "secret_sauce",
        "invalid_username": "locked_out_user",  # Could also be a non-existent user
        "invalid_password": "wrong_password"
    }

    # Check if step descriptions indicate a negative test scenario (e.g., invalid input)
    all_steps = " ".join(step_descriptions).lower()
    if any(word in all_steps for word in ["invalid", "wrong", "incorrect", "blocked", "locked"]):
        # Determine if the invalidity is related to username or password
        if "username" in all_steps or "user" in all_steps:
            return {"username": creds["invalid_username"], "password": creds["valid_password"]}
        elif "password" in all_steps:
            return {"username": creds["valid_username"], "password": creds["invalid_password"]}
        else:
            # Default to invalid password if specific invalid field is unclear
            return {"username": creds["valid_username"], "password": creds["invalid_password"]}

    # Default to positive scenario credentials
    return {"username": creds["valid_username"], "password": creds["valid_password"]}


def _generate_test_body(testcase: Dict[str, Any]) -> str:
    """
    Generates the Python code for the body of a single Pytest test function for SauceDemo login.
    It constructs the login sequence (filling username/password, clicking login)
    and then adds assertions based on the test case's expected result.

    Args:
        testcase (Dict[str, Any]): A dictionary representing a single test case, expected to contain:
                                    - "steps" (list): List of step descriptions.
                                    - "expected_result" (str): The expected outcome of the test.
                                    - "type" (str): The type of test (e.g., "positive", "negative").

    Returns:
        str: A multi-line string containing the Python code for the test body, properly indented.
    """
    steps = testcase.get("steps", [])
    expected = testcase.get("expected_result", "").lower()
    test_type = testcase.get("type", "positive").lower()

    # Determine login credentials based on test case details
    creds = _get_saucedemo_credentials(test_type, steps)

    code_lines = []

    # Generate code for entering credentials and clicking login
    code_lines.append(f'    username_field = driver.find_element("id", "user-name")')
    code_lines.append(f'    password_field = driver.find_element("id", "password")')
    code_lines.append(f'    login_button = driver.find_element("id", "login-button")')
    code_lines.append('')
    code_lines.append(f'    username_field.send_keys("{creds["username"]}")')
    code_lines.append(f'    password_field.send_keys("{creds["password"]}")')
    code_lines.append(f'    login_button.click()')

    # ⚠️ INTENTIONAL ERROR FOR LINTER DEMONSTRATION ⚠️
    # This line is intentionally left to trigger linter warnings/errors
    # for the code quality check step of the pipeline.
    code_lines.append('    unused_var = 123  # This will be caught by linters')

    code_lines.append('')

    # Generate assertions based on the expected result of the test case
    if "products page" in expected or "inventory" in expected:
        code_lines.append('    # Verify successful login: check URL and presence of inventory container')
        code_lines.append('    assert "inventory.html" in driver.current_url')
        code_lines.append('    assert driver.find_element("id", "inventory_container").is_displayed()')
    elif "error" in expected or "not displayed" in expected:
        code_lines.append('    # Verify login error: check for error message element visibility')
        code_lines.append('    error_message = driver.find_element("xpath", "//h3[@data-test=\'error\']")')
        code_lines.append('    assert error_message.is_displayed()')
    else:
        # Generic verification if expected result is not specific to success or error
        code_lines.append('    # Generic verification: assume title changes after successful login')
        code_lines.append('    assert driver.title != "Swag Labs"  # Title changes after login')

    return "\n".join(code_lines)

def run(ctx: dict) -> None:
    """
    Executes the Generate Autotests step. It takes a list of test cases from the context,
    generates Python Pytest files for each test case, and creates a `conftest.py` file
    with necessary WebDriver fixtures. The generated autotests are stored in a
    specific directory within the artifacts, and their paths are added to the context.

    Args:
        ctx (dict): The pipeline context dictionary, which must contain:
                    - 'run_id' (str): The unique identifier for the current pipeline run.
                    - 'testcases_json' (list): A list of dictionaries, where each dictionary
                                             represents a test case to be converted into an autotest.
    """
    run_id = ctx["run_id"]
    output_dir = os.path.join("artifacts", run_id, "autotests")
    os.makedirs(output_dir, exist_ok=True) # Ensure the output directory exists

    testcases = ctx["testcases_json"]
    # Ensure testcases is always a list for iteration
    if not isinstance(testcases, list):
        testcases = [testcases]

    # Create conftest.py if it doesn't already exist in the output directory
    conftest_path = os.path.join(output_dir, "conftest.py")
    if not os.path.exists(conftest_path):
        conftest_content = textwrap.dedent('''
            import pytest
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager

            @pytest.fixture(scope="function")
            def driver():
                # Install Chrome driver if not already present and set up the service
                service = Service(ChromeDriverManager().install())
                options = webdriver.ChromeOptions()
                # Configure Chrome options for headless execution and CI compatibility
                options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu") # Applicable to Windows mostly
                driver = webdriver.Chrome(service=service, options=options)
                driver.get("https://www.saucedemo.com/") # Navigate to the base URL
                yield driver # Provide the driver instance to the test
                driver.quit() # Teardown: Close the browser after the test
        ''').strip()

        with open(conftest_path, "w", encoding="utf-8") as f:
            f.write(conftest_content)

    autotest_files = [] # List to store paths of generated autotest files
    for testcase in testcases:
        test_id = testcase.get("test_id", "NO_ID")
        # Sanitize test_id to create a valid filename (replace invalid characters with underscores)
        safe_test_id = re.sub(r"[^a-zA-Z0-9_]", "_", test_id)
        file_name = f"test_{safe_test_id.lower()}.py"
        file_path = os.path.join(output_dir, file_name)

        with open(file_path, "w", encoding="utf-8") as f:
            # Add header comments to the test file for metadata
            f.write(f"# Test Case: {testcase.get('title', 'No Title')}\n")
            f.write(f"# Requirement ID: {testcase.get('requirement_id', 'N/A')}\n")
            f.write(f"# Severity: {testcase.get('severity', 'N/A')}\n")
            f.write(f"# Type: {testcase.get('type', 'N/A')}\n\n")
            f.write("import pytest\n\n")
            # Define the test function and insert the generated test body
            f.write(f"def test_{safe_test_id.lower()}(driver):\n")
            f.write(_generate_test_body(testcase))

        autotest_files.append(file_path)

    # Store the output directory and list of generated files in the context
    ctx["autotests_dir"] = output_dir
    ctx["autotest_files"] = autotest_files
    print(f"✅ Generated {len(autotest_files)} autotests in {output_dir}")