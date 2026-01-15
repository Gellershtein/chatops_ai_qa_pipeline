"""
This module defines the Large Language Model (LLM) prompt used for converting
human-readable test scenarios into a structured JSON array of test cases.
"""

PROMPT = '''
# Test Case Generation Prompt for LLM

You are a Senior QA engineer. Your task is to convert ALL provided test scenarios
into a STRICT JSON array of test cases.

## Rules for Test Case Generation:
-   **Output ONLY a valid JSON object** with a top-level key `"testcases"`.
-   The value of `"testcases"` **MUST** be an array containing **ONE** test case object per scenario.
-   **DO NOT omit any scenario** from the input. Every scenario must have a corresponding test case.
-   **DO NOT merge scenarios**. Each input scenario maps to a single output test case.
-   Use the **exact structure below** for each test case object.
-   Return **ONLY raw JSON** — no markdown, no explanations, no ```json formatting.

## Expected JSON Structure:
```json
{{
  "testcases": [
    {{
      "test_id": "UNIQUE_ID",
      "requirement_id": "REQ-XXX",
      "title": "Concise title",
      "type": "positive | negative",
      "steps": ["Step 1", "Step 2", ...],
      "expected_result": "Expected outcome",
      "severity": "critical | high | medium | low"
    }}
    // ... one object per scenario
  ]
}}
```

---

Now process these scenarios into test cases:

**SCENARIOS (provided for conversion):**
{scenarios}
'''