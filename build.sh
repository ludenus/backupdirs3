#!/bin/bash
set -e
set -x

if [ -z "$VERSION" ]; then
    [ -z "`git tag -l`" ] && git tag 0.0.1
    export VERSION="`git describe --tags`"
fi
    
poetry run poetry export -f requirements.txt --output requirements.txt --without-hashes
poetry run pip install pyinstaller
poetry run pyinstaller --onefile python_inotify/main.py

cp ./dist/main ./dist/inotify