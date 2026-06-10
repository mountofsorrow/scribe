import os
import sys
import time
from pathlib import Path

# path setup
sys.path.insert(0, str(Path(__file__).parent.parent))
from paths import MODELS_DIR, AUDIO_PATH, TRANSCRIPT, PROJECT_DLLS

try:
    from pipeline.config import WHISPER_MODEL, WHISPER_COMPUTE_TYPE, WHISPER_BEAM_SIZE, TRANSCRIPTION_LANG
except ModuleNotFoundError:
    from config import WHISPER_MODEL, WHISPER_COMPUTE_TYPE, WHISPER_BEAM_SIZE, TRANSCRIPTION_LANG


# model loader
def load_model():
    # dll setup — must happen before ctranslate2 is used
    os.add_dll_directory(str(PROJECT_DLLS))

    from faster_whisper import WhisperModel

    model_path = str(MODELS_DIR / WHISPER_MODEL)
    print(f"Loading Model ({WHISPER_MODEL}) Into GPU... (This May Take A Moment)")

    model = WhisperModel(
        model_path,
        device="cuda",
        compute_type=WHISPER_COMPUTE_TYPE,
        local_files_only=True
    )
    return model


# transcriber
def transcribe(model, audio_path: str, output_path: str = None) -> str:
    """
    Transcribe audio file and save to output_path.
    Falls back to TRANSCRIPT from paths.py if no output_path given.
    """
    if output_path is None:
        output_path = str(TRANSCRIPT)

    initial_prompt = (
        "این یک فایل صوتی به زبان فارسی است که ممکن است کلمات انگلیسی در آن باشد. "
        "لطفا همان‌طور که شنیده می‌شود بنویسید."
    ) if TRANSCRIPTION_LANG == "fa" else None

    print(f"\nProcessing {audio_path}...")
    start = time.time()

    segments, info = model.transcribe(
        audio_path,
        language=TRANSCRIPTION_LANG,
        beam_size=WHISPER_BEAM_SIZE,
        initial_prompt=initial_prompt,
        vad_filter=True,
        word_timestamps=False
    )

    print(f"Detected Language '{info.language}' With Probability {info.language_probability:.2f}")

    # write segments to transcript file as they stream in
    transcript_path = Path(output_path)
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for segment in segments:
                line = f"[{segment.start:.1f}s -> {segment.end:.1f}s] {segment.text}"
                print(line)
                f.write(line + "\n")
                f.flush()
    except Exception as e:
        # transcription failed midway — delete partial file
        if transcript_path.exists():
            transcript_path.unlink()
            print(f"\nTranscription Failed Midway — Deleted Incomplete File: {output_path}")
        raise RuntimeError(f"Transcription Failed: {e}")

    # check if transcript is empty or too short to be valid
    with open(output_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    if not content:
        transcript_path.unlink()
        raise RuntimeError(
            "Transcription Produced No Output.\n"
            "The Audio May Be Silent, Too Short, Or In The Wrong Language."
        )

    if len(content) < 100:
        print(
            f"\nWarning: Transcript Is Unusually Short ({len(content)} Characters).\n"
            "This Might Be A Short Announcement Or A Silent Recording."
        )
        choice = input("Continue Anyway? [Y / N]\n> ").strip().lower()
        if choice != "y":
            transcript_path.unlink()
            raise RuntimeError("Pipeline Cancelled By User — Transcript Too Short.")

    total_seconds = int(time.time() - start)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    print(f"\nDone! Saved To {output_path}. Total Time: {minutes}m {seconds}s")
    return output_path


# entry point
def main():
    model = load_model()
    transcribe(model, str(AUDIO_PATH))


if __name__ == "__main__":
    main()
