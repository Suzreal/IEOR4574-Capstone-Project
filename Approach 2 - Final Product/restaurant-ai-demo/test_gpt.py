from openai import OpenAI
import os

client = OpenAI()

print("=== Checking OPENAI_API_KEY ===")
print("Key exists:", bool(os.getenv("OPENAI_API_KEY")))

try:
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": "Say hello in one short sentence."}]
    )
    print("API connection SUCCESS!")
    print("Model reply:", response.choices[0].message["content"])
except Exception as e:
    print("API connection FAILED!")
    print("Error:", e)
