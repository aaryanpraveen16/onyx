from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import websockets
import asyncio
import json
import os
import sys
from dotenv import load_dotenv

from llm import stream_transcript_to_chat
from tts import stream_tts_from_generator

load_dotenv()

app = FastAPI(title="Real-Time AI Technical Interviewer Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEEPGRAM_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?model=nova-2"
    "&smart_format=true"
    "&encoding=linear16"
    "&sample_rate=16000"
    "&channels=1"
    "&interim_results=true"
)


@app.get("/")
async def root():
    return {"status": "ok", "message": "AI Interviewer Server is running"}


@app.websocket("/interview")
async def interview_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time streaming audio interview.
    Receives audio bytes from frontend, streams to Deepgram STT,
    and returns transcripts and AI voice responses.
    """
    await websocket.accept()
    print("Client connected to /interview WebSocket")

    api_key = os.getenv("DEEPGRAM_API_KEY") or os.getenv("DEEPGRAM_TTS")
    if not api_key:
        print("Error: Deepgram API key missing.")
        await websocket.close(code=1008, reason="Deepgram API key missing")
        return

    headers = {"Authorization": f"Token {api_key}"}
    final_transcripts = []

    try:
        async with websockets.connect(
            DEEPGRAM_URL,
            additional_headers=headers,
            ping_interval=None,
            ping_timeout=None
        ) as dg_ws:
            print("Connected to Deepgram WebSocket")

            dg_send_lock = asyncio.Lock()
            ai_tasks = set()

            async def safe_dg_send(payload):
                async with dg_send_lock:
                    try:
                        await dg_ws.send(payload)
                    except Exception:
                        pass

            async def keep_deepgram_alive():
                """
                Task 1: Sends KeepAlive messages every 3 seconds to Deepgram.
                Guarantees NET-0001 (10s inactivity timeout) is never triggered
                during candidate pauses, browser throttling, or long AI speech.
                """
                try:
                    while True:
                        await asyncio.sleep(3)
                        await safe_dg_send(json.dumps({"type": "KeepAlive"}))
                except (asyncio.CancelledError, websockets.ConnectionClosed):
                    pass
                except Exception as e:
                    print(f"KeepAlive error: {e}")

            async def send_audio_to_deepgram():
                """
                Task 2: Reads binary audio frames from client WebSocket
                and pipes them directly to Deepgram WebSocket.
                """
                try:
                    while True:
                        data = await websocket.receive_bytes()
                        if not data:
                            break
                        await safe_dg_send(data)
                except WebSocketDisconnect:
                    print("Client WebSocket disconnected")
                except Exception as e:
                    print(f"Audio sender error: {e}")
                finally:
                    await safe_dg_send(json.dumps({"type": "CloseStream"}))

            async def process_ai_turn(utterance: str):
                """
                Runs the LLM streaming and TTS playback in a non-blocking task
                so Deepgram WebSocket message receiver is never stalled.
                """
                try:
                    print(f"\n[AI Pipeline] Processing utterance: '{utterance}'")
                    try:
                        await websocket.send_json({
                            "type": "status",
                            "state": "thinking"
                        })
                    except Exception:
                        return

                    generator = stream_transcript_to_chat(utterance)
                    ai_response = await stream_tts_from_generator(generator)

                    try:
                        await websocket.send_json({
                            "type": "ai_response",
                            "text": ai_response
                        })
                    except Exception:
                        pass
                except Exception as err:
                    print(f"AI Pipeline error: {err}")

            async def receive_transcripts_from_deepgram():
                """
                Task 3: Receives transcript responses from Deepgram WebSocket,
                sends transcript status to frontend, and triggers LLM -> TTS pipeline
                when user speech is finalized.
                """
                try:
                    async for message in dg_ws:
                        res = json.loads(message)
                        channel = res.get("channel", {})
                        alternatives = channel.get("alternatives", [])
                        if alternatives:
                            transcript = alternatives[0].get("transcript", "")
                            is_final = res.get("is_final", False)
                            speech_final = res.get("speech_final", False)

                            if transcript:
                                if is_final:
                                    final_transcripts.append(transcript)
                                    print(f"\n[Deepgram Final] {transcript}")
                                    try:
                                        await websocket.send_json({
                                            "type": "transcript",
                                            "is_final": True,
                                            "text": transcript
                                        })
                                    except Exception:
                                        pass
                                else:
                                    sys.stdout.write(f"\r[Deepgram Interim] {transcript}              ")
                                    sys.stdout.flush()
                                    try:
                                        await websocket.send_json({
                                            "type": "transcript",
                                            "is_final": False,
                                            "text": transcript
                                        })
                                    except Exception:
                                        pass

                                # Trigger LLM evaluation when speech segment completes
                                if is_final and speech_final:
                                    full_text = " ".join(final_transcripts).strip()
                                    if full_text:
                                        final_transcripts.clear()
                                        task = asyncio.create_task(process_ai_turn(full_text))
                                        ai_tasks.add(task)
                                        task.add_done_callback(ai_tasks.discard)

                except Exception as e:
                    print(f"\nTranscript receiver error: {e}")

            keepalive_task = asyncio.create_task(keep_deepgram_alive())
            sender_task = asyncio.create_task(send_audio_to_deepgram())
            receiver_task = asyncio.create_task(receive_transcripts_from_deepgram())

            done, pending = await asyncio.wait(
                [sender_task, receiver_task, keepalive_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()
            for task in ai_tasks:
                task.cancel()

    except Exception as e:
        print(f"Interview WebSocket session error: {e}")
    finally:
        print("\nInterview WebSocket session closed.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
