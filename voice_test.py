import asyncio
import edge_tts
import pygame
import tempfile
import os

async def speak(text, voice="en-US-GuyNeural"):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
        temp_file = f.name

    await edge_tts.Communicate(text, voice).save(temp_file)

    pygame.mixer.init()
    pygame.mixer.music.load(temp_file)
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        await asyncio.sleep(0.1)

    pygame.mixer.quit()
    os.remove(temp_file)

asyncio.run(speak("Hello Rayen"))