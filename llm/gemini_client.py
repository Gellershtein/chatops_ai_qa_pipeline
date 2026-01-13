import os
import time
from dotenv import load_dotenv
from google import genai
import requests # For potential local LLM API calls

load_dotenv()

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "cloud") # Default to cloud
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LOCAL_LLM_ENDPOINT = os.getenv("LOCAL_LLM_ENDPOINT", "http://localhost:8000/v1") # Default local endpoint

# Initialize client based on provider
if LLM_PROVIDER == "cloud":
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set for 'cloud' LLM_PROVIDER.")
    client = genai.Client(api_key=GEMINI_API_KEY)
    print("Using Google Gemini (Cloud) LLM provider.")
elif LLM_PROVIDER == "local":
    # Placeholder for local LLM client.
    # In a real scenario, this would be an actual client for Ollama, LocalGPT, etc.
    class LocalLLMClient:
        def __init__(self, endpoint):
            self.endpoint = endpoint
            print(f"Using Local LLM provider with endpoint: {self.endpoint}")

        # This is a mock implementation. Users would replace this with actual API calls.
        def generate_content(self, model, contents, generation_config):
            # For a real local LLM (e.g., OpenAI compatible API like Ollama):
            try:
                headers = {"Content-Type": "application/json"}
                data = {
                    "model": model,
                    "messages": [{"role": "user", "content": contents[0]}],
                    "temperature": generation_config.get("temperature", 0.7),
                    "stream": False # Added this line
                }
                response = requests.post(f"{self.endpoint}/api/chat", headers=headers, json=data)
                response.raise_for_status()
                json_response = response.json()
                return type('obj', (object,), {
                    'candidates': [type('obj', (object,), {
                        'content': type('obj', (object,), {
                            'parts': [type('obj', (object,), {'text': json_response['message']['content']})]
                        })
                    })
                ]
                })()
            except requests.exceptions.RequestException as e:
                raise Exception(f"Local LLM API call failed: {e}")
            
    client = LocalLLMClient(LOCAL_LLM_ENDPOINT)
else:
    raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}. Must be 'cloud' or 'local'.")


def call_llm(model_name: str, temperature: float, prompt: str):
    # For cloud (Gemini), temperature is part of generation_config
    # For local, it might be passed directly or within messages
    generation_config_payload = {"temperature": temperature} if LLM_PROVIDER == "cloud" else {}

    # The `client.models.generate_content` call from Google's genai library
    # doesn't directly accept `generation_config` as a top-level argument.
    # It seems to be handled implicitly or via other means for the "cloud" provider in this setup.
    # For the local mock, we include it.

    if LLM_PROVIDER == "cloud":
        # Based on previous trial, generation_config is not a direct arg here.
        # This function should only pass the arguments that the client.models.generate_content expects.
        # The temperature in client.models.generate_content is often set via model parameters or
        # configured globally for a session, not directly in the call.
        # For this setup, we'll omit temperature if it causes issues for cloud.
        # However, the user's provided example did not include temperature.
        # Let's revert to a strict interpretation of the working example for cloud:
        response = client.models.generate_content(
            model=model_name,
            contents=[prompt],
        )
    elif LLM_PROVIDER == "local":
        # For the mock local client, `generate_content` is designed to accept generation_config
        response = client.generate_content(
            model=model_name,
            contents=[prompt],
            generation_config=generation_config_payload # Pass for local mock if designed to use it
        )
    
    return response.candidates[0].content.parts[0].text.strip()
