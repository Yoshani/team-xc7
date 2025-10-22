import traceback # Import added for detailed error reporting
from groq import Groq
from tdp_secrets import GROQ_API_KEY

LLM_MODEL = "llama-3.3-70b-versatile"
LLM_TEMPERATURE = 0.2
LLM_MAX_TOKENS = 1024

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
        # Check if the response structure is as expected
        if completion.choices and completion.choices[0].message:
             return completion.choices[0].message.content.strip()
        else:
            # Handle unexpected response structure
            print("!!!!!!!!!!!!!! UNEXPECTED GROQ API RESPONSE STRUCTURE !!!!!!!!!!!!!!")
            print(f"Response Object: {completion}")
            print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            return '{"suggestions": []}' # Fallback empty JSON

    except Exception as e:
        # --- DEBUGGING ADDED HERE ---
        print(f"!!!!!!!!!!!!!! ERROR CALLING GROQ API !!!!!!!!!!!!!!")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Details: {e}")
        traceback.print_exc() # Prints the full stack trace
        print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        # --- END DEBUGGING ---
        return '{"suggestions": []}' # Keep the fallback

