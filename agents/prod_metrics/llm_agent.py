from groq import Groq

from tdp_secrets import GROQ_API_KEY

LLM_MODEL = "openai/gpt-oss-20b"
LLM_TEMPERATURE = 0
LLM_MAX_TOKENS = 512
LLM_TOP_P = 1
LLM_REASONING_EFFORT = "medium"

client = Groq(api_key=GROQ_API_KEY)


def get_llm_completion(prompt: str):
    completion = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=LLM_TEMPERATURE,
        max_completion_tokens=LLM_MAX_TOKENS,
        top_p=LLM_TOP_P,
        reasoning_effort=LLM_REASONING_EFFORT,
        stream=False,
    )
    return completion.choices[0].message.content.strip()
