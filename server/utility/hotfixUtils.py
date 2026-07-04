
ClientResourceFlag = ";;;"  # 因为有本地加载hotfix的需求，所以这里需要用windows文件名的可用字符，而不能用|等特殊字符


class HotfixPlatform(object):
    UNKNOWN = 0
    WINDOWS = 1
    IOS = 2
    ANDROID = 3
    DS = 4  # ReviewServer(DedicatedServer)的CsFix


HotfixPlatformName2Type = {
    "StandaloneWindows64": HotfixPlatform.WINDOWS,
    "iOS": HotfixPlatform.IOS,
    "Android": HotfixPlatform.ANDROID,
    "DS": HotfixPlatform.DS
}


def isClientCsfix(hotfixName):
    return hotfixName.endswith(".csfix")


def isDedicatedServerCsFix(hotfixName):
    if not isClientCsfix(hotfixName):
        return False
    return '_DS_' in hotfixName


def getClientResourcePath(fullHotfixName):
    return fullHotfixName.split(ClientResourceFlag)
