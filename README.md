# python-configmon

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
export PATH="$HOME/.local/bin:$PATH"
```

Check poetry is installed correctly:

```bash
poetry --version
```

## How to run
```bash

poetry shell
poetry install
poetry show

python python_configmon/main.py
```