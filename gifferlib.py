"""Common functions"""

import sys
import os
import re
import glob
import time
import locale
import logging
import subprocess
import shlex
from queue import Queue

import tkinter

try:
    import win32api
    import winsound
except ImportError:
    pass

class GifferError(Exception):
    """Generic Error"""

class FFProbeError(GifferError):
    """FFProbe Error"""

def ffprobe(ffprobe_bin, filename, fields):
    """Retrieves ffprobe information about a video"""
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

# THAR BE DRAGONS
# This is all original instagiffer code past this point, prob needs to either
# be removed or refactored to something less retarded

# pylint: disable=invalid-name,broad-except,missing-function-docstring
# pylint: disable=too-many-locals,too-many-branches

ON_POSIX = 'posix' in sys.builtin_module_names

def is_mac():
    """Return true if running on a MAC"""
    return sys.platform == 'darwin'


def is_pc():
    """Return true if running on windows"""
    return sys.platform == 'win32'


def OpenFileWithDefaultApp(fileName):
    """Open a file in the application associated with this file extension"""
    if sys.platform == 'darwin':
        os.system('open ' + fileName)
    else:
        try:
            os.startfile(fileName)  # pylint: disable=no-member
        except Exception:
            msg = "Unable to open! "
            msg += f"I wasn't allowed to open '{fileName}'. "
            msg += "You will need to perform this task manually."
            tkinter.messagebox.showinfo(msg)


def GetFileExtension(filename):
    _, fext = os.path.splitext(filename)

    if fext is None:
        return ""

    fext = str(fext).lower()
    fext = fext.strip('.')
    return fext


def AudioPlay(wavPath):
    if is_mac():
        if wavPath is not None:
            subprocess.call(["afplay", wavPath])  # blocks
    elif is_pc():
        if wavPath is None:
            winsound.PlaySound(None, 0)
        else:
            winsound.PlaySound(
                wavPath, winsound.SND_FILENAME | winsound.SND_ASYNC)
    else:  # linux @leanrum (works on my machine) TODO change this shit
        if wavPath is not None:
            subprocess.call(["aplay", wavPath])  # blocks

    return True


def IsPictureFile(fileName):
    return GetFileExtension(fileName) in ['jpeg', 'jpg', 'png', 'bmp', 'tif']


def IsUrl(s):
    urlPatterns = re.compile(r'^(www\.|https://|http://)', re.I)
    return urlPatterns.match(s)


def GetLogPath():
    return os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + 'instagiffer-event.log'

#
# Mostly for Windows. Converts path into short form to bypass unicode headaches
#


def CleanupPath(path):
    #
    # Deal with Unicode video paths. On Windows, simply DON'T
    # deal with it. Use short names and paths instead :S
    #

    if is_pc():
        try:
            path.decode('ascii')
        except Exception:
            path = win32api.GetShortPathName(path)
    return path


#
# Re-scale a value
#

def ReScale(val, oldScale, newScale):
    OldMax = oldScale[1]
    OldMin = oldScale[0]
    NewMax = newScale[1]
    NewMin = newScale[0]
    OldValue = val
    OldRange = (OldMax - OldMin)
    NewRange = (NewMax - NewMin)
    NewValue = (((OldValue - OldMin) * NewRange) / OldRange) + NewMin
    return NewValue


#
# norecurse decorator
#
def norecurse(func):
    func.called = False

    def f(*args, **kwargs):
        if func.called:
            print("Recursion!")
            return False
        func.called = True
        result = func(*args, **kwargs)
        func.called = False
        return result
    return f

#
# Convert a time or duration (hh:mm:ss.ms) string into a value in milliseconds
#


def DurationStrToMillisec(string, throwParseError=False):
    try:
        return float(string) * 1000
    except ValueError:
        pass
    if string is not None:
        r = re.compile(r'[^\d]+')
        tokens = r.split(string)
        vidLen = ((int(tokens[0]) * 3600) + (int(tokens[1])
                                             * 60) + (int(tokens[2]))) * 1000 + int(tokens[3])
        return vidLen
    if throwParseError:
        raise ValueError("Invalid duration format")

    return 0


