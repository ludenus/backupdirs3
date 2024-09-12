import inotify.adapters
import os
import time
import hashlib
import zlib
import sys
from pprint import pprint
from datetime import datetime

# Decorator to measure execution time of a function
def time_this(func):
    def wrapped(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time_ms = (end_time - start_time) * 1000  # Convert to milliseconds
        print(f"Function '{func.__name__}' execution time: {execution_time_ms:.6f} milliseconds")  # Print function name and execution time
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
                print(f"Error processing {file_path}: {e}")
    return checksums

@time_this
# Function to get CRC32 checksums of files in a directory
def get_crc32_checksums(directory):
    checksums = {}
    for root, dirs, files in os.walk(directory):
        files.sort()
        for file in files:
            file_path = os.path.join(root, file)
            crc32 = 0
            try:
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        crc32 = zlib.crc32(chunk, crc32)
                checksums[file_path] = format(crc32 & 0xFFFFFFFF, '08x')  # Format as hex
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
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
                'old_value': dict1.get(key),
                'new_value': dict2.get(key)
            }
    return differences

# Function to check for file changes using inotify
def inotify_check():
    cwd = os.getcwd()
    watched_dir = f"{cwd}/watched"
    filename= f"{watched_dir}/file.log"
    print(f"watched_dir: {watched_dir}")
    i = inotify.adapters.InotifyTree(watched_dir)
    with open(filename, 'a') as file:
        file.write(datetime.now().isoformat())
    events = i.event_gen(yield_nones=False, timeout_s=1)
    events = list(events)
    pprint(events)

# Function to check python version
def check_python_version():
    major, minor = sys.version_info.major, sys.version_info.minor
    if major < 3 or (major == 3 and minor < 7):
        print("WARNING: You are using Python version {}.{}. Dictionary key order may not be preserved."
              .format(major, minor))
    else:
        print("INFO: You are using Python version {}.{}. Dictionary key order will be preserved."
              .format(major, minor))

def _main():
    check_python_version()
    cwd = os.getcwd()
    watched_dir = f"{cwd}/watched"

    sums1 = get_sha1_checksums(watched_dir)
    metas1 = get_files_metadata(watched_dir)

    filename= f"{watched_dir}/file.log"
    with open(filename, 'a') as file:
        file.write(datetime.now().isoformat())
    
    sums2 = get_sha1_checksums(watched_dir)
    metas2 = get_files_metadata(watched_dir)

    if(sums1!=sums2):
        print("Checksums are different")
        pprint(compare_dictionaries(sums1, sums2))
    else:
        print("Checksums are the same")


    if(metas1!=metas2):
        print("Metadata is different")
        pprint(compare_dictionaries(metas1, metas2))
    else:
        print("Metadata is the same")

    print("ok")

if __name__ == '__main__':
    _main()