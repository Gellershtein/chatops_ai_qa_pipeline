
import os
from dotenv import load_dotenv
from llm.gemini_client import call_llm
from llm.prompts.testcases import PROMPT

load_dotenv()

def run(ctx):
    llm_provider = os.getenv("LLM_PROVIDER", "cloud")
    if llm_provider == "cloud":
        model_name = os.getenv("CLOUD_MODEL_NAME", "gemini-pro")
    else: # local
        model_name = os.getenv("LOCAL_MODEL_NAME", "llama2")
    
    temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
    
    scenarios = ctx["scenarios"]
    prompt_text = PROMPT.format(scenarios=scenarios)
    result = call_llm(model_name=model_name, temperature=temperature, prompt=prompt_text)
    ctx["testcases_json"] = result