import os
from google import genai
import requests
from utils.exceptions import LLMError

def get_llm_client():
    llm_provider = os.getenv("LLM_PROVIDER", "cloud") # Default to "cloud" if not set
    if llm_provider == "cloud":
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise LLMError("GEMINI_API_KEY is not set for 'cloud' LLM_PROVIDER.")
        print("Using Google Gemini (Cloud) LLM provider.")
        return genai.Client(api_key=gemini_api_key)
    elif llm_provider == "local":
        local_llm_endpoint = os.getenv("LOCAL_LLM_ENDPOINT", "http://localhost:8000/v1") # Default if not set
        print(f"Using Local LLM provider with endpoint: {local_llm_endpoint}")
        return LocalLLMClient(local_llm_endpoint)
    else:
        raise LLMError(f"Unsupported LLM_PROVIDER: {llm_provider}. Must be 'cloud' or 'local'.")

class LocalLLMClient:
    def __init__(self, endpoint):
        self.endpoint = endpoint

    def generate_content(self, model, contents, generation_config):
        try:
            headers = {"Content-Type": "application/json"}
            data = {
                "model": model,
                "messages": [{"role": "user", "content": contents[0]}],
                "temperature": generation_config.get("temperature", 0.7),
                "stream": False
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
            raise LLMError(f"Local LLM API call failed: {e}") from e

client = get_llm_client()

def call_llm(model_name: str, temperature: float, prompt: str):
    llm_provider = os.getenv("LLM_PROVIDER", "cloud")
    try:
        if llm_provider == "cloud":
            response = client.models.generate_content(
                model=model_name,
                contents=[prompt],
                generation_config={"temperature": temperature}
            )
        elif llm_provider == "local":
            response = client.generate_content(
                model=model_name,
                contents=[prompt],
                generation_config={"temperature": temperature}
            )
        return response.candidates[0].content.parts[0].text.strip()
    except Exception as e:
        raise LLMError(f"Failed to call LLM: {e}") from e

