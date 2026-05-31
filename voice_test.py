"""Test voice synthesis with proper error handling."""
import asyncio
import os
import sys


async def test_voice():
    """Test edge-tts functionality."""
    try:
        import edge_tts
        print("✓ edge-tts installed")
    except ImportError:
        print("✗ edge-tts not installed. Run: pip install edge-tts")
        return

    try:
        from voice import synthesize_stream, is_available
        if not is_available():
            print("✗ Voice synthesis not available")
            return

        print("Testing voice synthesis...")
        text = "Hello Rayen, this is a test of the voice system."
        chunks = []
        async for chunk in synthesize_stream(text, lang="en"):
            chunks.append(chunk)
        print(f"✓ Generated {len(chunks)} audio chunks")

    except Exception as e:
        print(f"✗ Error: {e}")
        return


if __name__ == "__main__":
    asyncio.run(test_voice())
