import logging
import shutil
import sys
from pathlib import Path
import os
import time
try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

# path setup
sys.path.insert(0, str(Path(__file__).parent))
from paths import SESSIONS_DIR, create_session_folder
from pipeline import download_lecture, load_model, transcribe
from pipeline.summarize_file import run_pipeline, has_internet
from pipeline.query import query_single_session, query_entire_course


# logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# custom exception for user cancellation
class UserCancelled(Exception):
    pass


# ── helpers ──
def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def pause():
    input("\nPress Enter To Continue...")


# ── guards ──
def check_setup():
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        print("No .env file found. Please run setup first:")
        print("  python setup.py")
        sys.exit(1)


# ── session metadata ──
def save_session_metadata(session_dir: Path, url: str, model_used: str):
    import json
    from datetime import datetime
    metadata = {
        "url":        url,
        "date":       datetime.now().strftime("%Y-%m-%d %H:%M"),
        "model":      model_used,
        "transcript": str(session_dir / "transcript.txt"),
        "summary":    str(session_dir / "summary.md"),
        "audio":      str(session_dir / "audio.mp3"),
    }
    path = session_dir / "session.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    logging.info(f"Session Metadata Saved → {path}")

    # prepend course + date title to summary
    session_summary = session_dir / "summary.md"
    if session_summary.exists():
        shamsi_date = session_dir.name
        course      = session_dir.parent.name
        title = f"# {course} — {shamsi_date}\n\n"
        summary_content = session_summary.read_text(encoding="utf-8")
        session_summary.write_text(title + summary_content, encoding="utf-8")


# ── existing summary check ──
def check_existing_summary(summary_path: Path) -> Path | None:
    """
    If a summary already exists, ask user whether to overwrite,
    save as new file, or cancel.
    """
    if summary_path.exists():
        print(f"\nA Summary Already Exists At:\n  {summary_path}")
        print("\n  1) Overwrite It")
        print("  2) Save As New Summary")
        print("  0) Cancel")
        choice = input("\n> ").strip()
        if choice == "1":
            return summary_path
        elif choice == "2":
            from datetime import datetime
            timestamp = datetime.now().strftime("%H-%M")
            new_path = summary_path.parent / f"summary_{timestamp}.md"
            return new_path
        else:
            print("Cancelled. Existing Summary Kept.")
            return None
    return summary_path


# ── completion screen ──
def show_completion(session_dir: Path):
    clear()
    shamsi_date = session_dir.name
    course      = session_dir.parent.name
    summary     = session_dir / "summary.md"

    print("═" * 45)
    print("\n  Done ✔\n")
    print(f"  Course  : {course}")
    print(f"  Date    : {shamsi_date}")
    print(f"  Summary : {summary}\n")
    print("═" * 45)
    print("\n  1) Open Summary")
    print("  2) Process Another Recording")
    print("  3) Back To Main Menu\n")

    # flush buffered keystrokes before waiting for input
    time.sleep(0.2)
    if HAS_MSVCRT:
        # Windows — flush buffered keystrokes
        while msvcrt.kbhit():
            msvcrt.getch()
    else:
        # Mac/Linux — flush stdin using termios
        try:
            import termios
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except Exception:
            pass

    while True:
        choice = input("> ").strip()

        if choice == "1":
            os.startfile(str(summary))
            print("  Summary Opened. Choose An Option To Continue:")
        elif choice == "2":
            process_new_recording()
            break
        elif choice == "3":
            break
        else:
            print("Invalid Choice.")


