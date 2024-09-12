#!/bin/bash
set -e
set -x
poetry export -f requirements.txt --output requirements.txt --without-hashes
pip install pyinstaller
pyinstaller --onefile python_inotify/main.py
