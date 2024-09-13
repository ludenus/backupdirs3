#!/bin/bash
set -e
set -x

if [ -z "$VERSION" ]; then
    [ -z "`git tag -l`" ] && git tag 0.0.1
    export VERSION="`git describe --tags`"
fi
    
poetry install
poetry show
poetry export -f requirements.txt --output requirements.txt --without-hashes
pip install pyinstaller
pyinstaller --clean --noupx --onefile python_inotify/main.py

pyi-archive_viewer -l dist/main

cp ./dist/main ./dist/inotify
ls -pilaF ./dist