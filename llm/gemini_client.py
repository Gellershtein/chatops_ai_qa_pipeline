import os
from dotenv import load_dotenv
from google import genai # Correct import

load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")

# Initialize client once with API key
client = genai.Client(api_key=gemini_api_key)

def call_llm(model_name: str, temperature: float, prompt: str):
    response = client.models.generate_content(
        model=model_name,
        contents=[prompt]
    )
    return response.candidates[0].content.parts[0].text.strip()