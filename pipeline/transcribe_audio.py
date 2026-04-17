from faster_whisper import WhisperModel
import time

# DLLs are in the same folder as this script
# Path to your successfully downloaded and fixed model
model_path = r'D:\Work\Python (2025)\20. Transcription\models\large-v3'

# Load the model with VRAM optimization
print("Loading model into GPU... (This may take a moment)")
model = WhisperModel(
    model_path,
    device="cuda",
    compute_type= "int8_float16",  # Keeps VRAM usage around 4.5GB
    local_files_only=True
)

# Set the file path
audio_path = r"D:\Work\Python (2025)\20. Transcription\webcams.mp3"

initial_prompt = "این یک فایل صوتی به زبان فارسی است که ممکن است کلمات انگلیسی مثل AI, Python, یا Windows در آن باشد. لطفا همان‌طور که شنیده می‌شود بنویسید."

print(f"Processing {audio_path}...")
start = time.time()

# The transcription generates segments lazily
segments, info = model.transcribe(
    audio_path,
    language="fa",
    beam_size=5,
    initial_prompt=initial_prompt,
    vad_filter=True,
    word_timestamps=False
)

print(f"Detected language '{info.language}' with probability {info.language_probability:.2f}")

# Save to a text file
with open("transcript.txt", "w", encoding="utf-8") as f:
    for segment in segments:
        line = f"[{segment.start:.1f}s -> {segment.end:.1f}s] {segment.text}"

        # prints to terminal to see progress
        print(line)
        # saves to the file
        f.write(line + "\n")

        # ensures the text is written to the disk immediately so u don't lose progress
        f.flush()

total_seconds = int(time.time() - start)
minutes = total_seconds // 60
seconds = total_seconds % 60

print(f"Done! Saved to transcript.txt. Total time: {minutes}m {seconds}s")