# ── option 1: process new recording ──
def process_new_recording():
    url = input("\nPaste The Recording URL:\n> ").strip()
    if not url:
        print("No URL Provided. Returning To Menu.")
        return

    session_dir = None
    try:
        logging.info("Starting Pipeline")

        # step 1 — download and extract audio
        audio_path = download_lecture(url)
        logging.info(f"Download Complete → {audio_path}")

        # step 2 — ask for course and date, create session folder
        session_dir = create_session_folder()
        logging.info(f"Session Folder → {session_dir}")

        # define session file paths
        session_audio      = session_dir / "audio.mp3"
        session_transcript = session_dir / "transcript.txt"
        session_summary    = session_dir / "summary.md"

        # move audio into session folder
        shutil.move(str(audio_path), str(session_audio))
        logging.info(f"Audio Moved → {session_audio}")

        # step 3 — transcribe
        model = load_model()
        transcribe(model, str(session_audio), str(session_transcript))
        logging.info(f"Transcription Complete → {session_transcript}")

        # step 4 — summarize using default structured prompt
        run_pipeline(str(session_transcript), str(session_summary))
        logging.info(f"Summarization Complete → {session_summary}")

        # step 5 — save metadata and prepend title
        model_used = "gemini" if has_internet() else "ollama"
        save_session_metadata(session_dir, url, model_used)

        # step 6 — remove audio if user configured to save space
        from pipeline.config import KEEP_AUDIO
        if not KEEP_AUDIO and session_audio.exists():
            session_audio.unlink()
            logging.info("Audio Removed (KEEP_AUDIO=false)")

        logging.info(f"Pipeline Finished — Session Saved To: {session_dir}")

        # step 7 — show completion screen
        show_completion(session_dir)

    except ValueError as e:
        # clean user-facing errors — just show the message
        print(f"\n{e}")
        pause()

    except Exception as e:
        err = str(e).lower()
        # connection errors — show friendly message
        if "ssl" in err or "connection" in err or "timeout" in err or "max retries" in err:
            print("\nConnection Error — Could Not Reach The Server.")
            print("  • Check Your VPN / Proxy Is Active")
            print("  • The Server May Be Down Or The Link Expired")
            pause()
            return
        # unexpected errors — show full traceback for debugging
        logging.error(f"Pipeline Failed: {e}")
        import traceback
        traceback.print_exc()

        # only clean up if transcript doesn't exist yet
        # if transcript exists, session has value — don't delete it
        if session_dir and session_dir.exists():
            transcript = session_dir / "transcript.txt"
            if not transcript.exists():
                import shutil as _shutil
                _shutil.rmtree(session_dir)
                logging.info(f"Cleaned Up Incomplete Session Folder: {session_dir}")
            else:
                logging.info(f"Session Folder Kept (Transcript Exists) → {session_dir}")
                print(f"\nPipeline Failed But Transcript Is Saved At:\n  {session_dir / 'transcript.txt'}")
                print("You Can Re-Summarize It From Option 2 In The Menu.")
        pause()


# ── option 2: re-summarize existing session ──
def resummarize():
    print("\nEnter The Session Folder Path:")
    print("Example: sessions/operating-systems/1404-02-30")
    raw = input("> ").strip()

    if not raw:
        return

    session_dir = Path(raw) if Path(raw).is_absolute() else Path(__file__).parent / raw

    if not session_dir.exists():
        print(f"\nSession Folder Not Found. Try Again Or Press Enter To Return To Menu.")
        resummarize()
        return

    transcript = session_dir / "transcript.txt"
    summary    = session_dir / "summary.md"

    if not transcript.exists():
        print(f"No Transcript Found In {session_dir} — Cannot Summarize.")
        pause()
        return

    # check if summary already exists and ask before overwriting
    summary = check_existing_summary(summary)
    if summary is None:
        pause()
        return

    # summarize using default structured prompt
    print(f"\nRe-Summarizing: {transcript}")
    try:
        run_pipeline(str(transcript), str(summary))
        logging.info(f"Summary Saved → {summary}")

        # show completion screen
        show_completion(session_dir)

    except UserCancelled:
        print("\nSummarization Interrupted. Transcript Is Still Saved.")
        print("You Can Re-Summarize Later From Option 2.")
        pause()
    except Exception as e:
        err = str(e).lower()
        # connection errors — offer retry
        if "ssl" in err or "connection" in err or "timeout" in err or "403" in err or "forbidden" in err or "10053" in err:
            print(f"\nConnection Error — {e}")
            print("\n  1) Retry")
            print("  0) Back To Menu")
            choice = input("\n> ").strip()
            if choice == "1":
                run_pipeline(str(transcript), str(summary))
                logging.info(f"Summary Saved → {summary}")
                show_completion(session_dir)
                return
        else:
            print(f"\nError: {e}")
        print("Transcript Is Still Saved. You Can Re-Summarize From Option 2.")
        pause()


