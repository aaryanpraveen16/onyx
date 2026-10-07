import os
import sys
import time
# pyrefly: ignore [missing-import]
from google import genai
# pyrefly: ignore [missing-import]
from google.genai import types
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
from tts import play_stream

load_dotenv()

_client = None
_chat_session = None
_current_model_idx = 0
AVAILABLE_MODELS = ["gemini-3.8-flash"]


def get_chat_session(force_new: bool = False):
    """
    Returns or initializes a persistent chat session using the google-genai SDK.
    """
    global _client, _chat_session, _current_model_idx
    if _client is None:
        _client = genai.Client()

    if _chat_session is None or force_new:
        model_name = AVAILABLE_MODELS[_current_model_idx % len(AVAILABLE_MODELS)]
        system_instruction = (
            "You are an expert AI software engineering interviewer. "
            "Evaluate candidate answers constructively, keep responses concise for voice output, "
            "maintain context across the conversation history, and ask relevant follow-up questions."
        )
        _chat_session = _client.chats.create(
            model=model_name,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction
            )
        )
    return _chat_session


def stream_transcript_to_chat(transcript: str, max_retries: int = 3):
    """
    Generator that streams text chunks from the persistent Gemini chat session.
    Automatically retries with exponential backoff on temporary API load spikes.
    """
    prompt = (
        f"Candidate Answer: \"{transcript}\"\n\n"
        "Please evaluate this candidate's answer concisely. Provide key strengths, "
        "any missing details, and an appropriate follow-up question."
    )

    for attempt in range(max_retries):
        chat = get_chat_session()
        try:
            response_stream = chat.send_message_stream(prompt)
            has_yielded = False
            for chunk in response_stream:
                if chunk.text:
                    has_yielded = True
                    yield chunk.text
            if has_yielded:
                return
        except Exception as e:
            print(f"\nStream attempt {attempt + 1} with {AVAILABLE_MODELS[_current_model_idx]} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))


def send_transcript_to_chat(transcript: str) -> str:
    """
    Sends the STT transcript into the persistent chat session and streams
    text chunks directly to real-time sentence-level TTS.
    """
    generator = stream_transcript_to_chat(transcript)
    return play_stream(generator)


if __name__ == "__main__":
    print("Testing persistent streaming chat session using google-genai SDK...")
    send_transcript_to_chat("I prefer using HashMaps for O(1) average lookup time in Python using dictionaries.")

