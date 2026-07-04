from dataclasses import dataclass, field


class ServerStatus(object):
    SERVER_CLOSED = '服务器未响应'
    SERVER_RUNNING = '服务器运行中'
    SERVER_CLOSING = '服务器关闭中'
    SERVER_RESTARTING = '服务器重启中'
    SERVER_ERROR = '服务器有错误'


@dataclass
class ServerConfig(object):
    # 这部分为配置中应该提供的
    Namespace: str = ''
    index: int = 0
    SvnVersion: str = ''
    TargetAddress: str = None  # battleServer连接到的战斗服ip:port
    ServerType: str = 'NamespaceBattleServer'  # 在界面上归类的类别


@dataclass
class ServerRuntimeInfo:
    serverStatus: ServerStatus = ServerStatus.SERVER_CLOSED
    serverDetailInfo: dict = field(default_factory=dict)
