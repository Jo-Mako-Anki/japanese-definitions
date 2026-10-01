"""
Build JapaneseDefinitions.ankiaddon

    python build.py                 # download the dictionaries if missing, then build
    python build.py --update-data   # force downloading the latest dictionaries

Output: dist/JapaneseDefinitions-<version>.ankiaddon
Only the Python standard library is needed.
"""

import argparse
import gzip
import json
import os
import shutil
import sys
import time
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src", "JapaneseDefinitions")
DATA = os.path.join(ROOT, "data")
DIST = os.path.join(ROOT, "dist")

JMDICT_URL = "http://ftp.edrdg.org/pub/Nihongo/JMdict_e.gz"
FURIGANA_URL = (
    "https://github.com/Doublevil/JmdictFurigana/releases/latest/download/"
    "JmdictFurigana.json"
)

JMDICT_FILE = os.path.join(DATA, "JMdict_e.gz")
FURIGANA_FILE = os.path.join(DATA, "JmdictFurigana.json.gz")

EXCLUDED_DIRS = {"__pycache__"}
EXCLUDED_FILES = {"meta.json"}


def download(url, dest, compress=False):
    print(f"Downloading {url}")
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "JapaneseDefinitions-build"})
    with urllib.request.urlopen(req, timeout=120) as response:
        if compress:
            with gzip.open(tmp, "wb", compresslevel=9) as out:
                shutil.copyfileobj(response, out)
        else:
            with open(tmp, "wb") as out:
                shutil.copyfileobj(response, out)
    os.replace(tmp, dest)
    print(f"  -> {os.path.relpath(dest, ROOT)} ({os.path.getsize(dest) / 1e6:.1f} MB)")


def ensure_data(force):
    os.makedirs(DATA, exist_ok=True)
    if force or not os.path.exists(JMDICT_FILE):
        download(JMDICT_URL, JMDICT_FILE)
    if force or not os.path.exists(FURIGANA_FILE):
        download(FURIGANA_URL, FURIGANA_FILE, compress=True)


def read_manifest():
    with open(os.path.join(SRC, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def build():
    manifest = read_manifest()
    manifest["mod"] = int(time.time())
    version = manifest.get("human_version", "dev")

    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, f"JapaneseDefinitions-{version}.ankiaddon")

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:

        for folder, dirs, files in os.walk(SRC):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            rel_folder = os.path.relpath(folder, SRC)

            for name in files:
                if name in EXCLUDED_FILES or name == "manifest.json":
                    continue
                if name.startswith(("JMdict_e", "JmdictFurigana")):
                    continue
                rel = os.path.normpath(os.path.join(rel_folder, name))
                if rel.startswith("user_files") and name != "README.txt":
                    continue
                z.write(os.path.join(folder, name), rel.replace(os.sep, "/"))

        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=4))
        z.write(JMDICT_FILE, "JMdict_e.gz")
        z.write(FURIGANA_FILE, "JmdictFurigana.json.gz")

    size = os.path.getsize(out) / 1e6
    print(f"\nBuilt {os.path.relpath(out, ROOT)} ({size:.1f} MB) — version {version}")
    if size > 140:
        print("WARNING: close to AnkiWeb's ~150 MB upload limit.")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--update-data", action="store_true",
                        help="download the latest JMdict and JmdictFurigana")
    args = parser.parse_args()

    try:
        ensure_data(args.update_data)
    except Exception as e:
        print(f"\nDownload failed: {e}")
        print("You can also place JMdict_e.gz and JmdictFurigana.json.gz in data/ manually.")
        sys.exit(1)

    build()


if __name__ == "__main__":
    main()
