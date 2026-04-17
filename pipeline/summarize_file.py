import re
from google import genai
from config import API_KEY, CHUNK_SIZE, MODEL_NAME


client = genai.Client(api_key=API_KEY)

# Clean Transcript
def clean_transcript(raw_text: str) -> str:
    lines = raw_text.splitlines()
    cleaned_lines = []

    for line in lines:
        # remove timestamps
        text = re.sub(r"\[.*?\]", "", line).strip()

        if not text:
            continue

        cleaned_lines.append(text)

    merged = " ".join(cleaned_lines)
    merged = re.sub(r"\s+", " ", merged)

    return merged.strip()


# Chunk Text
def chunk_text(text, size):
    return [text[i:i + size] for i in range(0, len(text), size)]


# Summarize Chunk
def summarize_chunk(client, text):
    prompt = f"""
این متن پیاده‌سازی یک جلسه کامل کلاس دانشگاهی است.

لطفاً یک گزارش خلاصه اما دقیق بنویس که محتوای جلسه را به‌صورت متعادل بازگو کند.

ساختار خروجی:
1) موضوعات اصلی تدریس‌شده (به ترتیب مطرح شدن)
2) توضیح هر بخش با جزئیات کافی
3) نکات مهم یا تأکیدهای استاد
4) اگر درباره امتحان، تمرین، پروژه یا قوانین کلاس صحبت شده، همان را دقیق نقل کن

سبک نوشتار:
- روان
- واضح
- بدون حذف نکات مهم
- نه خیلی کوتاه نه خیلی طولانی

هدف: کسی که کلاس را ندیده با خواندن این متن تقریباً بداند در جلسه چه گذشت.
{text}
"""

    response = client.models.generate_content(
        model= MODEL_NAME,
        contents= prompt
    )
    return response.text.strip()


# Summarizer
def summarize_text(full_text: str):

    global client
    chunks = chunk_text(full_text, CHUNK_SIZE)
    partial_summaries = []

    for i, chunk in enumerate(chunks):
        print(f"Summarizing chunk {i+1}/{len(chunks)}...")
        s = summarize_chunk(client, chunk)
        partial_summaries.append(s)

    combined = "\n".join(partial_summaries)

    final_prompt = f"""
این متن شامل خلاصه بخش‌های مختلف یک جلسه کلاس است.
یک خلاصه نهایی و منسجم از کل جلسه بنویس:

{combined}
"""

    final = client.models.generate_content(
        model=MODEL_NAME,
        contents=final_prompt
    )
    return final.text.strip()


# Save Output
def save_output(text, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# Pipeline
def run_pipeline(input_path, output_path):

    with open(input_path, "r", encoding="utf-8") as f:
        raw = f.read()

    print("Cleaning transcript...")
    cleaned = clean_transcript(raw)

    print("Summarizing...")
    summary = summarize_text(cleaned)

    print("Saving...")
    save_output(summary, output_path)

    print("Done ✔")


if __name__ == "__main__":
    run_pipeline("transcript.txt", "summary.txt")