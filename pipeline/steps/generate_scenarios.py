from llm.gemini_client import call_llm
from llm.prompts.scenarios import PROMPT
from config import config

def run(ctx):
    if config.llm_provider == "cloud":
        model_name = config.cloud_model_name
    else:
        model_name = config.local_model_name
    
    temperature = config.gemini_temperature
    
    scenarios = ctx["masked_scenarios"]
    prompt_text = PROMPT.format(checklist=scenarios)
    result = call_llm(model_name=model_name, temperature=temperature, prompt=prompt_text)
    ctx["scenarios"] = result