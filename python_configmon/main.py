from datetime import datetime
from pprint import pprint
from zoneinfo import ZoneInfo
import argparse
import boto3
import hashlib
import inotify.adapters
import logging
import os
import re
import sys
import tempfile
import time
import yaml
import zipfile

VERSION = '0.1.0'
DEFAULT_CONFIG_YAML = "/etc/powerfactors/configmon.yaml"
DEFAULT_MONITORED_DIR = "/opt/n3uron/config"
DEFAULT_S3_BUCKET = "n3uron-backup"

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
            f"Function '{func.__name__}' execution time: {execution_time_ms:.6f} milliseconds"
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


@time_this
# Function to get metadata of files in a directory
def get_files_metadata(directory):
    file_metadata_map = {}
    for root, dirs, files in os.walk(directory):
        files.sort()
        for file in files:
            file_path = os.path.join(root, file)
            try:
                stats = os.stat(file_path)
                file_metadata_map[file_path] = stats
            except FileNotFoundError:
                # If file is deleted between finding it and statting it
                continue
            except PermissionError:
                # If permission is not granted to read file stats
                file_metadata_map[file_path] = "Permission Denied"
    return file_metadata_map


# Function to compare two dictionaries and return differences
def compare_dictionaries(dict1, dict2):
    differences = {}
    all_keys = set(dict1.keys()).union(set(dict2.keys()))

    for key in all_keys:
        if dict1.get(key) != dict2.get(key):
            differences[key] = {
                "old_value": dict1.get(key),
                "new_value": dict2.get(key),
            }
    return differences


# Function to check python version
def check_python_version():
    major, minor = sys.version_info.major, sys.version_info.minor
    if major < 3 or (major == 3 and minor < 7):
        logging.warning(
            f"You are using Python version {major}.{minor}. Dictionary key order may NOT be preserved."
        )
    else:
        logging.info(
            f"You are using Python version {major}.{minor}. Dictionary key order will be preserved."
        )


def diff_dir(directory):

    check_python_version()

    sums1 = get_sha1_checksums(directory)
    metas1 = get_files_metadata(directory)

    filename = f"{directory}/file.log"
    with open(filename, "a") as file:
        file.write(datetime.now().isoformat())

    sums2 = get_sha1_checksums(directory)
    metas2 = get_files_metadata(directory)

    if sums1 != sums2:
        logging.info("Checksums are different")
        pprint(compare_dictionaries(sums1, sums2))
    else:
        logging.info("Checksums are the same")

    if metas1 != metas2:
        logging.info("Metadata is different")
        pprint(compare_dictionaries(metas1, metas2))
    else:
        logging.info("Metadata is the same")


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


def get_backup_file_name():
    return f"{config.node_name}/{config.node_name}-backup-{get_iso8601_timestamp()}.zip"


def do_backup(directory, s3_bucket):
    temp_zip = tempfile.NamedTemporaryFile(
        delete=False, prefix="backup_", suffix=".zip"
    )
    temp_path = os.path.realpath(temp_zip.name)
    try:
        zip_directory(directory, temp_path)
        temp_size = os.path.getsize(temp_path)
        logging.info(f"temp zip file ({temp_size}) bytes: {temp_path}")
        aws_s3_upload(temp_path, s3_bucket, get_backup_file_name())
    finally:
        temp_zip.close()
        os.remove(temp_path)

def monitor_changes():
    directory = config.monitored_dir
    s3_bucket = config.s3_bucket
    i = inotify.adapters.InotifyTree(directory)
    logging.info(f"Monitoring started on: {directory}")

    try:
        while True:
            need_to_backup_config = False
            for event in i.event_gen(yield_nones=False, timeout_s=10):
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
                do_backup(directory, s3_bucket)
                need_to_backup_config = False
            else:
                logging.debug(f"no changes detected so far in {directory}")
    except KeyboardInterrupt:
        logging.info("Monitoring stopped.")


def get_iso8601_timestamp():
    # Get the current time with timezone
    timezone = ZoneInfo("UTC")
    current_time = datetime.now(timezone)

    # Format the timestamp without dashes or colons
    compact_timestamp = current_time.strftime("%Y%m%dT%H%M%S%z")

    return compact_timestamp


def aws_s3_ls():
    s3 = boto3.resource("s3")
    for bucket in s3.buckets.all():
        logging.info(bucket.name)


@time_this
def aws_s3_upload(local_file, remote_bucket, remote_file):
    s3 = boto3.resource("s3")
    s3.meta.client.upload_file(local_file, remote_bucket, remote_file)
    logging.info(f"uploaded: {local_file} to aws s3 {remote_bucket}/{remote_file}")


def validate_config_dir(config_dir):
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


def validate_node_name(node_name):
    regex = r"^[a-z0-9.-]+$"
    pattern = re.compile(regex)
    if not pattern.match(node_name):
        logging.error(f"does not match pattern /{regex}/   node_name: {node_name}")
        sys.exit(13)
    return node_name


####################################################################################################
# Init Config
####################################################################################################


def load_yaml(path):
    logging.info(f"loading yaml file: {path}")
    if not os.path.isfile(path):
        logging.error(f"file not found: {path}")
        exit(1)
    with open(path, "r") as file:
        config = yaml.safe_load(file)
    return config


class Config:
    def __init__(self, yaml_file):
        yaml = load_yaml(yaml_file)
        logging.info(f"validating loaded config: {yaml}")
        self.monitored_dir = validate_config_dir(
            yaml.get("monitored_dir")
            if yaml.get("monitored_dir")
            else DEFAULT_MONITORED_DIR
        )
        self.s3_bucket = validate_s3_bucket(
            yaml.get("s3_bucket") if yaml.get("s3_bucket") else DEFAULT_S3_BUCKET
        )
        self.node_name = validate_node_name(
            yaml.get("node_name") if yaml.get("node_name") else os.uname().nodename
        )


parser = argparse.ArgumentParser(
    description="This tool monitors a config directory for changes and backups the changes to S3"
)
parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {VERSION}")
parser.add_argument(
    "-c",
    "--config-file",
    type=str,
    metavar="config.yaml",
    help=f"yaml config file to use instead of default: {DEFAULT_CONFIG_YAML}",
)
args = parser.parse_args()

if args.config_file:
    config = Config(args.config_file)
else:
    config = Config(DEFAULT_CONFIG_YAML)


####################################################################################################
# Main function
####################################################################################################


def _main():

    logging.info(f"config: {config.__dict__}")
    aws_s3_ls()
    # aws_s3_upload(f"{directory}/file.log", "aa-test-n3uron-backup", f"{get_iso8601_timestamp()}/file.log")
    monitor_changes()
    logging.info("ok")


if __name__ == "__main__":
    _main()
