import os
import json
from llm.gemini_client import call_llm
from llm.prompts.code_review import PROMPT

def run(ctx):
    test_dir = os.path.join("tests", "generated")
    report_dir = "reports"
    os.makedirs(report_dir, exist_ok=True)

    reviews = []
    autotest_files = ctx.get("autotest_files", [])
    if not autotest_files:
        print("No autotest files found to review.")
        ctx["ai_code_reviews"] = []
        return

    reviews = []
    for file_path in autotest_files:
        if file_path.endswith(".py"):
            with open(file_path, "r") as f:
                code = f.read()

            test_id = os.path.basename(file_path).replace("Test_", "").replace(".py", "")
            
            review_prompt = PROMPT.format(code=code, test_id=test_id)
            review_json_str = call_llm(review_prompt)
            
            try:
                # The prompt asks for a JSON object, but the LLM might return it wrapped in ```json ... ```
                if review_json_str.startswith("```json"):
                    review_json_str = review_json_str[7:-4]

                review = json.loads(review_json_str)
                review_file = os.path.join(report_dir, f"code_review_{test_id}.json")
                with open(review_file, "w") as f:
                    json.dump(review, f, indent=2)
                reviews.append(review_file)
            except json.JSONDecodeError as e:
                print(f"Failed to decode JSON from LLM for {test_id}: {e}")
                # Optionally, save the raw string for debugging
                error_file = os.path.join(report_dir, f"code_review_{test_id}_error.txt")
                with open(error_file, "w") as f:
                    f.write(review_json_str)

    ctx["ai_code_reviews"] = reviews

