import os
import re
import textwrap

def _get_saucedemo_credentials(test_type: str, step_descriptions: list) -> dict:
    """
    Определяет, какие логин/пароль использовать, исходя из типа теста и шагов.
    """
    # Стандартные учетные данные SauceDemo
    creds = {
        "valid_username": "standard_user",
        "valid_password": "secret_sauce",
        "invalid_username": "locked_out_user",  # или "nonexistent"
        "invalid_password": "wrong_password"
    }

    # Если в шагах упоминается "invalid", "wrong", "blocked" — используем негативные данные
    all_steps = " ".join(step_descriptions).lower()
    if any(word in all_steps for word in ["invalid", "wrong", "incorrect", "blocked", "locked"]):
        # Проверяем, что именно неверное
        if "username" in all_steps or "user" in all_steps:
            return {"username": creds["invalid_username"], "password": creds["valid_password"]}
        elif "password" in all_steps:
            return {"username": creds["valid_username"], "password": creds["invalid_password"]}
        else:
            # По умолчанию — неверный пароль
            return {"username": creds["valid_username"], "password": creds["invalid_password"]}

    # Позитивный сценарий
    return {"username": creds["valid_username"], "password": creds["valid_password"]}


def _generate_test_body(testcase: dict) -> str:
    """Генерирует тело теста для SauceDemo."""
    steps = testcase.get("steps", [])
    expected = testcase.get("expected_result", "").lower()
    test_type = testcase.get("type", "positive").lower()

    # Определяем учетные данные
    creds = _get_saucedemo_credentials(test_type, steps)

    code_lines = []

    # Ввод логина и пароля
    code_lines.append(f'    username_field = driver.find_element("id", "user-name")')
    code_lines.append(f'    password_field = driver.find_element("id", "password")')
    code_lines.append(f'    login_button = driver.find_element("id", "login-button")')
    code_lines.append('')
    code_lines.append(f'    username_field.send_keys("{creds["username"]}")')
    code_lines.append(f'    password_field.send_keys("{creds["password"]}")')
    code_lines.append(f'    login_button.click()')

    # ⚠️ НАМЕРЕННАЯ ОШИБКА ДЛЯ ЛИНТЕРА
    code_lines.append('    unused_var = 123  # This will be caught by linters')

    code_lines.append('')

    # Проверка результата
    if "products page" in expected or "inventory" in expected:
        code_lines.append('    # Verify successful login')
        code_lines.append('    assert "inventory.html" in driver.current_url')
        code_lines.append('    assert driver.find_element("id", "inventory_container").is_displayed()')
    elif "error" in expected or "not displayed" in expected:
        code_lines.append('    # Verify login error')
        code_lines.append('    error_message = driver.find_element("xpath", "//h3[@data-test=\'error\']")')
        code_lines.append('    assert error_message.is_displayed()')
    else:
        code_lines.append('    # Generic verification')
        code_lines.append('    assert driver.title != "Swag Labs"  # Title changes after login')

    return "\n".join(code_lines)

def run(ctx):
    run_id = ctx["run_id"]
    output_dir = os.path.join("artifacts", run_id, "autotests")
    os.makedirs(output_dir, exist_ok=True)

    testcases = ctx["testcases_json"]
    if not isinstance(testcases, list):
        testcases = [testcases]

    # Создаём conftest.py один раз
    conftest_path = os.path.join(output_dir, "conftest.py")
    if not os.path.exists(conftest_path):
        conftest_content = textwrap.dedent('''
            import pytest
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager

            @pytest.fixture(scope="function")
            def driver():
                service = Service(ChromeDriverManager().install())
                options = webdriver.ChromeOptions()
                options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                driver = webdriver.Chrome(service=service, options=options)
                driver.get("https://www.saucedemo.com/")
                yield driver
                driver.quit()
        ''').strip()  # .strip() убирает пустые строки в начале/конце

        with open(conftest_path, "w", encoding="utf-8") as f:
            f.write(conftest_content)

    autotest_files = []
    for testcase in testcases:
        test_id = testcase.get("test_id", "NO_ID")
        # Очищаем ID от недопустимых символов
        safe_test_id = re.sub(r"[^a-zA-Z0-9_]", "_", test_id)
        file_name = f"test_{safe_test_id.lower()}.py"
        file_path = os.path.join(output_dir, file_name)

        with open(file_path, "w", encoding="utf-8") as f:
            # Заголовок
            f.write(f"# Test Case: {testcase.get('title', 'No Title')}\n")
            f.write(f"# Requirement ID: {testcase.get('requirement_id', 'N/A')}\n")
            f.write(f"# Severity: {testcase.get('severity', 'N/A')}\n")
            f.write(f"# Type: {testcase.get('type', 'N/A')}\n\n")
            f.write("import pytest\n\n")
            f.write(f"def test_{safe_test_id.lower()}(driver):\n")
            f.write(_generate_test_body(testcase))

        autotest_files.append(file_path)

    ctx["autotests_dir"] = output_dir
    ctx["autotest_files"] = autotest_files