from pathlib import Path


# project root — wherever this file sits
ROOT = Path(__file__).parent

# directories
DOWNLOADS_DIR = ROOT / "downloads"
MODELS_DIR    = ROOT / "models"
PIPELINE_DIR  = ROOT / "pipeline"
SESSIONS_DIR  = ROOT / "sessions"

# dll locations
PROJECT_DLLS   = ROOT
CTRANSLATE_DIR = ROOT / ".venv" / "Lib" / "site-packages" / "ctranslate2"

# temp files — used during processing then moved to session folder
AUDIO_PATH  = DOWNLOADS_DIR / "audio.mp3"
ZIP_PATH    = DOWNLOADS_DIR / "recording.zip"
EXTRACT_DIR = DOWNLOADS_DIR / "extracted"

# default output files (overridden by session paths in main.py)
TRANSCRIPT = ROOT / "transcript.txt"
SUMMARY    = ROOT / "summary.md"


# shamsi date validator
def validate_shamsi_date(date_str: str) -> bool:
    """Validate a Shamsi date string in the format YYYY-MM-DD."""
    try:
        import jdatetime
        parts = date_str.strip().split("-")
        if len(parts) != 3:
            return False
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        jdatetime.date(y, m, d)
        return True
    except Exception:
        return False


# course name prompt
def ask_course() -> str:
    print("\nWhat Course Is This?")
    while True:
        course = input("> ").strip().lower()
        if not course:
            print("Course Name Cannot Be Empty, Try Again.")
            continue
        if not all(ord(c) < 128 for c in course):
            print("Please Use English For The Course Name.")
            continue
        return course


# shamsi date prompt
def ask_shamsi_date() -> str:
    print("\nWhat Was The Date Of This Class? (Shamsi, e.g. 1404-02-30)")
    while True:
        date_str = input("> ").strip()
        if not date_str:
            print("Date Cannot Be Empty, Try Again.")
            continue
        if validate_shamsi_date(date_str):
            return date_str
        else:
            print("Invalid Shamsi Date. Please Use The Format YYYY-MM-DD (e.g. 1404-02-30)")


# session folder creator
def create_session_folder() -> Path:
    """
    Prompts for course name and Shamsi date, then creates and returns:
    sessions/operating-systems/1404-02-30/
    """
    course = ask_course()

    # sanitize course name — spaces to hyphens, remove special chars
    clean_course = "".join(c if c.isalnum() or c in " -_" else "" for c in course)
    clean_course = clean_course.replace(" ", "-")

    shamsi_date = ask_shamsi_date()

    session_path = SESSIONS_DIR / clean_course / shamsi_date
    session_path.mkdir(parents=True, exist_ok=True)

    return session_path
