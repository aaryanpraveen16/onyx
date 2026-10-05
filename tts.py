import asyncio
# pyrefly: ignore [missing-import]
import edge_tts
# pyrefly: ignore [missing-import]
import pygame
import os

# Default voice, can be changed. "en-US-GuyNeural" is a good male voice, "en-US-JennyNeural" is a good female voice.
VOICE = "en-US-GuyNeural"
OUTPUT_FILE = "response.mp3"

async def _generate_and_play(text: str):
    print(f"\nGenerating TTS...")
    communicate = edge_tts.Communicate(text, VOICE)
    
    # Save the generated audio to an MP3 file
    await communicate.save(OUTPUT_FILE)
    
    print("Playing TTS...")
    # Initialize pygame mixer and play the file
    pygame.mixer.init()
    pygame.mixer.music.load(OUTPUT_FILE)
    pygame.mixer.music.play()
    
    # Wait until the audio finishes playing
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)
        
    pygame.mixer.quit()
    
    # Clean up the audio file after playing
    if os.path.exists(OUTPUT_FILE):
        try:
            os.remove(OUTPUT_FILE)
        except Exception as e:
            print(f"Warning: Could not remove {OUTPUT_FILE}: {e}")

def play_text(text: str):
    """
    Synchronous wrapper to generate and play TTS audio using edge-tts and pygame.
    """
    # Disable pygame's welcome prompt
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
    asyncio.run(_generate_and_play(text))

if __name__ == "__main__":
    play_text("Hello! This is a test of the Edge TTS integration. I am ready to conduct the interview.")
