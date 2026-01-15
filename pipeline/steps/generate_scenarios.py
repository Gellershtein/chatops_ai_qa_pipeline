"""
This module implements the Generate Scenarios step of the QA pipeline.
It utilizes a Large Language Model (LLM) to convert a masked checklist of requirements
into a set of detailed test scenarios, which are then stored in the pipeline context.
"""
import os
from llm.llm_client import call_llm
from llm.prompts.scenarios import PROMPT
from typing import Dict, Any

def run(ctx: Dict[str, Any]) -> None:
    """
    Executes the Generate Scenarios step. It takes the PII-masked checklist from the
    context, formats it into a prompt for the LLM, calls the LLM to generate test scenarios,
    and then stores the generated scenarios back into the pipeline context.

    Args:
        ctx (Dict[str, Any]): The pipeline context dictionary, which must contain:
                              - 'masked_scenarios' (str): The PII-masked checklist content.
    """
    # Configure LLM provider and model name based on environment variables
    llm_provider = os.getenv("LLM_PROVIDER", "cloud")
    if llm_provider == "cloud":
        model_name = os.getenv("CLOUD_MODEL_NAME", "gemini-pro")
    else:
        model_name = os.getenv("LOCAL_MODEL_NAME", "llama2")
    
    # Set temperature for LLM generation from environment variable
    temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
    
    # Get the masked scenarios from the context
    scenarios_input = ctx["masked_scenarios"]
    # Format the prompt using the masked scenarios
    prompt_text = PROMPT.format(checklist=scenarios_input)
    
    # Call the LLM to generate the scenarios
    result = call_llm(model_name=model_name, temperature=temperature, prompt=prompt_text)
    
    # Store the generated scenarios back into the context
    ctx["scenarios"] = result
    print("✅ Scenarios generated successfully.")