# ── option 3: query sessions ──
def query_sessions():
    while True:
        clear()
        print("=== Query Sessions ===\n")
        print("  1) Single Session")
        print("  2) Entire Course")
        print("  0) Back")

        scope_choice = input("\n> ").strip()

        if scope_choice == "0":
            return

        elif scope_choice == "1":
            print("\nEnter Session Path:")
            print("Example: sessions/database-lab/1405-03-05")
            raw = input("> ").strip()
            if not raw:
                continue

            session_dir = Path(raw) if Path(raw).is_absolute() else Path(__file__).parent / raw

            if not session_dir.exists():
                print("\nSession Folder Not Found. Try Again.")
                pause()
                continue

            # inner query loop for same session
            while True:
                print("\nYour Question (Or Press Enter To Go Back):")
                question = input("> ").strip()
                if not question:
                    break

                print("\nSearching...\n")
                try:
                    answer = query_single_session(session_dir, question)
                    print(f"\n{answer}\n")
                    print("─" * 45)
                    print("  1) Ask Another Question")
                    print("  0) Back")
                    choice = input("\n> ").strip()
                    if choice != "1":
                        break
                except Exception as e:
                    print(f"\nError: {e}")
                    pause()
                    break

        elif scope_choice == "2":
            print("\nEnter Course Name:")
            print("Example: database-lab")
            course_name = input("> ").strip()
            if not course_name:
                continue

            course_dir = Path(__file__).parent / "sessions" / course_name

            if not course_dir.exists():
                print("\nCourse Not Found. Try Again.")
                pause()
                continue

            # inner query loop for same course
            while True:
                print("\nYour Question (Or Press Enter To Go Back):")
                question = input("> ").strip()
                if not question:
                    break

                print("\nSearching...\n")
                try:
                    answer = query_entire_course(course_dir, question)
                    print(f"\n{answer}\n")
                    print("─" * 45)
                    print("  1) Ask Another Question")
                    print("  0) Back")
                    choice = input("\n> ").strip()
                    if choice != "1":
                        break
                except Exception as e:
                    print(f"\nError: {e}")
                    pause()
                    break

        else:
            print("Invalid Choice.")


# ── option 4: batch process ──
def coming_soon_batch():
    print("\n=== Batch Process ===\n")
    print("""This Feature Will Let You Paste Multiple Recording URLs At Once.
The Pipeline Will Process Them One By One — Downloading, Transcribing
& Summarizing Each Session Automatically Without Any Input Needed Between Runs.

All Sessions Will Be Saved To Their Respective Course Folders
Just Like A Normal Run, Ready To Read Immediately Upon Completion.
""")
    pause()


# ── option 5: view sessions ──
def view_sessions():
    if not SESSIONS_DIR.exists() or not any(SESSIONS_DIR.iterdir()):
        print("\nNo Sessions Found.")
        pause()
        return

    print("=== Your Sessions ===\n")

    for course_dir in sorted(SESSIONS_DIR.iterdir()):
        if not course_dir.is_dir():
            continue
        sessions = sorted([s for s in course_dir.iterdir() if s.is_dir()])
        print(f"  {course_dir.name:<30} {len(sessions)} session(s)")

        for session in sessions:
            files = [f.name.lower() for f in session.iterdir()]

            # detect audio — any .mp3 or .wav file
            has_audio = any(f.endswith(".mp3") or f.endswith(".wav") for f in files)

            # detect transcript
            has_transcript = "transcript.txt" in files

            # detect summary — .md or .txt
            has_summary = "summary.md" in files or "summary.txt" in files

            status = " | ".join(filter(None, [
                "audio"      if has_audio      else None,
                "transcript" if has_transcript else None,
                "summary"    if has_summary    else None,
            ]))

            print(f"    └── {session.name:<26} {status}")

        print()

    pause()



