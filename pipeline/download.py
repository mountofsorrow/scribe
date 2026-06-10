import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse
import requests
from tqdm import tqdm

# path setup
sys.path.insert(0, str(Path(__file__).parent.parent))
from paths import DOWNLOADS_DIR, ZIP_PATH, EXTRACT_DIR, AUDIO_PATH

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# url validator
def validate_url(url: str) -> bool:
    """Check if URL has a valid format before attempting download."""
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


# platform detector
def detect_platform(url: str) -> str:
    """
    Detect whether the URL is a BigBlueButton or Adobe Connect recording.
    """
    bbb_patterns = [
        r"/playback/presentation/",
        r"/presentation/[a-f0-9\-]{40,}",
    ]
    for pattern in bbb_patterns:
        if re.search(pattern, url):
            return "Big Blue Button"
    return "Adobe Connect"


# ══ BigBlueButton ══

# bbb url builder
def build_bbb_url(page_url: str) -> str:
    parsed = urlparse(page_url)

    if page_url.endswith(".webm"):
        return page_url

    match = re.search(r"/([a-f0-9\-]+)$", parsed.path)
    if not match:
        raise ValueError("Could not detect BBB recording ID from URL")

    recording_id = match.group(1)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return f"{base}/presentation/{recording_id}/video/webcams.webm"


# bbb duration detector
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


