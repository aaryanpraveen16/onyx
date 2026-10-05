# Project: Real-Time AI Technical Interviewer (Voice Agent)

## Project Overview
A real-time, ultra-low latency voice agent that conducts software engineering and system design mock interviews. The system must support full-duplex conversational audio and handle user barge-in (interruption) with sub-500ms latency.

## Architecture & Tech Stack
- **Frontend:** Next.js (React/TypeScript) utilizing LiveKit React components to handle WebRTC microphone capture and audio playback.
- **Backend Orchestrator:** Python using the core `livekit-api` and `livekit.rtc` SDKs.
  - *Strict Constraint:* Do NOT use the `livekit-agents` framework. The orchestrator must manually handle WebRTC audio streams, async queues, and buffer management from first principles.
- **Speech-to-Text (STT):** Deepgram (REST for V1, WebSockets for V2).
- **LLM / Intelligence:** Google Gemini (`gemini-3.8-flash`) via the `google-genai` SDK.
- **Text-to-Speech (TTS):** Microsoft Edge TTS (`edge-tts`).

## Data & Audio Specifications
- **Audio Format:** Strictly 16kHz, 1-channel (Mono), 16-bit PCM.
- **Network Protocol:** LiveKit SFU (WebRTC) handles the client-to-server connection. The Python backend communicates with AI APIs via WebSockets and REST.
- **State Management:** In-memory Python list for conversation history. No database required for V1.

## Development Milestones
The AI assistant must strictly follow these milestones and NOT attempt to build the entire system at once. Only provide code for the requested milestone.

- **Milestone 1 (Local Sync Loop):** Use `pyaudio` to record a local `.wav` file -> Deepgram REST API -> Gemini LLM -> Edge TTS -> Play local `.wav`/`.mp3` file.
- **Milestone 2 (Local Async Stream):** Upgrade Milestone 1 to use `asyncio`, swapping Deepgram to its WebSocket stream and chunking Edge TTS playback.
- **Milestone 3 (LiveKit Backend):** Replace `pyaudio` with `livekit.rtc`. The Python script joins a LiveKit room, intercepts remote audio tracks, runs the AI loop, and publishes synthetic audio back to a virtual `AudioSource`.
- **Milestone 4 (Next.js Frontend):** Build the React UI to request microphone permissions, fetch a LiveKit token, and connect the human user to the LiveKit Room.
- **Milestone 5 (Barge-in):** Implement Silero VAD in the Python loop to detect human speech and instantly flush the TTS AsyncIO playback queue.