def DurationStrToSec(durationStr):
    ms = DurationStrToMillisec(durationStr)

    if ms == 0:
        return 0
    # return int((ms + 500) / 1000) # Rouding
    return int(ms/1000)  # Floor


def MillisecToDurationComponents(msTotal):
    secTotal = msTotal / 1000
    h = int(secTotal / 3600)
    m = int((secTotal % 3600) / 60)
    s = int(secTotal % 60)
    ms = int(msTotal % 1000)

    return [h, m, s, ms]


def MillisecToDurationStr(msTotal):
    dur = MillisecToDurationComponents(msTotal)
    return "%02d:%02d:%02d.%03d" % (dur[0], dur[1], dur[2], dur[3])


def CountFilesInDir(dirname, filenamePattern=None):
    if filenamePattern is None:
        return len([name for name in os.listdir(dirname)
                    if os.path.isfile(os.path.join(dirname, name))])
    fileglobber = dirname + filenamePattern + '*'
    return len(glob.glob(fileglobber))

#
# Run non-blocking
#

#
# Converts process output to status bar messages - there is some cross-cutting here
#


def DefaultOutputHandler(stdoutLines, stderrLines, cmd):
    s = None
    i = False

    for outData in [stdoutLines, stderrLines, cmd]:
        if not outData:
            continue

        if isinstance(outData, list):
            outData = " ".join(outData).encode('ascii')

        # youtube dl

        youtubeDlSearch = re.search(
            rb'\[download\]\s+([0-9\.]+)% of', outData, re.MULTILINE)
        if youtubeDlSearch:
            i = int(float(youtubeDlSearch.group(1)))
            s = "Downloaded %d%%..." % (i)

        # ffmpeg frame extraction progress
        ffmpegSearch = re.search(
            rb'frame=.+time=(\d+:\d+:\d+\.\d+)', outData, re.MULTILINE)
        if ffmpegSearch:
            secs = DurationStrToMillisec(ffmpegSearch.group(1))
            s = "Extracted %.1f seconds..." % (secs/1000.0)

        # imagemagick - figure out what we're doing based on comments
        imSearch = re.search(
            rb'^".+(convert\.exe|convert)".+-comment"? "([^"]+):(\d+)"', outData)
        if imSearch:
            n = int(imSearch.group(3))

            if n == -1:
                s = "%s" % (imSearch.group(2))
            else:
                i = n
                s = "%d%% %s" % (i, imSearch.group(2))

    return s, i


#
# Prompt User
#
def NotifyUser(title, msg):
    return tkinter.messagebox.showinfo(title, msg)

