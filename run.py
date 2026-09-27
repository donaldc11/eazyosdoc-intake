#!/usr/bin/env python3
"""CLI entrypoint: process a folder of sample PDFs/images into per-document
JSON records and a CSV ledger.

Usage:
    python run.py --samples ./samples --out ./out
"""

import argparse
from pathlib import Path

from intake.pipeline import run


def main():
    parser = argparse.ArgumentParser(description="EazyOS local document intake prototype")
    parser.add_argument("--samples", default="samples", help="folder of input PDFs/images")
    parser.add_argument("--out", default="out", help="output folder for records/ledger")
    args = parser.parse_args()

    run(Path(args.samples), Path(args.out))


if __name__ == "__main__":
    main()
