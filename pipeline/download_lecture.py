import subprocess
import re
import os
from urllib.parse import urlparse
from tqdm import tqdm


#  Build Direct Video URL
def build_direct_url(page_url: str) -> str:

    parsed = urlparse(page_url)

    # already direct video
    if page_url.endswith(".webm"):
        return page_url

    # extract recording id
    match = re.search(r"/([a-f0-9\-]+)$", parsed.path)
    if not match:
        raise ValueError("Could not detect recording ID from URL")

    recording_id = match.group(1)
    base = f"{parsed.scheme}://{parsed.netloc}"

    return f"{base}/presentation/{recording_id}/video/webcams.webm"


# Duration Detector
def get_duration(url: str) -> float:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        url
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    try:
        return float(result.stdout.strip())
    except:
        raise RuntimeError("Could not read video duration")


# Download Video
def download_video(url: str, out_path: str):

    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    print("\nFetching video duration...")
    duration = get_duration(url)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", url,
        "-c", "copy",
        "-progress", "pipe:1",
        "-nostats",
        out_path
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    time_pattern = re.compile(r"out_time_ms=(\d+)")

    with tqdm(total=duration, unit="s", desc="Downloading") as bar:
        for line in process.stdout:
            match = time_pattern.search(line)
            if match:
                current = int(match.group(1)) / 1_000_000
                bar.n = current
                bar.refresh()

    process.wait()

    if process.returncode != 0:
        raise RuntimeError("Download failed")

    print("\nSaved →", out_path)


# Audio Extractor
def extract_audio(video_path: str, audio_path: str):
    print("\nExtracting audio...")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "libmp3lame",
        "-ab", "128k",
        audio_path
    ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Audio saved →", audio_path)


# Main Pipeline
def main():

    print("=== Lecture Fetcher ===\n")
    url = input("Paste playback page URL:\n> ").strip()

    try:
        video_url = build_direct_url(url)
    except Exception as e:
        print("URL Error:", e)
        return

    print("\nDirect video URL detected:")
    print(video_url)

    filename = video_url.split("/")[-3]
    video_path = f"downloads/{filename}.webm"
    audio_path = f"downloads/{filename}.mp3"

    try:
        download_video(video_url, video_path)
        extract_audio(video_path, audio_path)
    except Exception as e:
        print("\nERROR:", e)


if __name__ == "__main__":
    main()