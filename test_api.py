import os
import google.generativeai as genai
from dotenv import load_dotenv

print("Debug: Current working directory:", os.getcwd())
print("Debug: .env file exists:", os.path.exists('.env'))

# Load environment variables
print("\nBefore loading .env:")
print("API_KEY =", os.getenv('GOOGLE_API_KEY'))

load_dotenv()

print("\nAfter loading .env:")
print("API_KEY =", os.getenv('GOOGLE_API_KEY'))

# Configure
api_key = os.getenv('GOOGLE_API_KEY')
print("\nAPI Key being used:", api_key)

genai.configure(api_key=api_key)

try:
    # List available models first
    print("\nTrying to list models...")
    for m in genai.list_models():
        print(m.name)
    
    # Then try to use the model
    model = genai.GenerativeModel('gemini-1.5-pro')
    response = model.generate_content("Say hello!")
    print("\nResponse:")
    print(response.text)

except Exception as e:
    print(f"\nError details:")
    print(f"Type: {type(e).__name__}")
    print(f"Message: {str(e)}")
    print("\nPlease verify:")
    print("1. API key is correct")
    print("2. Gemini API is enabled")
    print("3. Project is properly set up") 