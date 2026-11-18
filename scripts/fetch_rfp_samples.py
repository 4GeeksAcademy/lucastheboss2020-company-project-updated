"""Download public curriculum PDFs to a temporary folder, not to data/raw/."""

from pathlib import Path
import argparse, urllib.request

BASE = "https://raw.githubusercontent.com/4GeeksAcademy/ai-engineering-syllabus/main/content/contexts/09-agentic-workflows/rfp-requests/trackflow/"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/tmp/trackflow-rfp-samples")
    args = parser.parse_args()
    folder = Path(args.output)
    folder.mkdir(parents=True, exist_ok=True)
    for index in (1, 2, 3):
        name = f"trackflow-request-{index}.pdf"
        urllib.request.urlretrieve(BASE + name, folder / name)
        print("Downloaded", name)


if __name__ == "__main__":
    main()
