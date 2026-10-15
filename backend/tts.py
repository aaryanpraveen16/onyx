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
    Streams text chunks from Gemini generator, captures the full text for the chat UI,
    but only sends the spoken sentence(s) after 'Follow-up Question:' to TTS.
    Filters out Evaluation, Strengths, markdown symbols, and internal notes from voice playback.
    """
    voice_buffer = ""
    full_text = []
    speech_active = False
    question_regex = re.compile(
        r'(?:\*\*|\#\#)?\s*(?:follow-?up\s*(?:question)?|question)\s*:\s*(?:\*\*|\#\#)?',
        re.IGNORECASE
    )

    async def iterate_chunks():
        if hasattr(chunk_generator, '__anext__'):
            async for ch in chunk_generator:
                yield ch
        else:
            for ch in chunk_generator:
                yield ch

    print("\n--- Gemini Streaming Response (Voice Filtered for Spoken Question) ---")
    async for chunk in iterate_chunks():
        if not chunk:
            continue

        sys.stdout.write(chunk)
        sys.stdout.flush()

        full_text.append(chunk)

        if not speech_active:
            voice_buffer += chunk
            match = question_regex.search(voice_buffer)
            if match:
                speech_active = True
                # Discard everything before and including the follow-up question label
                voice_buffer = voice_buffer[match.end():]
        else:
            voice_buffer += chunk

        if speech_active:
            sentences, voice_buffer = extract_sentences(voice_buffer)
            for sentence in sentences:
                await play_sentence_audio(sentence)

    # Flush any remaining sentence for voice
    if speech_active and voice_buffer.strip():
        await play_sentence_audio(voice_buffer.strip())
    elif not speech_active:
        # Fallback if the model did not output the standard header:
        # Strip markdown headers/evaluations and play whatever question or text remains
        fallback_text = "".join(full_text)
        clean_fallback = re.sub(
            r'(?i)\*?\*?(?:evaluation|strengths?|weaknesses?)\*?\*?:?[^\n]*\n?',
            '',
            fallback_text
        )
        clean_fallback = re.sub(r'[*#_`~]', '', clean_fallback).strip()
        if clean_fallback:
            sentences, rem = extract_sentences(clean_fallback)
            for s in sentences:
                await play_sentence_audio(s)
            if rem.strip():
                await play_sentence_audio(rem.strip())

    print("\n----------------------------------------------------------------------\n")
    return "".join(full_text)


def play_stream(chunk_generator) -> str:
    """
    Synchronous wrapper to stream text chunks to real-time speech.
    """
    return asyncio.run(stream_tts_from_generator(chunk_generator))
