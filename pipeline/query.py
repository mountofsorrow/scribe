import sys
import socket
import re
import requests
from pathlib import Path
from datetime import datetime

# path setup
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from pipeline.config import API_KEY, MODEL_NAME, CHUNK_SIZE, OLLAMA_MODEL
except ModuleNotFoundError:
    from config import API_KEY, MODEL_NAME, CHUNK_SIZE, OLLAMA_MODEL


# ── internet check ──
def has_internet(host="8.8.8.8", port=53, timeout=3) -> bool:
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except OSError:
        return False


# ── prompt builder ──
def build_query_prompt(question: str, text: str) -> str:
    return f"""بر اساس محتوای زیر که پیاده‌سازی یک جلسه کلاس دانشگاهی است، به سوال زیر پاسخ بده:

سوال: {question}

دستورالعمل:
- مستقیم و دقیق پاسخ بده
- فقط اطلاعاتی که در متن وجود دارد را استفاده کن
- اگر پاسخ در متن نبود، صریح بگو که این موضوع در جلسه مطرح نشده
- پاسخ را به فارسی بنویس

محتوا:
{text}
"""


def build_merge_prompt(question: str, partial_answers: list) -> str:
    combined = "\n\n---\n\n".join(partial_answers)
    return f"""سوال زیر درباره یک درس دانشگاهی پرسیده شده و پاسخ‌های جزئی از بخش‌های مختلف آمده است.
یک پاسخ نهایی، منسجم و دقیق به فارسی بنویس:

سوال: {question}

پاسخ‌های جزئی:
{combined}
"""


# ── gemini query ──
def ask_gemini(prompt: str) -> str:
    from google import genai
    import time
    client = genai.Client(api_key=API_KEY)

    for attempt in range(3):
        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
            return response.text.strip()
        except Exception as e:
            err = str(e).lower()
            if "rate" in err or "429" in err or "disconnect" in err or "remoteprotocol" in err:
                wait = 10 * (attempt + 1)
                print(f"Connection Issue — Retrying In {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Gemini — Max Retries Exceeded.")


# ── ollama query ──
def ask_ollama(prompt: str) -> str:
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        },
        timeout=120
    )
    return response.json()["response"].strip()


# ── backend router ──
def ask(prompt: str) -> str:
    if has_internet():
        return ask_gemini(prompt)
    else:
        return ask_ollama(prompt)


# ── text chunker ──
def chunk_text(text: str, size: int) -> list:
    return [text[i:i + size] for i in range(0, len(text), size)]


# ── query log saver ──
def save_to_log(log_path: Path, question: str, answer: str, scope: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"[{timestamp}] [{scope}]\nQ: {question}\nA: {answer}\n{'-' * 60}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)


# ── single session query ──
def query_single_session(session_dir: Path, question: str) -> str:
    transcript_path = session_dir / "transcript.txt"

    if not transcript_path.exists():
        raise FileNotFoundError(f"No Transcript Found In {session_dir}")

    text = transcript_path.read_text(encoding="utf-8")

    # remove timestamps from transcript
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    chunks = chunk_text(text, CHUNK_SIZE)

    if len(chunks) == 1:
        answer = ask(build_query_prompt(question, chunks[0]))
    else:
        print(f"  Searching Through {len(chunks)} Parts...")
        partial = []
        for i, chunk in enumerate(chunks):
            print(f"  Part {i+1}/{len(chunks)}...")
            partial.append(ask(build_query_prompt(question, chunk)))
        answer = ask(build_merge_prompt(question, partial))

    # save to session query log
    log_path = session_dir / "queries.log"
    scope = f"{session_dir.parent.name}/{session_dir.name}"
    save_to_log(log_path, question, answer, scope)

    return answer


# ── entire course query ──
def query_entire_course(course_dir: Path, question: str) -> str:
    sessions = sorted([s for s in course_dir.iterdir() if s.is_dir()])

    if not sessions:
        raise FileNotFoundError(f"No Sessions Found In {course_dir}")

    # collect all summaries
    texts = []
    for session in sessions:
        summary_path = session / "summary.md"
        if summary_path.exists():
            content = summary_path.read_text(encoding="utf-8")
            texts.append(f"=== {session.name} ===\n{content}")

    if not texts:
        raise FileNotFoundError("No Summaries Found In This Course. Run Summarization First.")

    combined = "\n\n".join(texts)
    chunks = chunk_text(combined, CHUNK_SIZE)

    if len(chunks) == 1:
        answer = ask(build_query_prompt(question, chunks[0]))
    else:
        print(f"  Searching Through {len(chunks)} Parts Across {len(sessions)} Sessions...")
        partial = []
        for i, chunk in enumerate(chunks):
            print(f"  Part {i+1}/{len(chunks)}...")
            partial.append(ask(build_query_prompt(question, chunk)))
        answer = ask(build_merge_prompt(question, partial))

    # save to global query log at sessions root
    from paths import SESSIONS_DIR
    log_path = SESSIONS_DIR / "queries.log"
    scope = f"course:{course_dir.name}"
    save_to_log(log_path, question, answer, scope)

    return answer
