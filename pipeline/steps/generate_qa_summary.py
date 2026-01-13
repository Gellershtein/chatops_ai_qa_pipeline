import os
from llm.gemini_client import call_llm
from llm.prompts.qa_summary import PROMPT
from logs.logger import log_error

def run(ctx):
    """
    Generates a QA summary by analyzing test results with an LLM.
    """
    run_id = ctx["run_id"]
    report_dir = "reports"
    os.makedirs(report_dir, exist_ok=True)
    
    test_log_path = ctx.get("test_run_log")
    test_xml_path = ctx.get("test_results")

    test_log = ""
    if test_log_path and os.path.exists(test_log_path):
        with open(test_log_path, 'r') as f:
            test_log = f.read()

    test_xml = ""
    if test_xml_path and os.path.exists(test_xml_path):
        with open(test_xml_path, 'r') as f:
            test_xml = f.read()

    if not test_log and not test_xml:
        print("No test results found to generate a QA summary.")
        ctx["qa_summary"] = None
        return

    try:
        prompt = PROMPT.format(test_log=test_log, test_xml=test_xml)
        summary_text = call_llm(prompt)
        
        summary_file_path = os.path.join(report_dir, f"qa_summary_{run_id}.txt")
        with open(summary_file_path, "w") as f:
            f.write(summary_text)
            
        ctx["qa_summary_report"] = summary_file_path
        ctx["qa_summary_text"] = summary_text # Also keep the text in context for the bug report step
        print(f"QA Summary generated and saved to {summary_file_path}")

    except Exception as e:
        error_message = f"Failed to generate QA summary. Error: {e}"
        log_error(error_message)
        # Do not fail the whole pipeline, just log the error
        ctx["qa_summary_report"] = None
        ctx["qa_summary_text"] = None
