# python-configmon

A tool to monitor a directory for configuration changes, create a backup in the form of a zip file, and upload it to an AWS S3 bucket.

## Prerequisites
* `curl`: Required for installing Poetry.
* `python3`: Ensure Python 3.10+ is installed on your system.
* `AWS credentials`: Configure AWS credentials to enable S3 uploads.

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

poetry shell    # Activate the Poetry virtual environment:
poetry install  # Install dependencies
poetry show     # List installed dependencies

python python_configmon/main.py -h # show help
python python_configmon/main.py    # run with default config
```

## How to build standalone binary
```bash
poetry run ./build.sh
```
The generated binary will be located in `./dist/configmon`

## Configuration
By default, the tool looks for its configuration file at `/etc/powerfactors/configmon.yaml`. You can override this location by providing the -c option followed by the path to your custom YAML file.

```bash
configmon -c ./config.yaml
```

### Example Configuration File

```yaml
monitored_dir: /opt/n3uron/config  # Directory to monitor for changes. Cannot be the root directory '/'.
s3_bucket: my-backup-s3-bucket     # AWS S3 bucket for storing the backup zip files.
node_name: my-hostname             # Optional. Prefix for backup files. Defaults to the system's hostname.
```