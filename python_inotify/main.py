import inotify.adapters
import os
import time
from pprint import pprint
from datetime import datetime

def _main():
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

if __name__ == '__main__':
    _main()