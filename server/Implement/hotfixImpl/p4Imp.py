import config
import json
import os
from utility import p4Utils


def getFileName(p4filePath):
    # 从p4filePath中提取文件名，例如//C7/Development/Mainline/Server/script_lua/Data/Excel/FStatePropData#2.lua -> FStatePropData#2.lua
    # 还有一种情况是FStatePropData.lua#2，需要提取FStatePropData.lua
    fileName = os.path.basename(p4filePath)
    fileName = fileName.split('#')[0]
    fileName = fileName.split('.')[0]
    return fileName


def getFileContent(p4filePath):
    # filePath是类似//C7/Development/Mainline/Server/script_lua/Data/Excel/FStatePropData#2.lua的形式
    # 我需要找到本地文件夹中p4WorkSpace下/Server/script_lua/Data/Excel/FStatePropData#2.lua对应的文件并返回，如果文件不存在，那么返回错误信息
    if not p4filePath.startswith('//'):
        return {
            'code': -1,
            'errMsg': '文件路径错误，必须以//开头，示例：//C7/Development/Mainline/Server/script_lua/Data/Excel/FStatePropData.lua#2',
            'fileContent': ''
        }

    # 使用config中的P4_WORKSPACE_DIRECTORY配置
    localFilePath = os.path.join(config.P4_WORKSPACE_DIRECTORY, p4filePath.replace("//", ""))
    
    if not os.path.exists(localFilePath):
        # 使用p4指令查看文件是否存在，如果存在，那么下载到config.P4_WORKSPACE_DIRECTORY下的对应目录中
        if not p4Utils.p4_file_exists(p4filePath):
            return {
                'code': -2,
                'errMsg': f'文件不存在: {p4filePath}',
                'fileContent': ''
            }
        # 下载文件到指定目录，递归创建文件夹
        if not p4Utils.download_file(p4filePath, localFilePath):
            return {
                'code': -3,
                'errMsg': f'文件下载失败: {p4filePath}',
                'fileContent': ''
            }
        else:
            with open(localFilePath, 'r', encoding='utf-8') as f:
                content = f.read()
                return {
                    'code': 0,
                    'errMsg': '',
                    'fileContent': content
                }
    else:
        with open(localFilePath, 'r', encoding='utf-8') as f:
            content = f.read()
            return {
                'code': 0,
                'errMsg': '',
                'fileContent': content
            }
