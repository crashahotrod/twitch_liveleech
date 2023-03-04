import os
from signal import SIGKILL
for root, dirs, files in os.walk(r"/root/"):
    for file in files:
        if file.endswith('.pid'):
            pidFile = root + "/" + file
            with open(pidFile) as f:
                pid = int(f.readline())
                os.kill(pid, SIGKILL)
print('Finished Successfully')
