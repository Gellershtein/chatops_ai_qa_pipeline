import os
from llm.llm_client import call_llm
from llm.prompts.scenarios import PROMPT

def run(ctx):
    llm_provider = os.getenv("LLM_PROVIDER", "cloud")
    if llm_provider == "cloud":
        model_name = os.getenv("CLOUD_MODEL_NAME", "gemini-pro")
    else:
        model_name = os.getenv("LOCAL_MODEL_NAME", "llama2")
    
    temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
    
    scenarios = ctx["masked_scenarios"]
    prompt_text = PROMPT.format(checklist=scenarios)
    result = call_llm(model_name=model_name, temperature=temperature, prompt=prompt_text)
    ctx["scenarios"] = result