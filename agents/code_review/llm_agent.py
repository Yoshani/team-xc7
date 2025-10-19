from groq import Groq
from tdp_secrets import GROQ_API_KEY

# We are choosing a more powerful model for the complex task of code review.
# Llama3-70b is one of the best available models on Groq for reasoning.
LLM_MODEL = "llama3-70b-8192"
LLM_TEMPERATURE = 0.2  # We want creative but still factual suggestions
LLM_MAX_TOKENS = 1024  # Give it enough space for detailed suggestions

client = Groq(api_key=GROQ_API_KEY)

def get_llm_completion(prompt: str):
    """Sends a prompt to the Groq API and returns the text response."""
    try:
        completion = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            stream=False,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling Groq API: {e}")
        return '{"suggestions": []}' # Return empty JSON on error