from google import genai
import requests
from config import config
from utils.exceptions import LLMError

def get_llm_client():
    if config.llm_provider == "cloud":
        if not config.gemini_api_key:
            raise LLMError("GEMINI_API_KEY is not set for 'cloud' LLM_PROVIDER.")
        print("Using Google Gemini (Cloud) LLM provider.")
        return genai.Client(api_key=config.gemini_api_key)
    elif config.llm_provider == "local":
        print(f"Using Local LLM provider with endpoint: {config.local_llm_endpoint}")
        return LocalLLMClient(config.local_llm_endpoint)
    else:
        raise LLMError(f"Unsupported LLM_PROVIDER: {config.llm_provider}. Must be 'cloud' or 'local'.")

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
    try:
        if config.llm_provider == "cloud":
            response = client.models.generate_content(
                model=model_name,
                contents=[prompt],
                generation_config={"temperature": temperature}
            )
        elif config.llm_provider == "local":
            response = client.generate_content(
                model=model_name,
                contents=[prompt],
                generation_config={"temperature": temperature}
            )
        return response.candidates[0].content.parts[0].text.strip()
    except Exception as e:
        raise LLMError(f"Failed to call LLM: {e}") from e

