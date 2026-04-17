import argparse
import logging
import sys
from pipeline import download_lecture, transcribe_audio, summarize_file


# logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# main pipeline
def run_pipeline(url: str):
    try:
        logging.info("Starting pipeline")

        video, audio = download_lecture(url)
        logging.info("Download complete")

        transcript = transcribe_audio(audio)
        logging.info("Transcription complete")

        summary = summarize_file(transcript)
        logging.info("Summarization complete")

        logging.info("Pipeline finished successfully")
        return summary

    except Exception as e:
        logging.error(f"Pipeline failed: {e}")
        sys.exit(1)


# CLI
def main():
    parser = argparse.ArgumentParser(description="Lecture Processing Pipeline")
    parser.add_argument("url", help="Lecture video URL")

    args = parser.parse_args()
    run_pipeline(args.url)


if __name__ == "__main__":
    main()