# bbb video downloader
def download_bbb_video(url: str, out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    print("\nFetching video duration...")
    duration = get_duration(url)

    cmd = [
        "ffmpeg", "-y",
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
        raise RuntimeError("BBB download failed")

    print("\nSaved →", out_path)


# bbb audio extractor
def extract_bbb_audio(video_path: str, audio_path: str):
    print("\nExtracting audio...")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "libmp3lame",
        "-ab", "128k",
        audio_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Audio saved →", audio_path)


# bbb main pipeline
def download_lecture_bbb(url: str) -> str:
    video_url = build_bbb_url(url)
    print(f"\nDetected BBB recording:")
    print(f"  {video_url}")

    filename  = video_url.split("/")[-3]
    video_path = str(DOWNLOADS_DIR / f"{filename}.webm")
    audio_path = str(AUDIO_PATH)

    download_bbb_video(video_url, video_path)
    extract_bbb_audio(video_path, audio_path)

    # remove webm after audio is extracted
    try:
        os.remove(video_path)
        print(f"Removed: {video_path}")
    except FileNotFoundError:
        pass

    return audio_path


# ══ ADOBE CONNECT ══

# adobe url builder
def build_zip_url(room_url: str) -> str:
    parsed = urlparse(room_url)
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}/output/recording.zip?download=zip"


# adobe zip downloader
def download_zip(zip_url: str, zip_path: str):
    if os.path.exists(zip_path):
        # verify existing ZIP is not corrupt before trusting it
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.namelist()
            print(f"\nZIP already exists and is valid, skipping download -> {zip_path}")
            return
        except zipfile.BadZipFile:
            print(f"\nExisting ZIP is corrupt — deleting and re-downloading...")
            os.remove(zip_path)

    print(f"\nDownloading ZIP from:\n  {zip_url}\n")

    response = requests.get(zip_url, stream=True, verify=False, timeout=60)

    if response.status_code == 404:
        raise RuntimeError(
            "404 - ZIP not found.\n"
            "  The room URL might be wrong, or the recording isn't ready yet."
        )
    if response.status_code != 200:
        raise RuntimeError(f"Server returned HTTP {response.status_code}")

    total = int(response.headers.get("content-length", 0))
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)

    with open(zip_path, "wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc="Downloading", bar_format="{l_bar}{bar:20}{r_bar}") as bar:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))

    print(f"\nZIP saved -> {zip_path}")


# adobe extractor
def extract_audio_files(zip_path: str, extract_dir: str) -> list:
    print("\nInspecting ZIP contents...")
    os.makedirs(extract_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        all_files = zf.namelist()
        print(f"  {len(all_files)} files found inside ZIP")

        # priority 1: cameraVoip segments
        def sort_key(filename):
            # extract the start timestamp number from cameraVoip_START_END.flv
            match = re.search(r"cameraVoip_(\d+)_", filename, re.IGNORECASE)
            return int(match.group(1)) if match else 0

        targets = sorted(
            [f for f in all_files if re.search(r"cameraVoip", f, re.IGNORECASE) and f.endswith(".flv")],
            key=sort_key
        )

        # priority 2: mainstream segments
        def sort_key_generic(filename):
            match = re.search(r"_(\d+)_", filename)
            return int(match.group(1)) if match else 0

        if not targets:
            targets = sorted(
                [f for f in all_files if re.search(r"mainstream", f, re.IGNORECASE) and f.endswith(".flv")],
                key=sort_key_generic
            )

        # priority 3: any flv as last resort
        if not targets:
            targets = sorted(
                [f for f in all_files if f.endswith(".flv")],
                key=sort_key_generic
            )

        if not targets:
            raise RuntimeError(f"No usable audio file found in ZIP.\nFiles present: {all_files}")

        print(f"  Found {len(targets)} audio segment(s):")
        for t in targets:
            print(f"    {t}")
            zf.extract(t, extract_dir)

    return [os.path.join(extract_dir, t) for t in targets]


# adobe converter
def convert_to_mp3(flv_paths: list, mp3_path: str):
    print(f"\nConverting {len(flv_paths)} segment(s) to MP3...")

    if len(flv_paths) == 1:
        # single segment — direct conversion
        cmd = [
            "ffmpeg", "-y",
            "-i", flv_paths[0],
            "-vn",
            "-acodec", "libmp3lame",
            "-ab", "128k",
            mp3_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

    else:
        # Stitch multiple segments
        concat_list_path = str(DOWNLOADS_DIR / "concat_list.txt")
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for p in flv_paths:
                safe = os.path.abspath(p).replace("\\", "/")
                f.write(f"file '{safe}'\n")

        print("  Concat list:")
        for p in flv_paths:
            print(f"    {p}")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-vn",
            "-acodec", "libmp3lame",
            "-ab", "128k",
            mp3_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        # remove temp concat list
        try:
            os.remove(concat_list_path)
        except FileNotFoundError:
            pass

    if result.returncode != 0:
        # clean up leftover extracted files before raising
        import shutil
        try:
            shutil.rmtree(str(EXTRACT_DIR))
        except FileNotFoundError:
            pass
        raise RuntimeError(f"ffmpeg failed.\nSTDERR:\n{result.stderr}")

    print(f"Audio Saved -> {mp3_path}")

# adobe cleanup
def cleanup(zip_path: str, extract_dir: str):
    try:
        os.remove(zip_path)
        print(f"Removed: {zip_path}")
    except FileNotFoundError:
        pass
    try:
        shutil.rmtree(extract_dir)
        print(f"Removed: {extract_dir}/")
    except FileNotFoundError:
        pass


# adobe main pipeline
def download_lecture_adobe(room_url: str) -> str:
    zip_url     = build_zip_url(room_url)
    zip_path    = str(ZIP_PATH)
    extract_dir = str(EXTRACT_DIR)
    mp3_path    = str(AUDIO_PATH)

    download_zip(zip_url, zip_path)
    flv_paths = extract_audio_files(zip_path, extract_dir)
    convert_to_mp3(flv_paths, mp3_path)
    cleanup(zip_path, extract_dir)

    return mp3_path


# main pipeline
def download_lecture(url: str) -> str:
    """
    Auto-detects platform from URL and routes to the correct downloader.
    Always returns the path to downloads/audio.mp3.
    """
    if not validate_url(url):
        raise ValueError(
            f"Invalid URL: '{url}'\n"
            "Make Sure The URL Starts With http:// or https:// and Has A Valid Domain."
        )

    platform = detect_platform(url)
    print(f"\nDetected Platform: {platform.upper()}")

    if platform == "Big Blue Button":
        return download_lecture_bbb(url)
    else:
        return download_lecture_adobe(url)


# entry point
def main():
    print("=== Lecture Audio Fetcher ===\n")
    url = input("Paste the recording URL:\n> ").strip()

    if not url:
        print("No URL provided. Exiting.")
        return

    try:
        audio_path = download_lecture(url)
        print(f"\nDone. Audio ready at: {audio_path}")
    except Exception as e:
        print(f"\nERROR: {e}")


if __name__ == "__main__":
    main()
