import os
from dotenv import load_dotenv
from llm.gemini_client import call_llm
from llm.prompts.scenarios import PROMPT

load_dotenv()

def run(ctx):
    model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-pro")
    temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
    
    # The PROMPT now expects the raw checklist text
    prompt_text = PROMPT.format(checklist=ctx["txt"])
    result = call_llm(model_name=model_name, temperature=temperature, prompt=prompt_text)
    print(f"DEBUG: Generated Scenarios Result Length: {len(result) if result else 0}")
    print(f"DEBUG: Generated Scenarios Result Snippet: {result[:200] if result else 'None'}")
    # Store the JSON output from the LLM back into ctx["txt"]
    ctx["scenarios"] = result