# ── option 6: settings ──
def settings():
    from dotenv import dotenv_values
    env_path = Path(__file__).parent / ".env"
    current  = dotenv_values(env_path)

    while True:
        clear()
        print("\n=== Settings ===\n")
        print(f"  1) Gemini API Key       : {'*' * 8 + current.get('GEMINI_API_KEY', '')[-4:] if current.get('GEMINI_API_KEY') else 'Not Set'}")
        print(f"  2) Gemini Model         : {current.get('GEMINI_MODEL', 'gemini-2.5-flash')}")
        print(f"  3) Ollama Model         : {current.get('OLLAMA_MODEL', 'llama3.2:3b')}")
        print(f"  4) Whisper Model        : {current.get('WHISPER_MODEL', 'large-v3')}")
        print(f"  5) Whisper Compute Type : {current.get('WHISPER_COMPUTE_TYPE', 'int8_float16')}")
        print(f"  6) Whisper Beam Size    : {current.get('WHISPER_BEAM_SIZE', '5')}")
        print(f"  7) Keep Audio After Processing : {current.get('KEEP_AUDIO', 'true')}")
        print(f"  8) Transcription Language      : {current.get('TRANSCRIPTION_LANG', 'fa')}")
        print("\n  0) Back")

        choice = input("\n> ").strip()

        if choice == "0":
            break
        elif choice == "1":
            val = input("New Gemini API Key:\n> ").strip()
            if val:
                current["GEMINI_API_KEY"] = val
        elif choice == "2":
            print("Options: gemini-2.5-flash, gemini-2.5-flash-lite")
            val = input("Model Name:\n> ").strip()
            current["GEMINI_MODEL"] = val
        elif choice == "3":
            print("Examples: llama3.2:3b, llama3.1:8b, mistral:7b")
            val = input("Model Name:\n> ").strip()
            current["OLLAMA_MODEL"] = val
        elif choice == "4":
            print("Options: large-v3, medium, small, tiny")
            val = input("Model Size:\n> ").strip()
            current["WHISPER_MODEL"] = val
        elif choice == "5":
            print("Options: int8_float16, int8, float16")
            val = input("Compute Type:\n> ").strip()
            current["WHISPER_COMPUTE_TYPE"] = val
        elif choice == "6":
            val = input("Beam Size (1-10, default 5):\n> ").strip()
            current["WHISPER_BEAM_SIZE"] = val
        elif choice == "7":
            val = input("Keep Audio After Processing? [true/false]:\n> ").strip().lower()
            current["KEEP_AUDIO"] = val
        elif choice == "8":
            print("Examples: fa (Persian), en (English), ar (Arabic)")
            val = input("Language Code:\n> ").strip()
            current["TRANSCRIPTION_LANG"] = val
        else:
            print("Invalid Choice.")
            continue

        # save back to .env
        lines = "\n".join(f"{k}={v}" for k, v in current.items() if v is not None)
        env_path.write_text(lines + "\n", encoding="utf-8")
        print("Saved.")


# ── option 7: about ──
def about():
    from dotenv import dotenv_values
    env_path = Path(__file__).parent / ".env"
    current  = dotenv_values(env_path)

    print("\n=== About ===\n")
    print(f"  Gemini Model         : {current.get('GEMINI_MODEL', 'gemini-2.5-flash')}")
    print(f"  Ollama Model         : {current.get('OLLAMA_MODEL', 'llama3.2:3b')}")
    print(f"  Whisper Model        : {current.get('WHISPER_MODEL', 'large-v3')}")
    print(f"  Whisper Compute Type : {current.get('WHISPER_COMPUTE_TYPE', 'int8_float16')}")
    print(f"  Whisper Beam Size    : {current.get('WHISPER_BEAM_SIZE', '5')}")
    print(f"  Transcription Lang   : {current.get('TRANSCRIPTION_LANG', 'fa')}")
    print(f"  Keep Audio           : {current.get('KEEP_AUDIO', 'true')}")
    print(f"  Sessions Folder      : {SESSIONS_DIR}")
    print()
    pause()


# ── main menu ──
def main():
    check_setup()

    while True:
        clear()
        print(r"""
         ___  ___ _ __(_) |__   ___ 
        / __|/ __| '__| | '_ \ / _ \\
        \__ \ (__| |  | | |_) |  __/
        |___/\___|_|  |_|_.__/ \___|
        """)
        print("  1) Process New Recording")
        print("  2) Re-Summarize Existing Session")
        print("  3) Query Sessions")
        print("  4) Batch Process [Coming Soon]")
        print("  5) View Sessions")
        print("  6) Settings")
        print("  7) About")
        print("  0) Exit")

        choice = input("\n> ").strip()

        if choice == "1":
            try:
                process_new_recording()
            except UserCancelled:
                pass
        elif choice == "2":
            try:
                resummarize()
            except UserCancelled:
                pass
        elif choice == "3":
            query_sessions()
        elif choice == "4":
            coming_soon_batch()
        elif choice == "5":
            view_sessions()
        elif choice == "6":
            settings()
        elif choice == "7":
            about()
        elif choice == "0":
            print("\nGoodbye.")
            sys.exit(0)
        else:
            print("Invalid Choice. Try Again.")


if __name__ == "__main__":
    main()
