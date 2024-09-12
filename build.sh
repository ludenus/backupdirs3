#!/bin/bash
set -e
set -x

if [ -z "$VERSION" ]; then
    [ -z "`git tag -l`" ] && git tag 0.0.1
    export VERSION="`git describe --tags`"
fi
    
poetry install
poetry export -f requirements.txt --output requirements.txt --without-hashes
pip install pyinstaller
pyinstaller --onefile python_inotify/main.py

cp ./dist/main ./dist/inotify