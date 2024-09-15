# backupdir

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
poetry shell    # Activate the Poetry virtual environment
poetry install  # Install dependencies
poetry show     # List installed dependencies

python backupdir/main.py -h # show help
```

## How to build standalone binary
```bash
poetry run ./build.sh
```
The generated binary will be located in `./dist/backupdir`


## Help
```
usage: backupdir [-h] [-v] [-c CONFIG_FILE] [-m MONITORED_DIR] [-s S3_BUCKET] [-n NODE_NAME] [-b BACKUP_NAME] [-l LOCAL_BACKUP_DIR] [-k] [-d DELAY_BEFORE_UPLOAD]

This tool monitors a config directory for changes and backups the changes to S3

options:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -c CONFIG_FILE, --config-file CONFIG_FILE
                         yaml config file, mutually exclusive with other command line options 
                         default: /etc/backupdir/config.yaml
  -m MONITORED_DIR, --monitored-dir MONITORED_DIR
                         dir to monitor for changes 
                         default: /etc/backupdir
  -s S3_BUCKET, --s3-bucket S3_BUCKET
                         aws s3 bucket to upload backup zip files 
                         default: backupdir-s3-bucket
  -n NODE_NAME, --node-name NODE_NAME
                         node name to use as prefix for backup file 
                         default: thinkpad-e16gen1
  -b BACKUP_NAME, --backup-name BACKUP_NAME
                         app name to use as suffix for backup file 
                         default: backup
  -l LOCAL_BACKUP_DIR, --local-backup-dir LOCAL_BACKUP_DIR
                         local dir to store backup zip files before upload 
                         default: /tmp
  -k, --keep-local-backups
                         do not delete backup zip files after upload to s3 
                         default: False
  -d DELAY_BEFORE_UPLOAD, --delay-before-upload DELAY_BEFORE_UPLOAD
                         seconds to wait after the last file update event before starting upload, valid range: [1..60] 
                         default: 10
```

## Configuration
By default, the tool looks for its configuration file at `/etc/backupdir/config.yaml`. 
The settings specified in the default config file are used as defaults and can be overridden by command-line options.

> [!IMPORTANT]
>
> When custom config file is specified via `-c` `--config-file`
> * no other command-line parameters are allowed
> * only settings from the specified config file are used
> * default config is ignored

```bash
backupdir -c ./config.yaml
```

### Example Configuration File Explained
`config.yaml`:
```yaml
# Config file for the backup directory monitoring tool

# The directory to monitor for changes
# Must be an existing directory and cannot be the root directory ('/')
# User must have read permissions to all files within this dir
monitored_dir: "/etc/backupdir"

# AWS S3 bucket where the backup files will be uploaded
# This bucket must already exist, and the script should have the necessary permissions to upload to it
s3_bucket: "backupdir-s3-bucket"

# The name of the node (usually the machine's hostname) used in naming the backup files
# Optional. If specified must only contain lowercase letters, numbers, dots, and hyphens
node_name: "your-node-name"

# A custom name to be appended to the backup file
# Optional. If specified must only contain lowercase letters, numbers, underscores, and hyphens
backup_name: "backup"

# Directory to store the local backup zip files before uploading to S3
# Must be an existing directory; defaults to system temporary directory
local_backup_dir: "/tmp"

# Delay in seconds after the last detected change before the backup process starts
# This is used to debounce rapid file changes and ensure the backup process isn't triggered too often
# Valid values are between 1 and 60 seconds
delay_before_upload: 10

# Whether to keep the local backup zip files after they are uploaded to S3
# Set to true if you want to retain the backups locally; false to delete them after upload
keep_local_backups: false
```

## Future improvements

1. include/exclude filters for files inside dir?
2. encrypt zip archive before upload?
3. one-time backup without monitor loop?
4. backup to local dir only without s3 upload?
