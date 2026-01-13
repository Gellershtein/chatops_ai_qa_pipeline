PROMPT = '''
You are a Senior QA Engineer.

Based on the following artifacts:
- original checklist
- generated test cases
- generated autotests
- AI code review
- Test results
- QA Summary

Detect potential defects, inconsistencies, missing validations or risks.

If no issues are found, return:

{ "status": "NO_BUGS_FOUND" }

If issues are found, return STRICT JSON:

{
  "title": "",
  "severity": "",
  "priority": "",
  "environment": "web",
  "preconditions": "",
  "steps_to_reproduce": [],
  "actual_result": "",
  "expected_result": "",
  "probable_root_cause": "",
  "evidence": ""
}

Rules:
- return ONLY valid JSON
- no markdown
- no explanations

CHECKLIST:
{checklist}

TESTCASES:
{testcases}

CODE REVIEW:
{review}

AUTOTESTS:
{tests}

QA_SUMMARY:
{qa_summary}

TEST_RESULTS:
{test_results}
'''
