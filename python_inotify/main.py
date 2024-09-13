from datetime import datetime
from pprint import pprint
from zoneinfo import ZoneInfo
import argparse
import boto3
import hashlib
import inotify.adapters
import logging
import os
import sys
import tempfile
import time
import yaml
import zipfile

VERSION = "0.0.8-2-gb75013a"
DEFAULT_CONFIG_ENVVAR_PREFIX = "CONFIGMON"
DEFAULT_CONFIG_PATHS = [
    "/etc/powerfactors/configmon.yaml",
    "/etc/powerfactors/configmon.yml",
    # "configmon.yaml",
    # "configmon.yml",
]

settings = {}

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s: [%(name)s] %(message)s"
)


def load_config(path):
    with open(path, 'r') as file:
        config = yaml.safe_load(file)
    return config

def init():

    parser = argparse.ArgumentParser(
        description="This tool monitors a config directory for changes and backups the changes to S3"
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {VERSION}"
    )
    parser.add_argument(
        "-c",
        "--config-file",
        type=str,
        metavar="config.yaml",
        help=f"yaml config file to use instead of default chain: {DEFAULT_CONFIG_PATHS}",
    )
    args = parser.parse_args()

    settings = load_config("/etc/powerfactors/configmon.yaml")
    logging.info(f"config loaded: {settings}")
    if not os.path.isdir(settings['config_dir_src']):
        logging.error(
            f"not an existing directory! config_dir_src: {settings['config_dir_src']}"
        )
        sys.exit(11)
    if "/" == os.path.realpath(settings['config_dir_src']):
        logging.error(
            f"cannot monitor system root directory! config_dir_src: {settings['config_dir_src']}"
        )
        sys.exit(12)

    settings["resolved_config_dir"] = os.path.realpath(settings['config_dir_src'])

    s3 = boto3.resource("s3")
    bucket_exists = False
    for bucket in s3.buckets.all():
        if settings['s3_bucket_dst'] == bucket.name:
            bucket_exists = True
            break
    if not bucket_exists:
        logging.error(f"s3 bucket does not exist s3_bucket_dst: {settings['s3_bucket_dst']}")
        sys.exit(13)

    # logging.info(bucket.name)

    settings["resolved_s3_bucket_dst"] = settings['s3_bucket_dst']

    logging.info(f"config resolved: {settings}")
    return settings


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


def do_backup(directory):
    temp_zip = tempfile.NamedTemporaryFile(
        delete=False, prefix="backup_", suffix=".zip"
    )
    temp_path = os.path.realpath(temp_zip.name)
    zip_directory(directory, temp_path)
    temp_size = os.path.getsize(temp_path)
    logging.info(f"zip file ({temp_size}) bytes: {temp_path}")
    aws_s3_upload(
        temp_path, "aa-test-n3uron-backup", f"{get_iso8601_timestamp()}/backup.zip"
    )


def monitor_changes(directory):
    i = inotify.adapters.InotifyTree(directory)
    logging.info(f"Monitoring started on: {directory}")

    try:
        while True:
            config_dir_updated = False
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
                        logging.info(f"inotify {event_type}: {full_path}")
                        config_dir_updated = True
            if config_dir_updated:
                do_backup(directory)
                config_dir_updated = False
            else:
                logging.debug(f"No changes detected so far in {directory}")
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


def aws_s3_upload(local_file, remote_bucket, remote_file):
    s3 = boto3.resource("s3")
    s3.meta.client.upload_file(local_file, remote_bucket, remote_file)


####################################################################################################
# Main function
####################################################################################################


def _main():

    logging.info(get_iso8601_timestamp())
    cfg = init()
    aws_s3_ls()
    # aws_s3_upload(f"{directory}/file.log", "aa-test-n3uron-backup", f"{get_iso8601_timestamp()}/file.log")

    monitor_changes(os.path.realpath(cfg['resolved_config_dir']))
    logging.info("ok")


if __name__ == "__main__":
    _main()
