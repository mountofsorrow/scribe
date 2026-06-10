import re
import sys
import socket
import time
from pathlib import Path
import requests

# path setup
sys.path.insert(0, str(Path(__file__).parent.parent))
from paths import TRANSCRIPT, SUMMARY

try:
    from pipeline.config import API_KEY, CHUNK_SIZE, MODEL_NAME, OLLAMA_MODEL
except ModuleNotFoundError:
    from config import API_KEY, CHUNK_SIZE, MODEL_NAME, OLLAMA_MODEL


# custom exception for switching backends mid-run
class SwitchToOllama(Exception):
    pass


# ── internet check ──
def has_internet(host="8.8.8.8", port=53, timeout=3) -> bool:
    """Ping Google DNS to check internet connectivity."""
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except OSError:
        return False


# ── ollama connection check ──
def check_ollama() -> bool:
    try:
        response = requests.get("http://localhost:11434", timeout=3)
        return response.status_code == 200
    except Exception:
        return False


# ── connectivity router ──
def check_connectivity() -> str:
    """
    Check internet and ask user what to do if offline.
    Returns 'gemini' or 'ollama'.
    """
    while True:
        if has_internet():
            print("Internet Connection Detected — Using Gemini.")
            return "gemini"
        else:
            print("\nNo Internet Connection Detected.")
            choice = input("Use Local Model Instead, Or Retry? [L = Local / R = Retry]\n> ").strip().lower()
            if choice == "l":
                if check_ollama():
                    return "ollama"
                else:
                    print("Ollama Is Not Running. Start It With 'ollama serve' In A Separate Terminal, Then Retry.")
            elif choice == "r":
                print("Retrying Connection...")
                continue
            else:
                print("Invalid Input, Please Enter L Or R.")


# ── transcript cleaner ──
def clean_transcript(raw_text: str) -> str:
    lines = raw_text.splitlines()
    cleaned_lines = []

    for line in lines:
        # remove timestamps like [0.0s -> 5.2s]
        text = re.sub(r"\[.*?\]", "", line).strip()
        if not text:
            continue
        cleaned_lines.append(text)

    merged = " ".join(cleaned_lines)
    merged = re.sub(r"\s+", " ", merged)
    return merged.strip()


# ── text chunker ──
def chunk_text(text: str, size: int) -> list:
    return [text[i:i + size] for i in range(0, len(text), size)]


# ── shared prompt builder ──
def build_prompt(text: str) -> str:
    return f"""
متن زیر پیاده‌سازی یک جلسه کلاس دانشگاهی است.

خروجی را به‌صورت Markdown بنویس با ساختار زیر:

## موضوعات تدریس‌شده
فهرست موضوعاتی که در این جلسه تدریس شده، به ترتیب مطرح شدن.

## توضیحات
توضیح کامل هر موضوع با جزئیات کافی. از زیربخش‌های Markdown استفاده کن اگر لازم بود.

## نکات مهم استاد
نکاتی که استاد روی آن‌ها تأکید کرده یا چند بار تکرار کرده.

---
بخش زیر فقط اگر در جلسه به آن اشاره شده اضافه کن، در غیر این صورت حذفش کن:

## تکالیف / امتحان / پروژه
هر چیزی که استاد درباره تکلیف، امتحان، پروژه یا ددلاین گفته — دقیق و کامل.

---
اگر موضوع مهم دیگری وجود دارد که در بخش‌های بالا جا نمی‌شود، می‌توانی یک بخش جدید با عنوان مناسب اضافه کنی.

متن جلسه:
{text}
"""


# ── final merge prompt ──
def build_final_prompt(combined: str) -> str:
    return f"""
این متن شامل خلاصه بخش‌های مختلف یک جلسه کلاس است.
یک خلاصه نهایی و منسجم به‌صورت Markdown بنویس با ساختار زیر:

## موضوعات تدریس‌شده
## توضیحات
## نکات مهم استاد
## تکالیف / امتحان / پروژه (فقط اگر مطرح شده)

{combined}
"""


