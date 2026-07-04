# gameServer 和 battleServer 公用的一些

# builtin
import os
import time
import subprocess
import logging
import threading
from subprocess import STDOUT, check_output


# int
import config
from managers.timeMgr import TimeMgr


class CommonServerMgr(object):
    def __init__(self, restartScript):
        self.restartScript = restartScript
        self.timerCnt = 0
        self.restartTimerJobIds: set[str] = set()

# region restart
    def requestRestart(self, delay=0, targetSvnVersion=None):
        # TODO: 做个防抖 短时间不要太多次
        self._setRestartTimer(delay, targetSvnVersion)

    def cancelRestart(self, jobId=None):
        logging.info(f"cancel restart {jobId}")
        if jobId is not None:
            jobIds = self.restartTimerJobIds
        else:
            jobIds = [jobId]

        for id in jobIds:
            TimeMgr.remove_schedule(id)

    def getRestartSchedule(self):
        # ret: list[tuple(targetTime, targetSvnVersion)]
        ret = []
        for jobId in self.restartTimerJobIds:
            infos = jobId.split("_")
            targetTime = time.strftime('%H:%M:%S', time.localtime(infos[1]))
            targetSvn = infos[2]
            ret.append((targetTime, targetSvn))
        return ret

    def _getJobId(self, delay, targetSvnVersion):
        # ret: timerId_targetTime(ts)_svnVersion
        return f"{self._getNextTimerId()}_{int(time.time()) + delay}_{targetSvnVersion}"

    def _getNextTimerId(self):
        self.timerCnt += 1
        return self.timerCnt

    def _setRestartTimer(self, seconds, targetSvnVersion=None):
        logging.info("setRestartTimer {}".format(seconds))
        jobId = self._getJobId(seconds, targetSvnVersion)
        TimeMgr.add_schedule_once(seconds, lambda: self._doRestart(jobId, targetSvnVersion), jobId)
        self.restartTimerJobIds.add(jobId)

    def _doRestart(self, jobId, targetSvnVersion: str = None):
        if targetSvnVersion == '':
            targetSvnVersion = None
        if targetSvnVersion is not None and not targetSvnVersion.isnumeric():
            logging.info(f"doRestart {targetSvnVersion = } not valid")
            return
        execScript = self.restartScript % (targetSvnVersion or "")
        logging.info(f"dlx doRestart {jobId} script: {execScript} targetSvnVer:{targetSvnVersion}")
        self.runShellCmd(execScript)

    def runShellCmd(self, script):
        logging.info(f'add shell exec thread: {script}')
        t = threading.Thread(target=lambda: self._runShellCmdImp(script), daemon=True)
        t.start()

    def _runShellCmdImp(self, execScript):
        logging.info(f'exec: {execScript}')
        try:
            output = check_output(execScript, stderr=STDOUT, shell=True, timeout=config.ShellCmdTimeout, preexec_fn=os.setpgrp)
            logging.info(f"{execScript} ret: {output}")
        except subprocess.TimeoutExpired as e:
            partial_output = e.output.decode("utf-8")
            logging.info(f"{execScript} timeout: {partial_output}")
        except subprocess.CalledProcessError as e:
            logging.info(f"{execScript} return error: {e}")

# endregion
