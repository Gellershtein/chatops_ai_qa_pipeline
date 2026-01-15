"""
This module provides a unified client for interacting with different Large Language Model (LLM) providers,
supporting both cloud-based (Google Gemini) and local LLMs. It abstracts the underlying API calls
to provide a consistent interface for generating content.
"""
import os
from google import genai
import requests
from utils.exceptions import LLMError
from abc import ABC, abstractmethod # Import ABC and abstractmethod

# Abstract LLM Client Interface
class AbstractLLMClient(ABC):
    """
    Abstract base class for LLM clients.
    Defines the common interface for generating content from an LLM.
    """
    @abstractmethod
    def generate_content(self, model_name: str, contents: list, generation_config: dict):
        """
        Generates content using the specified LLM.

        Args:
            model_name (str): The name of the LLM model to use.
            contents (list): A list of content parts to send to the LLM (e.g., prompts).
            generation_config (dict): Configuration for content generation, such as temperature.
        """
        pass

class CloudLLMClient(AbstractLLMClient):
    """
    LLM client for interacting with cloud-based Google Gemini models.
    """
    def __init__(self, api_key: str):
        """
        Initializes the CloudLLMClient with the Google Gemini API key.

        Args:
            api_key (str): The API key for Google Gemini.
        """
        genai.configure(api_key=api_key)

    def generate_content(self, model_name: str, contents: list, generation_config: dict):
        """
        Generates content using a cloud-based Google Gemini model.

        Args:
            model_name (str): The name of the Gemini model to use (e.g., 'gemini-pro').
            contents (list): A list of content parts (prompts).
            generation_config (dict): Configuration for generation, typically including 'temperature'.

        Returns:
            GenerativeModelResponse: The response object from the Gemini API.
        """
        model = genai.GenerativeModel(model_name)
        # Assuming temperature is the only config for now that needs to be explicitly passed
        temp_config = genai.GenerationConfig(temperature=generation_config.get("temperature", 0.7))
        response = model.generate_content(
            contents=contents,
            generation_config=temp_config
        )
        return response

class LocalLLMClient(AbstractLLMClient):
    """
    LLM client for interacting with local LLM endpoints (e.g., Ollama).
    """
    def __init__(self, endpoint: str):
        """
        Initializes the LocalLLMClient with the local LLM endpoint URL.

        Args:
            endpoint (str): The URL of the local LLM API endpoint.
        """
        self.endpoint = endpoint

    def generate_content(self, model_name: str, contents: list, generation_config: dict):
        """
        Generates content using a local LLM by making an HTTP POST request to the local endpoint.

        Args:
            model_name (str): The name of the local LLM model to use.
            contents (list): A list of content parts (prompts).
            generation_config (dict): Configuration for generation, typically including 'temperature'.

        Returns:
            object: A mocked response object structured similarly to the Gemini API response
                    to maintain compatibility.

        Raises:
            LLMError: If the local LLM API call fails.
        """
        try:
            headers = {"Content-Type": "application/json"}
            data = {
                "model": model_name,
                "messages": [{"role": "user", "content": contents[0]}],
                "temperature": generation_config.get("temperature", 0.7),
                "stream": False
            }
            response = requests.post(f"{self.endpoint}/api/chat", headers=headers, json=data)
            response.raise_for_status()
            json_response = response.json()
            # Reconstruct a similar response object structure to mimic genai.GenerativeModelResponse
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

def get_llm_client() -> AbstractLLMClient:
    """
    Factory function to get the appropriate LLM client based on the 'LLM_PROVIDER'
    environment variable.

    Returns:
        AbstractLLMClient: An instance of either CloudLLMClient or LocalLLMClient.

    Raises:
        LLMError: If 'LLM_PROVIDER' is unsupported or 'GEMINI_API_KEY' is missing for cloud provider.
    """
    llm_provider = os.getenv("LLM_PROVIDER", "cloud") # Default to "cloud" if not set
    if llm_provider == "cloud":
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise LLMError("GEMINI_API_KEY is not set for 'cloud' LLM_PROVIDER.")
        print("Using Google Gemini (Cloud) LLM provider.")
        return CloudLLMClient(gemini_api_key)
    elif llm_provider == "local":
        local_llm_endpoint = os.getenv("LOCAL_LLM_ENDPOINT", "http://localhost:8000/v1") # Default if not set
        print(f"Using Local LLM provider with endpoint: {local_llm_endpoint}")
        return LocalLLMClient(local_llm_endpoint)
    else:
        raise LLMError(f"Unsupported LLM_PROVIDER: {llm_provider}. Must be 'cloud' or 'local'.")

# Global client instance obtained at module import time
client = get_llm_client()

def call_llm(model_name: str, temperature: float, prompt: str) -> str:
    """
    Calls the configured LLM client to generate content based on a prompt.

    Args:
        model_name (str): The name of the LLM model to use (e.g., 'gemini-pro', 'codegemma:7b').
        temperature (float): The generation temperature to control creativity (0.0 to 1.0).
        prompt (str): The input prompt for the LLM.

    Returns:
        str: The generated text content from the LLM.

    Raises:
        LLMError: If the LLM call fails for any reason.
    """
    try:
        response = client.generate_content(
            model_name=model_name,
            contents=[prompt],
            generation_config={"temperature": temperature}
        )
        # Extract and return the generated text from the response
        return response.candidates[0].content.parts[0].text.strip()
    except Exception as e:
        raise LLMError(f"Failed to call LLM: {e}") from e

