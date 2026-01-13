PROMPT = '''
You are a senior QA Lead.

Based on the provided test execution logs and results, generate a brief, high-level QA summary.
If no issues, write: "All tests passed successfully."
The summary should be easy for a project manager to understand.


Focus on:
- The overall status (e.g., how many tests passed, failed, or were skipped).
- Any significant errors or patterns observed in the logs.
- A concluding sentence on the stability of the build based on these results.

Do not include code snippets or overly technical jargon.

TEST RESULTS LOG:
{test_log}

TEST RESULTS XML REPORT:
{test_xml}
'''