# builtin
import logging


# int
import config
from Implement.gameServerCommon.GameServerCommon import CommonServerMgr

defaultShellPath = config.GameServerShellPath
GAME_SERVER_RESTART = f"cd {defaultShellPath} && bash svn_update.sh %s && bash ./admin_restart_server.sh"


class GameServerMgr(CommonServerMgr):
    def __init__(self, restartScript=GAME_SERVER_RESTART, deleteShellPath=config.GameServerDeleteAccountPath):
        super(GameServerMgr, self).__init__(restartScript)
        self.deleteScript = f'cd {deleteShellPath} && sudo python3 main.py -ids %s'

# region deleteAccount
    # 这个是作为server来实际执行的
    def deleteAccount(self, nickName: str):
        # 通知踢人是删号脚本里做的
        if not nickName.isalnum():
            logging.info(f"delete account {nickName = } not valid")
            return
        logging.info("deleteAccount %s", nickName)
        runCommand = self.deleteScript % nickName
        self.runShellCmd(runCommand)
# endregion
