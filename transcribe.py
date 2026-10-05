import os
import requests
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
from llm import generate_response
from tts import play_text

load_dotenv()

def transcribe_wav(file_path: str):
    """
    Send a WAV file to Deepgram REST API and print the transcribed text.
    """
    # We check for DEEPGRAM_TTS or DEEPGRAM_API_KEY
    api_key = os.getenv("DEEPGRAM_API_KEY") or os.getenv("DEEPGRAM_TTS")
    
    if not api_key:
        print("Error: Deepgram API key not found. Please set DEEPGRAM_API_KEY in your .env file.")
        return
    
    # We use nova-2, which is their best model currently
    url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true"
    
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "audio/wav"
    }
    
    print(f"Transcribing {file_path}...")
    try:
        with open(file_path, "rb") as audio_file:
            response = requests.post(url, headers=headers, data=audio_file)
            
        # Raise an exception for bad status codes
        response.raise_for_status()
        
        result = response.json()
        
        # Safely extract the transcript from the JSON response
        transcript = (
            result.get("results", {})
            .get("channels", [{}])[0]
            .get("alternatives", [{}])[0]
            .get("transcript", "")
        )
        
        print("\n--- Transcript ---")
        print(transcript)
        print("------------------\n")
        
        return transcript
        
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
    except requests.exceptions.RequestException as e:
        print(f"Error during Deepgram API request: {e}")
        if 'response' in locals() and response is not None:
            print(f"Details: {response.text}")

if __name__ == "__main__":
    # Test the function with the sample.wav present in the directory
    sample_file_path = "sample.wav"
    if os.path.exists(sample_file_path):
        transcript = transcribe_wav(sample_file_path)
        if transcript:
            prompt = f"You are an AI software engineering interviewer. The candidate said: '{transcript}'. How do you respond briefly?"
            llm_response = generate_response(prompt)
            if llm_response:
                play_text(llm_response)
    else:
        print(f"Warning: {sample_file_path} does not exist in the current directory.")
