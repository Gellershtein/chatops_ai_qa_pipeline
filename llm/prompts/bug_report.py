"""
This module defines the Large Language Model (LLM) prompt used for generating bug reports.
The prompt instructs the LLM to analyze test cases and autotests to identify discrepancies
and format the findings into a structured JSON bug report.
"""

PROMPT = '''
# Bug Report Generation Prompt for LLM

You are a Senior QA Engineer. Your task is to meticulously analyze the provided `TESTCASES`
and `AUTOTESTS` to identify any mismatches or incomplete implementations.

## Analysis Criteria:
1.  **Compare each test case in `TESTCASES` with its corresponding autotest in `AUTOTESTS`**
    (match them by `test_id`).
2.  **Verify if the autotest implements ALL steps** described in its respective test case.
3.  **Check if assertions in the autotest accurately match the `expected_result`** specified in the test case.
4.  **Report ONLY concrete, verifiable mismatches.** Do not make assumptions or infer issues.

## Output Format:

If **NO issues are found**, return the following exact JSON:
```json
{{"status": "NO_BUGS_FOUND"}}
```

If an **issue is found**, return a STRICT JSON object representing a bug report, using the following structure:
```json
{{
  "title": "Mismatch in [TEST_ID]",
  "severity": "critical",
  "priority": "high",
  "environment": "QA pipeline",
  "preconditions": "Test case vs autotest comparison",
  "steps_to_reproduce": [
    "1. Open test case [TEST_ID]",
    "2. Open autotest test_[test_id].py",
    "3. Compare steps and assertions"
  ],
  "actual_result": "Autotest does X",
  "expected_result": "Autotest should do Y",
  "probable_root_cause": "Generator did not implement cart logic",
  "evidence": "Code snippet showing missing steps"
}}
```

## Important Rules:
-   Output **ONLY** valid JSON. No additional text, explanations, or formatting.
-   Provide **NO** general advice or recommendations.
-   Focus on describing **ONE specific defect** per report.
-   Use **real `test_id` values** from the `TESTCASES` provided.

---

**TESTCASES (provided for analysis):**
{testcases}

**AUTOTESTS (provided for analysis):**
{tests}
'''