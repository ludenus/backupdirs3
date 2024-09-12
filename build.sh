#!/bin/bash
set -e
set -x
poetry run poetry export -f requirements.txt --output requirements.txt --without-hashes
poetry run pip install pyinstaller
poetry run pyinstaller --onefile python_inotify/main.py
