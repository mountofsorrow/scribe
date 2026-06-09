# Scribe

```
 ___  ___ _ __(_) |__   ___ 
/ __|/ __| '__| | '_ \ / _ \
\__ \ (__| |  | | |_) |  __/
|___/\___|_|  |_|_.__/ \___|
```

Scribe is a command-line tool that automatically downloads, transcribes and summarizes university lecture recordings. Paste a link from your online class and get a structured Persian-language summary without attending.

Supports **BigBlueButton** and **Adobe Connect (Vadana)** — the two platforms used by most Iranian universities.

---

## Requirements

Before installing, make sure you have:

- **Python 3.10+**
- **ffmpeg** — installed and added to your system PATH ([download](https://ffmpeg.org/download.html))
- **NVIDIA GPU with CUDA** — required for fast transcription via Whisper
- **CUDA DLLs** — `cublas64_12.dll`, `cublasLt64_12.dll`, `nvblas64_12.dll` copied into `.venv/Lib/site-packages/ctranslate2/` (see CUDA Setup below)
- **Gemini API key** — free at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- **Ollama** (optional) — for offline summarization ([ollama.com](https://ollama.com))

---

## Installation

```bash
git clone https://github.com/yourname/scribe.git
cd scribe
uv pip install -e .
python setup.py
```

`setup.py` will ask for your Gemini API key, preferred model, and Ollama model name. It writes everything to a `.env` file so you never have to edit config manually.

---

## CUDA Setup

Whisper runs on your GPU via `ctranslate2`. On Windows, the CUDA DLLs need to be placed manually:

1. Download or locate these three files:
   - `cublas64_12.dll`
   - `cublasLt64_12.dll`
   - `nvblas64_12.dll`
2. Copy them into:
   ```
   .venv\Lib\site-packages\ctranslate2\
   ```

---

## Usage

```bash
python main.py
```

```
 ___  ___ _ __(_) |__   ___ 
/ __|/ __| '__| | '_ \ / _ \
\__ \ (__| |  | | |_) |  __/
|___/\___|_|  |_|_.__/ \___|

  1) Process New Recording
  2) Re-Summarize Existing Session
  3) Query Sessions
  4) Batch Process [Coming Soon]
  5) View Sessions
  6) Settings
  7) About
  0) Exit
```

### Menu Options

| Option | What It Does |
|--------|-------------|
| 1) Process New Recording | Paste a URL → downloads, transcribes, and summarizes in one go |
| 2) Re-Summarize | Run summarization again on an existing transcript |
| 3) Query Sessions | Ask specific questions about one session or an entire course |
| 4) Batch Process | Coming soon — process multiple recordings overnight |
| 5) View Sessions | See all your saved courses and sessions |
| 6) Settings | Configure models, language, and pipeline behavior |
| 7) About | Show current configuration |

---

## Session Structure

Every processed recording is saved under `sessions/` organized by course and date:

```
sessions/
└── operating-systems/
    └── 1404-02-30/
        ├── audio.mp3        ← original recording audio
        ├── transcript.txt   ← raw whisper output with timestamps
        ├── summary.md       ← structured markdown summary
        ├── queries.log      ← history of questions asked about this session
        └── session.json     ← metadata (url, date, model used)
```

Dates use the **Shamsi (Persian) calendar** — you enter the date when processing a recording.

---

## Supported Platforms

Scribe auto-detects the platform from the URL:

**BigBlueButton** — URLs containing `/playback/presentation/` or `/presentation/`
```
https://bbb.university.ac.ir/playback/presentation/2.3/abc123...
```

**Adobe Connect / Vadana** — any other URL (the ZIP endpoint is constructed automatically)
```
https://vadavc042.ec.iau.ir/l4jwca518uhk/
```

No configuration needed — just paste the URL and Scribe figures it out.

---

## Internet & Proxy

Scribe uses **Gemini** for summarization and querying when internet is available, and falls back to a local **Ollama** model when offline.

---

## Settings

All settings are stored in `.env` and can be changed via the Settings menu or by editing the file directly:

| Key | Default | Description |
|-----|---------|-------------|
| `GEMINI_API_KEY` | — | Your Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model to use |
| `OLLAMA_MODEL` | `llama3.2:3b` | Local Ollama model for offline use |
| `WHISPER_MODEL` | `large-v3` | Whisper model size |
| `WHISPER_COMPUTE_TYPE` | `int8_float16` | Compute type (affects VRAM usage) |
| `WHISPER_BEAM_SIZE` | `5` | Transcription beam size |
| `TRANSCRIPTION_LANG` | `fa` | Language code for transcription |
| `KEEP_AUDIO` | `true` | Keep audio file after processing |

---

## Known Limitations

- **Windows only** — the keyboard buffer fix uses `msvcrt` which is Windows-specific
- **NVIDIA GPU required** — CPU transcription is not currently supported
- **Persian primary** — the summarization prompt and query responses are in Persian by default
- **VPN may be needed** — Gemini API is blocked in Iran without a proxy

---


## License

MIT
