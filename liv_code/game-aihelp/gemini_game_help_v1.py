import os
import google.generativeai as genai

# Best Practice: Set this in your environment variables instead of hardcoding.
# In PowerShell: $env:GEMINI_API_KEY="your_new_key_here"
# Or just replace the string below for local testing (but don't share it!).
os.environ["GEMINI_API_KEY"] = "AIzaSyDioYIqPW1Eh0LyVAMxdBKSS6MIQSWNQJc"

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        return

    genai.configure(api_key=api_key)

    # Try to use the model
    try:
        # 'gemini-1.5-flash' is the correct stable model name
        #model = genai.GenerativeModel("gemini-1.5-flash")

        # Updated to the available 2.5 version from your list
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        prompt = (
            'How can I achieve the following goal in the standard The Witcher 3(Wild Hunt)?Please answer in as few words as possible. I am using Microsoft controller along with keyboard and mouse.: '
            'I wish to jump using controller.'
        )
        
        print("Sending request to Google AI...")
        response = model.generate_content(prompt)
        
        print("\n=== Google AI Response ===")
        print(response.text)

    except Exception as e:
        print(f"\nError encountered: {e}")
        
        # Troubleshooting: List available models to verify access
        print("\n--- Troubleshooting: Available Models ---")
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    print(f"- {m.name}")
        except Exception as list_e:
            print(f"Could not list models: {list_e}")

if __name__ == "__main__":
    main()