import os
import google.generativeai as genai

# Expect GEMINI_API_KEY to be set in environment
# PowerShell example:  $env:GEMINI_API_KEY="your_api_key"

def check_sentence(sentence: str) -> str:
    """
    Sends a sentence to Gemini for grammar checking and improvement.
    Returns the model's text response.
    """

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Error: GEMINI_API_KEY environment variable not set."

    genai.configure(api_key=api_key)

    try:
        # Using your working model
        model = genai.GenerativeModel("gemini-2.5-flash")

        prompt = (
            "Is the following sentence grammatically correct, and how can it be improved?\n"
            f"Sentence: {sentence}"
        )

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        return f"Error while calling Gemini: {e}"
