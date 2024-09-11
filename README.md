# python-inotify

## Prerequisites
* curl
* python3

## Install 
* python poetry
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Update PATH your shell configuration file
```bash
export PATH="/home/vagrant/.local/bin:$PATH"
```

Check poetry is installed correctly:

```bash
poetry --version
```

## How to run
```bash

poetry shell

python python_inotify/main.py
```