# ── gemini summarizer ──
def summarize_chunk_gemini(client, text: str) -> str:
    prompt = build_prompt(text)
    for attempt in range(3):
        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
            return response.text.strip()
        except Exception as e:
            err = str(e).lower()
            if "403" in str(e) or "forbidden" in err:
                print("\nGemini Returned 403 Forbidden.")
                print("This Is Likely A Regional Block — Your Proxy May Not Be Routing API Requests.")
                print("\n  1) Retry With Gemini")
                print("  2) Switch To Local Ollama For This Session")
                choice = input("\n> ").strip()
                if choice == "2":
                    raise SwitchToOllama()
                continue
            elif "rate" in err or "429" in err or "disconnect" in err or "remoteprotocol" in err or "server disconnected" in err:
                wait = 10 * (attempt + 1)
                print(f"Connection Issue — Retrying In {wait}s... (Attempt {attempt + 1}/3)")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Gemini — Max Retries Exceeded. Try Switching To Local Model.")


def summarize_text_gemini(full_text: str) -> str:
    from google import genai
    client = genai.Client(api_key=API_KEY)
    chunks = chunk_text(full_text, CHUNK_SIZE)
    partial_summaries = []

    for i, chunk in enumerate(chunks):
        print(f"Summarizing Chunk {i+1}/{len(chunks)} Via Gemini...")
        try:
            s = summarize_chunk_gemini(client, chunk)
        except SwitchToOllama:
            # switch remaining chunks to ollama
            print("\nSwitching To Ollama For Remaining Chunks...")
            remaining = chunks[i:]
            for j, remaining_chunk in enumerate(remaining):
                print(f"Summarizing Chunk {i+j+1}/{len(chunks)} Via Ollama...")
                partial_summaries.append(summarize_chunk_ollama(remaining_chunk))
            combined = "\n".join(partial_summaries)
            # try final merge with gemini if still online, else ollama
            if has_internet():
                final = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=build_final_prompt(combined)
                )
                return final.text.strip()
            else:
                return summarize_text_ollama(combined)
        partial_summaries.append(s)

    # merge all chunk summaries into one final summary
    combined = "\n".join(partial_summaries)
    final = client.models.generate_content(
        model=MODEL_NAME,
        contents=build_final_prompt(combined)
    )
    return final.text.strip()


# ── ollama summarizer ──
def summarize_chunk_ollama(text: str) -> str:
    prompt = build_prompt(text)
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


def summarize_text_ollama(full_text: str) -> str:
    chunks = chunk_text(full_text, CHUNK_SIZE)
    partial_summaries = []

    for i, chunk in enumerate(chunks):
        print(f"Summarizing Chunk {i+1}/{len(chunks)} Via Ollama (Local)...")
        s = summarize_chunk_ollama(chunk)
        partial_summaries.append(s)

    # merge all chunk summaries into one final summary
    combined = "\n".join(partial_summaries)
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": build_final_prompt(combined),
            "stream": False
        },
        timeout=120
    )
    return response.json()["response"].strip()


# ── output saver ──
def save_output(text: str, path: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ── main pipeline ──
def run_pipeline(input_path: str, output_path: str):
    with open(input_path, "r", encoding="utf-8") as f:
        raw = f.read()

    print("\nCleaning Transcript...")
    cleaned = clean_transcript(raw)

    # check connectivity and pick summarizer
    backend = check_connectivity()

    print(f"\nSummarizing Using {backend.upper()}...")
    if backend == "gemini":
        summary = summarize_text_gemini(cleaned)
    else:
        summary = summarize_text_ollama(cleaned)

    print("\nSaving...")
    save_output(summary, output_path)
    print("Done ✔")


if __name__ == "__main__":
    run_pipeline(str(TRANSCRIPT), str(SUMMARY))
