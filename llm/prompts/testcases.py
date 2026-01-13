PROMPT = '''
You are a Senior QA engineer. Convert ALL provided test scenarios into a STRICT JSON array of test cases.

Rules:
- Output ONLY a valid JSON object with key "testcases"
- The value MUST be an array containing ONE test case per scenario
- DO NOT omit any scenario
- DO NOT merge scenarios
- Use the exact structure below for each test case
- Return ONLY raw JSON — no markdown, no explanations, no ```json

Expected JSON structure:
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

Now process these scenarios:

SCENARIOS:
{scenarios}
'''