import os
from dotenv import load_dotenv
from openai import OpenAI

print("=== Testing OpenAI API Key Connection ===")

# load .env
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
print("Loaded OPENAI_API_KEY:", OPENAI_API_KEY[:10] + "..." if OPENAI_API_KEY else None)

if not OPENAI_API_KEY:
    print("❌ No OPENAI_API_KEY found in environment!")
    exit()

# initialize client
client = OpenAI(api_key=OPENAI_API_KEY)

# test simple request
try:
    print("Sending test request...")
    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "user", "content": "Say 'test successful'."}
        ],
        max_completion_tokens=20
    )

    print("✅ OpenAI connection successful!")
    print("Model response:", completion.choices[0].message.content)

except Exception as e:
    print("❌ OpenAI connection failed.")
    print("Error:", repr(e))
