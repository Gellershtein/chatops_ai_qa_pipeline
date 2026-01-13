import os
import json
from llm.gemini_client import call_llm
from llm.prompts.bug_report import PROMPT

def run(ctx):
    checklist = ctx["txt"]
    testcases = ctx["testcases_json"]
    
    autotests = ""
    autotest_files = ctx.get("autotest_files", [])
    if autotest_files:
        for file_path in autotest_files:
            if file_path.endswith(".py"):
                with open(file_path, "r") as f:
                    autotests += f"--- {os.path.basename(file_path)} ---\n"
                    autotests += f.read()
                    autotests += "\n\n"

    reviews = ""
    if "ai_code_reviews" in ctx:
        for review_path in ctx["ai_code_reviews"]:
            with open(review_path, "r") as f:
                reviews += f"--- {os.path.basename(review_path)} ---\n"
                reviews += f.read()
                reviews += "\n\n"
    
    test_results = ""
    if "test_results" in ctx and ctx["test_results"] and os.path.exists(ctx["test_results"]):
        with open(ctx["test_results"], "r") as f:
            test_results = f.read()

    qa_summary = ctx.get("qa_summary_text", "Not available")

    prompt = PROMPT.format(
        checklist=checklist,
        testcases=testcases,
        tests=autotests,
        review=reviews,
        qa_summary=qa_summary,
        test_results=test_results
    )

    bug_report_json_str = call_llm(prompt)
    
    try:
        if bug_report_json_str.startswith("```json"):
            bug_report_json_str = bug_report_json_str[7:-4]
        bug_report = json.loads(bug_report_json_str)
        report_dir = "reports"
        os.makedirs(report_dir, exist_ok=True)
        report_file = os.path.join(report_dir, f"bug_report_{ctx['run_id']}.json")
        with open(report_file, "w") as f:
            json.dump(bug_report, f, indent=2)
        ctx["bug_report"] = report_file
    except json.JSONDecodeError:
        print(f"Failed to decode JSON from LLM for bug report")
        # Optionally, save the raw string for debugging
        error_file = os.path.join("reports", f"bug_report_{ctx['run_id']}_error.txt")
        with open(error_file, "w") as f:
            f.write(bug_report_json_str)
