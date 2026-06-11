import os
from dotenv import load_dotenv

load_dotenv()

# gemini
API_KEY    = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
CHUNK_SIZE = 12000

# ollama
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

# whisper
WHISPER_MODEL        = os.getenv("WHISPER_MODEL", "large-v3")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8_float16")
WHISPER_BEAM_SIZE    = int(os.getenv("WHISPER_BEAM_SIZE", "5"))
TRANSCRIPTION_LANG   = os.getenv("TRANSCRIPTION_LANG", "fa")

# pipeline behavior
KEEP_AUDIO    = os.getenv("KEEP_AUDIO", "true").lower() == "true"



''' models to use:
gemini-3-flash-preview ~50b
gemini-2.5-flash ~5b
gemini-2.5-flash-lite ~1b
'''
