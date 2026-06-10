import sys
from pathlib import Path


ENV_PATH = Path(__file__).parent / ".env"


# ── api key validator ──
def validate_gemini_key(api_key: str) -> bool:
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        list(client.models.list())
        return True
    except Exception:
        return False


# ── gemini setup ──
def ask_gemini() -> str:
    print("\nEnter Your Gemini API Key.")
    print("Get One Free At: https://aistudio.google.com/apikey")
    while True:
        key = input("> ").strip()
        if not key:
            print("API Key Cannot Be Empty, Try Again.")
            continue
        print("Validating Key...")
        if validate_gemini_key(key):
            print("API Key Is Valid.")
            return key
        else:
            print("Invalid API Key Or No Internet Connection. Try Again.")


def ask_gemini_model() -> str:
    print("\nWhich Gemini Model Do You Want To Use?")
    print("  1) gemini-2.5-flash      (Recommended, Fast)")
    print("  2) gemini-2.5-flash-lite (Lighter, Cheaper)")
    print("  3) Enter Custom Model Name")
    choice = input("> ").strip()

    if choice == "1" or choice == "":
        return "gemini-2.5-flash"
    elif choice == "2":
        return "gemini-2.5-flash-lite"
    elif choice == "3":
        name = input("Model Name:\n> ").strip()
        return name if name else "gemini-2.5-flash"
    else:
        print("Invalid Choice, Defaulting To gemini-2.5-flash.")
        return "gemini-2.5-flash"


# ── ollama setup ──
def ask_ollama_model() -> str:
    print("\nEnter Your Ollama Model Name For Offline Use.")
    print("Examples: llama3.2:3b, llama3.1:8b, mistral:7b")
    print("Press Enter To Skip If You Don't Use Ollama.")
    model = input("> ").strip()
    return model if model else "llama3.2:3b"


# ── env writer ──
def write_env(api_key: str, gemini_model: str, ollama_model: str):
    content = f"""# Gemini
GEMINI_API_KEY={api_key}
GEMINI_MODEL={gemini_model}

# Ollama (local fallback)
OLLAMA_MODEL={ollama_model}

# Whisper
WHISPER_MODEL=large-v3
WHISPER_COMPUTE_TYPE=int8_float16
WHISPER_BEAM_SIZE=5

# Pipeline
TRANSCRIPTION_LANG=fa
KEEP_AUDIO=true
"""
    ENV_PATH.write_text(content, encoding="utf-8")
    print(f"\nSaved To {ENV_PATH}")


# ── main setup flow ──
def main():
    print("=== Scribe — First Time Setup ===")

    if ENV_PATH.exists():
        print(f"\n.env Already Exists At {ENV_PATH}")
        overwrite = input("Overwrite It? [y/N] ").strip().lower()
        if overwrite != "y":
            print("Setup Cancelled.")
            sys.exit(0)

    api_key      = ask_gemini()
    gemini_model = ask_gemini_model()
    ollama_model = ask_ollama_model()

    write_env(api_key, gemini_model, ollama_model)

    print("\nSetup Complete. You Can Now Run:")
    print("  python main.py")


if __name__ == "__main__":
    main()
