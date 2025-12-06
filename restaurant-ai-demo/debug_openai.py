import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
print("DEBUG OPENAI_API_KEY loaded:", bool(api_key))

client = OpenAI(api_key=api_key)

resp = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Give me 3 signature dishes of a typical Japanese restaurant."},
    ],
    max_completion_tokens=150,
)

print("Response text:\n", resp.choices[0].message.content)
