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
AVAILABLE_MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite"]


def get_chat_session(force_new: bool = False):
    """
    Returns or initializes a persistent async chat session using client.aio.
    """
    global _client, _chat_session, _current_model_idx
    if _client is None:
        _client = genai.Client()

    if _chat_session is None or force_new:
        model_name = AVAILABLE_MODELS[_current_model_idx % len(AVAILABLE_MODELS)]
        system_instruction = (
            "You are an expert AI technical interviewer conducting a live voice interview.\n\n"
            "STRUCTURE YOUR RESPONSE IN EXACTLY THIS FORMAT FOR EVERY TURN:\n"
            "Evaluation: <1-2 concise sentences assessing the candidate's answer, highlighting strengths and any technical gaps.>\n"
            "Follow-up Question: <A single, conversational follow-up question spoken directly to the candidate to probe deeper or move to the next technical topic.>\n\n"
            "CRITICAL RULES:\n"
            "1. Always include the exact labels 'Evaluation:' and 'Follow-up Question:'.\n"
            "2. Keep the Follow-up Question natural and conversational, as it will be spoken aloud to the candidate.\n"
            "3. Do not use asterisks or bullet lists around the labels."
        )
        _chat_session = _client.aio.chats.create(
            model=model_name,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction
            )
        )
    return _chat_session


async def stream_transcript_to_chat(transcript: str, max_retries: int = 3):
    """
    Asynchronous generator that streams text chunks from the persistent Gemini chat session
    without blocking the asyncio event loop.
    """
    global _current_model_idx
    prompt = (
        f"Candidate Answer: \"{transcript}\"\n\n"
        "Remember to respond strictly using this format:\n"
        "Evaluation: <brief assessment>\n"
        "Follow-up Question: <conversational follow-up question to speak to candidate>"
    )

    for attempt in range(max_retries):
        chat = get_chat_session()
        try:
            response_stream = await chat.send_message_stream(prompt)
            has_yielded = False
            async for chunk in response_stream:
                if chunk.text:
                    has_yielded = True
                    yield chunk.text
            if has_yielded:
                return
        except Exception as e:
            current_model = AVAILABLE_MODELS[_current_model_idx % len(AVAILABLE_MODELS)]
            print(f"\nStream attempt {attempt + 1} with {current_model} failed: {e}")
            _current_model_idx += 1
            get_chat_session(force_new=True)
            if attempt < max_retries - 1:
                await asyncio.sleep(1)



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

