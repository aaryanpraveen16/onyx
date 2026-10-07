from dotenv import load_dotenv
import os
import json
import asyncio
import sys
import pyaudio
import websockets
from llm import send_transcript_to_chat

load_dotenv()

# Audio capture configuration (16kHz, mono, 16-bit PCM)
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 2048

async def transcribe_live_websocket() -> str:
    """
    Streams live microphone audio over WebSockets to the Deepgram API
    and prints transcripts in real-time as they arrive.
    """
    api_key = os.getenv("DEEPGRAM_API_KEY") or os.getenv("DEEPGRAM_TTS")
    if not api_key:
        print("Error: Deepgram API key not found. Please set DEEPGRAM_API_KEY in your .env file.")
        return ""

    url = (
        "wss://api.deepgram.com/v1/listen"
        "?model=nova-2"
        "&smart_format=true"
        "&encoding=linear16"
        "&sample_rate=16000"
        "&channels=1"
        "&interim_results=true"
    )
    headers = {"Authorization": f"Token {api_key}"}

    audio = pyaudio.PyAudio()
    try:
        stream = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
    except Exception as e:
        print(f"Error opening microphone stream: {e}")
        audio.terminate()
        return ""

    stop_event = asyncio.Event()
    final_transcripts = []

    print("\nConnecting to Deepgram WebSocket...")
    try:
        async with websockets.connect(url, additional_headers=headers) as ws:
            print("Connected!")
            print("🎙  Listening... Speak into your microphone.")
            print("--> Press ENTER to stop recording <--\n")

            async def send_audio():
                while not stop_event.is_set():
                    data = await asyncio.to_thread(stream.read, CHUNK, exception_on_overflow=False)
                    await ws.send(data)
                
                # Signal Deepgram that the audio stream is complete
                await ws.send(json.dumps({"type": "CloseStream"}))

            async def receive_transcripts():
                async for message in ws:
                    try:
                        res = json.loads(message)
                        channel = res.get("channel", {})
                        alternatives = channel.get("alternatives", [])
                        if alternatives:
                            transcript = alternatives[0].get("transcript", "")
                            is_final = res.get("is_final", False)
                            
                            if transcript:
                                if is_final:
                                    final_transcripts.append(transcript)
                                    print(f"\r[Final] {transcript}")
                                else:
                                    sys.stdout.write(f"\r[Interim] {transcript}                      ")
                                    sys.stdout.flush()
                    except Exception as err:
                        print(f"\nError processing transcript frame: {err}")

            async def wait_for_stop():
                await asyncio.to_thread(input)
                stop_event.set()

            sender_task = asyncio.create_task(send_audio())
            receiver_task = asyncio.create_task(receive_transcripts())
            input_task = asyncio.create_task(wait_for_stop())

            # Wait for user to press ENTER
            await input_task
            print("\nStopping audio stream and finalizing transcription...")
            
            await sender_task
            await receiver_task

    except Exception as e:
        print(f"\nWebSocket connection error: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()

    full_transcript = " ".join(final_transcripts).strip()
    
    print("\n--- Final Transcript ---")
    print(full_transcript if full_transcript else "(No speech detected)")
    print("------------------------\n")
    
    return full_transcript


def transcribe_wav(file_path: str):
    """
    Fallback function: Send a WAV file to Deepgram REST API and print transcribed text.
    """
    import requests
    api_key = os.getenv("DEEPGRAM_API_KEY") or os.getenv("DEEPGRAM_TTS")
    if not api_key:
        print("Error: Deepgram API key not found. Please set DEEPGRAM_API_KEY in your .env file.")
        return ""

    url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true"
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "audio/wav"
    }

    print(f"Transcribing {file_path} via REST API...")
    try:
        with open(file_path, "rb") as audio_file:
            response = requests.post(url, headers=headers, data=audio_file)
        response.raise_for_status()
        result = response.json()
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
    except Exception as e:
        print(f"Error during REST API transcription: {e}")
        return ""


if __name__ == "__main__":
    transcript = asyncio.run(transcribe_live_websocket())
    
    if transcript:
        print("\nSending transcript to persistent Gemini chat session...")
        send_transcript_to_chat(transcript)




