# builtin
import logging
import os
import time
import datetime
import subprocess
from collections import deque
import typing
if typing.TYPE_CHECKING:
    from psutil import Process
    from typing import TypedDict, Tuple

    class BattleServerProcessInfo(TypedDict):
        pid: int
        name: str
        cpu_percent: float
        memory_percent: float
        create_time: int
    recordsType = Tuple[int, list[BattleServerProcessInfo]]

# 3rd
try:
    import psutil
    WITH_PSUTIL = True
except ImportError:
    WITH_PSUTIL = False

# int
import config
from managers.timeMgr import TimeMgr
from Implement.gameServerCommon.GameServerCommon import CommonServerMgr

BATTLE_SERVER_RESTART = f"cd {config.BattleServerShellPath} && bash svn_update.sh %s && bash ./restart.sh"


class BattleServerMgr(CommonServerMgr):
    def __init__(self, restartScript=BATTLE_SERVER_RESTART):
        super(BattleServerMgr, self).__init__(restartScript)

        self.recordJobId = None
        self.records: list["recordsType"] = []
        interval, maxLen = config.battleStatisticRecordInterval, config.battleStatisticRecordLen
        self.startRecord(interval, maxLen)

    def getRecordInfo(self):
        ret = {}
        recordLen = len(self.records)
        timeStamp = [None] * recordLen
        for ind, (ts, infos) in enumerate(self.records):
            for info in infos:
                for infoName in config.battleStatisticRecordItems:
                    if info["name"] not in ret:
                        ret[info["name"]] = {}
                    if infoName not in ret[info["name"]]:
                        ret[info["name"]][infoName] = [None] * recordLen
                    ret[info["name"]][infoName][ind] = info[infoName]

            timeStamp[ind] = int(ts)

        return {"statistic": ret, "timeStamp": timeStamp}

    def cancelRecord(self):
        if self.recordJobId is None:
            return
        logging.info("[battleServerRecord] cancel record ")
        TimeMgr.remove_schedule(self.recordJobId)
        self.recordJobId = None

    def startRecord(self, interval, maxLen):
        if maxLen == 0 or self.recordJobId is not None:
            logging.info("[battleServerRecord] len is 0, or already started")
            return
        logging.info("[battleServerRecord] start record ")
        self.recordJobId = "bs_cron_record_info"
        recordInterval = {'second': interval}
        self.records = deque([], maxlen=maxLen)
        TimeMgr.add_schedule_interval(recordInterval, self._cronRecord, self.recordJobId)

    def getProcessInfo(self):
        # ret: list[dict[battleServerProcessInfos, value]]
        if WITH_PSUTIL:
            return self._getProcessInfoByPsUtil()
        else:
            return self._getProcessInfoByPipe()

    def getSvnInfo(self):
        ret = {}
        # svn
        try:
            output = subprocess.check_output(["svn", "info"], cwd=config.BattleServerShellPath)
            output = output.decode("utf-8")
            lines = output.split("\n")
            for line in lines:
                if line.startswith("Revision:"):
                    ret['svnVersion'] = line.split(":")[1].strip()
                if line.startswith("URL:"):
                    url = line.split(" ")[1].strip()
                    # 对linux是分支信息是在这个位置
                    ret['svnBranch'] = url.split('/')[-5]
        except Exception as e:
            print("Error:", e)

        # battleVersion
        try:
            battleVersionFilePath = os.path.join(config.BattleServerShellPath, '../../Assets/Des/Lockstep/version.txt')
            with open(battleVersionFilePath, "r") as file:
                # 读取文件内容
                ret['battleVersion'] = file.read().strip()
        except Exception as e:
            print("Error:", e)

        return ret

    # private
    def _getProcessInfoByPipe(self):
        cmd = f"ps -eo pid,comm,pcpu,pmem,lstart | grep {config.BattleServerProcessPrefix}"
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        stdout, _ = process.communicate()
        output_lines = stdout.decode().split('\n')

        battle_processes_info = []
        for line in output_lines:
            fields = line.split()
            if len(fields) < 5:
                continue
            pid, name, cpu_percent, mem_percent, create_time = fields[0], fields[1], fields[2], fields[3], " ".join(fields[4:])
            if 'battle' in name.lower():
                # 将获取的信息添加到列表中
                process_info = {
                    'pid': pid,
                    'name': name,
                    'cpu_percent': cpu_percent,
                    'memory_percent': mem_percent,
                    'create_time': create_time
                }
                battle_processes_info.append(process_info)

        return battle_processes_info

    def _getProcessInfoByPsUtil(self):
        bsInfoList: list["Process"] = []
        for proc in psutil.process_iter():
            if proc.name().startswith(config.BattleServerProcessPrefix):
                bsInfoList.append(proc)

        retInfo = []
        for processInfo in bsInfoList:
            processInfoDict = processInfo.as_dict(config.BattleServerProcessInfos)
            if "create_time" in processInfoDict:
                # 转成可读的
                createDateTime = datetime.date.fromtimestamp(processInfoDict["create_time"])
                processInfoDict["create_time"] = createDateTime.strftime("%a %b %d %H:%M:%S %Y")
            retInfo.append(processInfoDict)

        logging.debug("process Info: %s", retInfo)
        return retInfo

    def _cronRecord(self):
        self.records.append((time.time(), self.getProcessInfo()))
