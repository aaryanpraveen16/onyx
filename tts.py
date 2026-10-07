import asyncio
import os
import re
import sys
import tempfile
import uuid
# pyrefly: ignore [missing-import]
import edge_tts
# pyrefly: ignore [missing-import]
import pygame

VOICE = "en-US-GuyNeural"
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"


def extract_sentences(buffer: str):
    """
    Extracts complete sentences ending with '.', '!', '?', or newline from buffer.
    Returns (list_of_completed_sentences, remaining_incomplete_buffer).
    """
    parts = re.split(r'(?<=[.!?\n])\s+', buffer)
    if len(parts) > 1:
        sentences = [p.strip() for p in parts[:-1] if p.strip()]
        remaining = parts[-1]
        return sentences, remaining
    return [], buffer


async def play_sentence_audio(text: str):
    """
    Generates and plays TTS audio for a single sentence chunk in real-time.
    Strips markdown formatting symbols so voice synthesis sounds natural.
    """
    clean_text = re.sub(r'[*#_`~]', '', text).strip()
    if not clean_text:
        return

    temp_file = os.path.join(tempfile.gettempdir(), f"tts_{uuid.uuid4().hex}.mp3")
    try:
        communicate = edge_tts.Communicate(clean_text, VOICE)
        await communicate.save(temp_file)

        if not pygame.mixer.get_init():
            pygame.mixer.init()

        pygame.mixer.music.load(temp_file)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.05)
    except Exception as e:
        print(f"\nTTS Error: {e}")
    finally:
        if pygame.mixer.get_init():
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass


async def stream_tts_from_generator(chunk_generator):
    """
    Streams text chunks from Gemini generator, buffers into sentences,
    and plays TTS audio sentence-by-sentence in real time.
    """
    buffer = ""
    full_text = []

    print("\n--- Gemini Streaming Response (Voice Active) ---")
    for chunk in chunk_generator:
        if not chunk:
            continue

        sys.stdout.write(chunk)
        sys.stdout.flush()

        full_text.append(chunk)
        buffer += chunk

        sentences, buffer = extract_sentences(buffer)
        for sentence in sentences:
            await play_sentence_audio(sentence)

    # Flush remaining text in buffer if any
    if buffer.strip():
        await play_sentence_audio(buffer.strip())

    print("\n------------------------------------------------\n")
    return "".join(full_text)


def play_stream(chunk_generator) -> str:
    """
    Synchronous wrapper to stream text chunks to real-time speech.
    """
    return asyncio.run(stream_tts_from_generator(chunk_generator))
