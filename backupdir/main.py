from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import boto3
import inotify.adapters
import logging
import os
import re
import sys
import tempfile
import time
import yaml
import zipfile

VERSION = "0.1.1-dirty"
DEFAULT_CONFIG_YAML = "/etc/backupdir/config.yaml"
DEFAULT_S3_BUCKET = "backupdir-s3-bucket"
DEFAULT_UPLOAD_COOLDOWN_SECONDS = 10
DEFAULT_KEEP_LOCAL_BACKUPS = False
DEFAULT_LOCAL_BACKUP_DIR = tempfile.gettempdir()
DEFAULT_NODE_NAME = os.uname().nodename
DEFAULT_MONITORED_DIR = "/etc/backupdir"
DEFAULT_BACKUP_NAME = "backup"
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s: [%(name)s] %(message)s"
)


# Decorator to measure execution time of a function
def time_this(func):

    def wrapped(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time_ms = (end_time - start_time) * 1000  # Convert to milliseconds
        logging.info(
            f"function '{func.__name__}' execution time: {execution_time_ms:.6f} milliseconds"
        )
        return result

    return wrapped


@time_this
# Function to get SHA1 checksums of files in a directory
def get_sha1_checksums(directory):
    checksums = {}
    for root, dirs, files in os.walk(directory):
        files.sort()
        for file in files:
            file_path = os.path.join(root, file)
            hasher = hashlib.sha1()
            try:
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hasher.update(chunk)
                checksums[file_path] = hasher.hexdigest()
            except Exception as e:
                logging.warning(f"Error processing {file_path}: {e}")
    return checksums


# @time_this
# # Function to get metadata of files in a directory
# def get_files_metadata(directory):
#     file_metadata_map = {}
#     for root, dirs, files in os.walk(directory):
#         files.sort()
#         for file in files:
#             file_path = os.path.join(root, file)
#             try:
#                 stats = os.stat(file_path)
#                 file_metadata_map[file_path] = stats
#             except FileNotFoundError:
#                 # If file is deleted between finding it and statting it
#                 continue
#             except PermissionError:
#                 # If permission is not granted to read file stats
#                 file_metadata_map[file_path] = "Permission Denied"
#     return file_metadata_map


# # Function to compare two dictionaries and return differences
# def compare_dictionaries(dict1, dict2):
#     differences = {}
#     all_keys = set(dict1.keys()).union(set(dict2.keys()))

#     for key in all_keys:
#         if dict1.get(key) != dict2.get(key):
#             differences[key] = {
#                 "old_value": dict1.get(key),
#                 "new_value": dict2.get(key),
#             }
#     return differences


# # Function to check python version
# def check_python_version():
#     major, minor = sys.version_info.major, sys.version_info.minor
#     if major < 3 or (major == 3 and minor < 7):
#         logging.warning(
#             f"You are using Python version {major}.{minor}. Dictionary key order may NOT be preserved."
#         )
#     else:
#         logging.info(
#             f"You are using Python version {major}.{minor}. Dictionary key order will be preserved."
#         )


# def diff_dir(directory):

#     check_python_version()

#     sums1 = get_sha1_checksums(directory)
#     metas1 = get_files_metadata(directory)

#     filename = f"{directory}/file.log"
#     with open(filename, "a") as file:
#         file.write(datetime.now().isoformat())

#     sums2 = get_sha1_checksums(directory)
#     metas2 = get_files_metadata(directory)

#     if sums1 != sums2:
#         logging.info("Checksums are different")
#         pprint(compare_dictionaries(sums1, sums2))
#     else:
#         logging.info("Checksums are the same")

#     if metas1 != metas2:
#         logging.info("Metadata is different")
#         pprint(compare_dictionaries(metas1, metas2))
#     else:
#         logging.info("Metadata is the same")


@time_this
def zip_directory(folder_path, output_path):
    with zipfile.ZipFile(
        output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(
                    file_path,
                    os.path.relpath(file_path, os.path.join(folder_path, "..")),
                )


def get_iso8601_timestamp(time):
    return time.strftime("%Y%m%dT%H%M%S%z")


def get_local_backup_file_prefix(time):
    return f"{config.node_name}-{config.backup_name}-{get_iso8601_timestamp(time)}."


def get_s3_backup_file_name(time):
    return f"{config.node_name}/{config.node_name}-{config.backup_name}-{get_iso8601_timestamp(time)}.zip"


def do_backup():
    time = datetime.now(ZoneInfo("UTC"))
    temp_zip = tempfile.NamedTemporaryFile(
        delete=False,
        dir=config.local_backup_dir,
        prefix=get_local_backup_file_prefix(time),
        suffix=".zip",
    )
    temp_path = os.path.realpath(temp_zip.name)
    try:
        zip_directory(config.monitored_dir, temp_path)
        temp_size = os.path.getsize(temp_path)
        logging.info(f"temp zip file ({temp_size}) bytes: {temp_path}")
        aws_s3_upload(temp_path, config.s3_bucket, get_s3_backup_file_name(time))
    finally:
        temp_zip.close()
        if not config.keep_local_backups:
            os.remove(temp_path)


def monitor_changes():
    directory = config.monitored_dir
    s3_bucket = config.s3_bucket
    i = inotify.adapters.InotifyTree(directory)
    logging.info(f"Monitoring started on: {directory}")

    try:
        while True:
            need_to_backup_config = False
            for event in i.event_gen(
                yield_nones=False, timeout_s=DEFAULT_UPLOAD_COOLDOWN_SECONDS
            ):
                (_, type_names, path, filename) = event
                for event_type in type_names:
                    full_path = f"{path}/{filename}"
                    if event_type in [
                        "IN_DELETE",
                        "IN_CREATE",
                        "IN_MODIFY",
                        "IN_MOVED_TO",
                        "IN_MOVED_FROM",
                    ]:
                        logging.info(f"change detected {event_type}: {full_path}")
                        need_to_backup_config = True
            if need_to_backup_config:
                do_backup()
                need_to_backup_config = False
            else:
                logging.debug(f"no changes detected so far in {directory}")
    except KeyboardInterrupt:
        logging.info("Monitoring stopped.")


@time_this
def aws_s3_upload(local_file, remote_bucket, remote_file):
    s3 = boto3.resource("s3")
    s3.meta.client.upload_file(local_file, remote_bucket, remote_file)
    logging.info(f"uploaded: {local_file} to aws s3 {remote_bucket}/{remote_file}")


####################################################################################################
# Init Config
####################################################################################################


def validate_monitored_dir(config_dir):
    logging.info(f"validating monitored_dir: {config_dir}")
    if not os.path.isdir(config_dir):
        logging.error(f"directory not exists monitored_dir: {config_dir}")
        sys.exit(11)
    if "/" == os.path.realpath(config_dir):
        logging.error(
            f"cannot monitor system root directory! monitored_dir: {config_dir}"
        )
        sys.exit(12)
    return os.path.realpath(config_dir)


def validate_s3_bucket(s3_bucket):
    logging.info(f"validating s3_bucket: {s3_bucket}")
    s3 = boto3.resource("s3")
    bucket_exists = False
    for bucket in s3.buckets.all():
        if s3_bucket == bucket.name:
            bucket_exists = True
            break
    if not bucket_exists:
        logging.error(f"s3 bucket does not exist s3_bucket: {s3_bucket}")
        sys.exit(13)
    return s3_bucket


def validate_against_regex(str, regex):
    logging.info(f"validating '{str}' against /{regex}/")
    pattern = re.compile(regex)
    if not pattern.match(str):
        logging.error(f"string: {str} does not match pattern /{regex}/")
        sys.exit(13)
    return str


def validate_node_name(name):
    logging.info(f"validating node_name: {name}")
    regex = r"^[a-z0-9.-]+$" # allow only lowercase letters, numbers, dots and hyphens
    return validate_against_regex(name, regex)


def validate_backup_name(name):
    logging.info(f"validating backup_name: {name}")
    regex = r"^[a-z0-9_-]+$" # allow only lowercase letters, numbers, underscores and hyphens
    return validate_against_regex(name, regex)


def validate_local_backup_dir(local_backup_dir):
    logging.info(f"validating local_backup_dir: {local_backup_dir}")
    if not os.path.isdir(local_backup_dir):
        logging.error(f"directory not exists local_backup_dir: {local_backup_dir}")
        sys.exit(14)
    return os.path.realpath(local_backup_dir)


def load_yaml(path):
    logging.info(f"loading yaml file: {path}")
    config = {}
    if not os.path.isfile(path):
        logging.warning(f"file not found: {path}")
    else:
        with open(path, "r") as file:
            config = yaml.safe_load(file)
            logging.info(f"yaml parsed: {config}")
    return config


def resolve_chain(key, default_value, *args):
    for arg in args:
        logging.debug(f"resolve_chain looking for key: '{key}' in {arg}")
        if key in arg and arg[key] != None:
            logging.debug(f"resolve_chain key: '{key}' resolved: {arg[key]}")
            return arg[key]
        else:
            logging.debug(f"resolve_chain key: '{key}' not found in {arg}")
    logging.info(f"resolve_chain key: '{key}' fallback to default: '{default_value}'")
    return default_value


class Config:
    def __init__(self, args_dict):
        cfg = load_yaml(resolve_chain("config_file", DEFAULT_CONFIG_YAML, args_dict))

        self.monitored_dir = validate_monitored_dir(
            resolve_chain("monitored_dir", DEFAULT_MONITORED_DIR, args_dict, cfg)
        )
        self.s3_bucket = validate_s3_bucket(
            resolve_chain("s3_bucket", DEFAULT_S3_BUCKET, args_dict, cfg)
        )
        self.node_name = validate_node_name(
            resolve_chain("node_name", DEFAULT_NODE_NAME, args_dict, cfg)
        )

        self.backup_name = validate_node_name(
            resolve_chain("backup_name", DEFAULT_BACKUP_NAME, args_dict, cfg)
        )

        self.local_backup_dir = validate_local_backup_dir(
            resolve_chain("local_backup_dir", DEFAULT_LOCAL_BACKUP_DIR, args_dict, cfg)
        )

        self.keep_local_backups = resolve_chain(
            "keep_local_backups", DEFAULT_KEEP_LOCAL_BACKUPS, args_dict, cfg
        )


parser = argparse.ArgumentParser(
    argument_default=argparse.SUPPRESS,
    formatter_class=argparse.RawTextHelpFormatter,
    description="This tool monitors a config directory for changes and backups the changes to S3",
)
parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {VERSION}")
parser.add_argument(
    "-c",
    "--config-file",
    type=str,
    help=f" yaml config file, mutually exclusive with other command line options \n default: {DEFAULT_CONFIG_YAML}",
)
parser.add_argument(
    "-m",
    "--monitored-dir",
    type=str,
    help=f" dir to monitor for changes \n default: {DEFAULT_MONITORED_DIR}",
)
parser.add_argument(
    "-s",
    "--s3-bucket",
    type=str,
    help=f" aws s3 bucket to upload backup zip files \n default: {DEFAULT_S3_BUCKET}",
)
parser.add_argument(
    "-n",
    "--node-name",
    type=str,
    help=f" node name to use as prefix for backup file \n default: {DEFAULT_NODE_NAME}",
)
parser.add_argument(
    "-b",
    "--backup-name",
    type=str,
    help=f" app name to use as suffix for backup file \n default: {DEFAULT_BACKUP_NAME}",
)
parser.add_argument(
    "-l",
    "--local-backup-dir",
    type=str,
    help=f" local dir to store backup zip files before upload \n default: {DEFAULT_LOCAL_BACKUP_DIR}",
)
parser.add_argument(
    "-k",
    "--keep-local-backups",
    action="store_true",
    help=f" do not delete backup zip files after upload to s3 \n default: {DEFAULT_KEEP_LOCAL_BACKUPS}",
)

args = parser.parse_args()
args_dict = vars(args)
if "config_file" in args_dict and len(args_dict) > 1:
    logging.error("--config-file and other options are mutually exclusive")
    sys.exit(2)

config = Config(args_dict)
logging.info(f"config: {config.__dict__}")


####################################################################################################
# Main function
####################################################################################################


def _main():

    monitor_changes()
    logging.info("ok")


if __name__ == "__main__":
    _main()
