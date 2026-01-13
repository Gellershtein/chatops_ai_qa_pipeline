
import os
from dotenv import load_dotenv
from llm.gemini_client import call_llm
from llm.prompts.testcases import PROMPT

load_dotenv()

def run(ctx):
    model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-pro")
    temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
    
    scenarios = ctx["masked_scenarios"]
    prompt_text = PROMPT.format(scenarios=scenarios)
    result = call_llm(model_name=model_name, temperature=temperature, prompt=prompt_text)
    ctx["testcases_json"] = result