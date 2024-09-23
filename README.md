# backupdirs3

A tool to monitor a directory for changes, create a backup in the form of a zip file, and upload it to an AWS S3 bucket.

## Prerequisites
* `AWS credentials`: Configure AWS credentials to enable S3 uploads.


## How to run
```
pip install backupdirs3

python backupdirs3.main.py -h

```

## Help
```
usage: backupdirs3 [-h] [-v] [-c CONFIG_FILE] [-m MONITORED_DIR] [-s S3_BUCKET] [-n NODE_NAME] [-b BACKUP_NAME] [-l LOCAL_BACKUP_DIR] [-k] [-d DELAY_BEFORE_UPLOAD]

This tool monitors a directory for changes, create a backup in the form of a zip file, and upload it to an AWS S3 bucket.

options:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -c CONFIG_FILE, --config-file CONFIG_FILE
                         yaml config file, mutually exclusive with other command line options 
                         default: /etc/backupdirs3/config.yaml
  -m MONITORED_DIR, --monitored-dir MONITORED_DIR
                         dir to monitor for changes 
                         default: /etc/backupdirs3
  -s S3_BUCKET, --s3-bucket S3_BUCKET
                         aws s3 bucket to upload backup zip files 
                         default: backupdirs3-bucket
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
  -i INCLUDE_FILES, --include-files INCLUDE_FILES
                         files to include into backup. Can specify multiple times. If not specified, ALL files are included. 
                         default: []
  -x EXCLUDE_FILES, --exclude-files EXCLUDE_FILES
                         files to exclude from backup. Can specify multiple times. If not specified, NO files are excluded. 
                         default: []
  -1, --one-time-run     perform backup and exit without further monitoring. 
                         default: False
```

## Configuration
By default, the tool looks for its configuration file at `/etc/backupdirs3/config.yaml`. 
The settings specified in the default config file are used as defaults and can be overridden by command-line options.

> [!IMPORTANT]
>
> When custom config file is specified via `-c` `--config-file`
> * no other command-line parameters are allowed
> * only settings from the specified config file are used
> * default config is ignored

```bash
backupdirs3 -c ./config.yaml
```

### Example Configuration File Explained
`config.yaml`:
```yaml
# Config file for the backup directory monitoring tool

# The directory to monitor for changes
# Must be an existing directory and cannot be the root directory ('/')
# User must have read permissions to all files within this dir
monitored_dir: "/etc/backupdirs3"

# AWS S3 bucket where the backup files will be uploaded
# This bucket must already exist, and the script should have the necessary permissions to upload to it
s3_bucket: "backupdirs3-s3-bucket"

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

# List of file patterns to include in the backup.
# Patterns can be specified using Unix-style wildcards (e.g., "*.txt" to include all text files).
# If not specified, all files in the monitored directory are included by default.
include_files:
  - "*.n3c"

# List of file patterns to exclude from the backup.
# Use Unix-style wildcards (e.g., "*.log" to exclude all log files).
# If not specified, no files are excluded by default.
exclude_files:
  - "*.bak"
  - "*.bkp"

# Do not monitor changes, perform one-time backup and exit immediately.
# It makes more sense to specify this flag as a command line parameter rather than in config file.
# Defaults to false.
one_time_run: false
```

## Future improvements

1. include/exclude filters for files inside dir [DONE]
2. encrypt zip archive before upload?
3. one-time backup without monitor loop [DONE]
4. backup to local dir only without s3 upload?
