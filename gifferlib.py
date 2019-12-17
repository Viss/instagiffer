"""Common functions"""

import subprocess
import shlex

class GifferError(Exception):
    """Generic Error"""

class FFProbeError(GifferError):
    """FFProbe Error"""

def ffprobe(ffprobe_bin, filename, fields):
    if isinstance(fields, str):
        fields = [fields]

    fstring = ','.join(fields)
    cmd = [ffprobe_bin]
    cmd.extend('-v error -select_streams v:0'.split())
    cmd.extend(f'-show_entries stream={fstring} -of csv=p=0'.split())
    cmd.append(filename)
    cmd = shlex.join(cmd)
    output = subprocess.getoutput(cmd).strip().split(',')
    if len(output) != len(fields):
        raise FFProbeError("Output doesn't match fields")
    return output
