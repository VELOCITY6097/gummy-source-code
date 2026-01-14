import google.generativeai as genai

# Paste your Gemini API key here
GEMINI_KEY = "AIzaSyANChpishR7J-7g4xrTgY8cSEkdw3A8S1U"

# Configure the Gemini SDK
genai.configure(api_key=GEMINI_KEY)

# List available models
models = list(genai.list_models())

print("Available Gemini Models:\n")
for m in models:
    print(m)