def RunProcess(cmd, callback=None, returnOutput=False,
               callBackFinalize=True, outputTranslator=DefaultOutputHandler):
    """Run a process"""
    logging.info("Running Command: %s", cmd)

    env = os.environ.copy()

    if is_pc():
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
    else:
        startupinfo = None
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)

    pipe = subprocess.Popen(
        cmd, startupinfo=startupinfo, shell=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env, bufsize=1, close_fds=ON_POSIX)
    qOut = Queue()
    qErr = Queue()
    for line in pipe.stdout.readlines():
        qOut.put(line)
    for line in pipe.stderr.readlines():
        qErr.put(line)

    callbackReturnedFalse = False

    stdout = ""
    stderr = ""

    percent = None
    while True:
        statusStr = None
        stderrLines = None
        stdoutLines = None

        try:
            while True:  # Exhaust the queue
                stdoutLines = qOut.get_nowait()
                stdout += stdoutLines
        except Exception:
            pass

        try:
            while True:
                stderrLines = qErr.get_nowait()
                stderr += stderrLines
        except Exception:
            pass

        if outputTranslator is not None:
            # try:
            statusStr, percentDoneInt = outputTranslator(
                stdoutLines, stderrLines, cmd)

            if isinstance(percentDoneInt, int):
                percent = percentDoneInt
            elif percent is not None:
                percentDoneInt = percent

            # except:
            #    pass

        # Caller wants to abort!
        if callback is not None and callback(percentDoneInt, statusStr) is False:
            try:
                pipe.terminate()
                pipe.kill()
            except Exception:
                logging.error(
                    "RunProcess: kill() or terminate() caused an exception")

            callbackReturnedFalse = True
            break

        # Check if done
        if pipe.poll() is not None:
            break

        # Polling frequency. Lengthening this will decrease responsiveness
        time.sleep(0.1)

    # Notify callback of exit. Check callballFinalize so we don't prematurely reset the progress bar
    if callback is not None and callBackFinalize is True:
        callback(True)

    # Callback aborted command
    if callbackReturnedFalse:
        logging.error("RunProcess was aborted by caller")
        # return False

    # result
    try:
        remainingStdout = ""
        remainingStderr = ""
        remainingStdout, remainingStderr = pipe.communicate()
    except IOError as e:
        logging.error("Encountered error communicating with sub-process %s", e)

    success = (pipe.returncode == 0)
    if isinstance(remainingStdout, bytes):
        remainingStdout = remainingStdout.decode('ascii')
    stdout += remainingStdout
    if isinstance(remainingStderr, bytes):
        remainingStderr = remainingStderr.decode('ascii')
    stderr += remainingStderr

    # Logging
    logging.info("return: %s", success)
    logging.info("stdout: %s", stdout)
    logging.error("stderr: %s", stderr)

    if returnOutput:
        return stdout, stderr  # , success
    return success


#
# Create working directory
#

def CreateWorkingDir(conf):
    tempDir = None

    # See if they specified a custom dir
    if conf.ParamExists('paths', 'workingDir'):
        tempDir = conf.GetParam('paths', 'workingDir')

    appDataRoot = ''

    # No temp dir configured
    if not tempDir:
        if is_mac():
            appDataRoot = os.path.expanduser("~") + '/Library/Application Support/'
            tempDir = appDataRoot + 'Instagiffer/'
        else:
            appDataRoot = os.path.expanduser("~") + os.sep
            tempDir = appDataRoot + '.instagiffer' + os.sep + 'working'

    # Pre-emptive detection and correction of language issues
    try:
        tempDir.encode(locale.getpreferredencoding())
    except UnicodeError:
        logging.info(
            "Users home directory is problematic due to non-latin characters: %s",
            tempDir)
        tempDir = GetFailSafeDir(conf, tempDir)

    # Try to create temp directory
    if not os.path.exists(tempDir):
        os.makedirs(tempDir)
        if not os.path.exists(tempDir):
            logging.error("Failed to create working directory: %s", tempDir)
            return ""

    logging.info("Working directory created: %s", tempDir)
    return tempDir


#
# For language auto-fix
#
def GetFailSafeDir(conf, badPath):
    path = badPath

    if is_pc():
        goodPath = conf.GetParam('paths', 'failSafeDir')
        if not os.path.exists(goodPath):
            if tkinter.messagebox.askyesno(
                    "Automatically Fix Language Issue?",
                    "It looks like you are using a non-latin locale. "
                    f"Can Instagiffer create directory {goodPath} to solve this issue?"):
                err = False
                try:
                    os.makedirs(goodPath)
                except Exception:
                    err = True

                if os.path.exists(goodPath):
                    path = goodPath
                else:
                    err = True

                if err:
                    tkinter.messagebox.showinfo(
                        "Error Fixing Language Issue",
                        "Failed to create '{goodPath}'. "
                        "Please make this directory manually in Windows Explorer, "
                        "then restart Instagiffer.")
        else:
            path = goodPath

    return path
