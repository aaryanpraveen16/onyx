import os
# pyrefly: ignore [missing-import]
from google import genai
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

def generate_response(prompt: str) -> str:
    """
    Send text to Google Gemini (gemini-2.5-flash) using the google-genai SDK 
    and print the text response.
    """
    # The SDK automatically picks up GEMINI_API_KEY from the environment variables
    client = genai.Client()
    
    print("Generating response from Gemini...")
    try:
        # Use gemini-3.8-flash as gemini-2.5-flash is deprecated
        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt,
        )
        
        print("\n--- Gemini Response ---")
        print(response.text)
        print("-----------------------\n")
        
        return response.text
    
    except Exception as e:
        print(f"Error during Gemini API request: {e}")
        return ""

if __name__ == "__main__":
    # Test the function
    generate_response("Hello, you are an AI interviewer. Are you ready for a practice question?")
