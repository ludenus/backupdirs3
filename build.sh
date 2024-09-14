#!/bin/bash
set -e
set -x

if [ -z "$VERSION" ]; then
    [ -z "`git tag -l | head -1`" ] && git tag 0.0.1
    export VERSION="`git describe --tags`"
fi
    
poetry install
poetry show
poetry export -f requirements.txt --output requirements.txt --without-hashes
pip install pyinstaller
sed -ri "s/VERSION *= *['\"][0-9]+\.[0-9]+\.[0-9]+[^'\"]+['\"]/VERSION = '${VERSION}'/g" ./python_configmon/main.py
grep 'VERSION = ' ./python_configmon/main.py
pyinstaller --clean --noupx --onefile python_configmon/main.py

pyi-archive_viewer -l dist/main

cp ./dist/main ./dist/configmon
ls -pilaF ./dist