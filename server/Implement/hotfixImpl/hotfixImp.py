import config
import json
import os
from utility import const
from Implement.hotfixImpl import luaImp

def generateHotfix(hotfixPrepareInfo):

    # 传入的是两个lua文件的内容，形式类似于topData={}
    # 我需要对比这两个文件的差异，生成一个热更文件
    
    # local data = Game.TableData.GetRoleCreatePropConfigDataTable()
    # if not data then
    #     return
    # end
    # data[1200001][0]["Sex"] = 1
    hotfixType = luaImp.check_hotfix_type(hotfixPrepareInfo)
    if hotfixType == 'both':
        return {
            'code': 2,
            'errMsg': '文件包含Client和Server两种路径，无法生成Hotfix，只能包含一种',
            'hotfixContent': '',
            'diffInfo': []
        }
    elif hotfixType == '':
        return {
            'code': 2,
            'errMsg': '文件路径不是有效的Client/Server路径，无法生成Hotfix',
            'hotfixContent': '',
            'diffInfo': []
        }

    hotfixContent, all_raw_lists = luaImp.generate_hotfix_by_content(hotfixType, hotfixPrepareInfo)

    if hotfixContent == '':
        return {
            'code': 2,
            'errMsg': '文件无差异，无需Hotfix',
            'hotfixContent': hotfixContent,
            'diffInfo': []
        }
    else:
        return {
            'code': 0,
            'errMsg': '',
            'hotfixContent': hotfixContent,
            'diffInfo': all_raw_lists
        }

# template:
# print("hotfix xxxx start")
# ksbc_enable_patch(true)
# local data = Game.TableData.GetRoleCreatePropConfigDataTable()
# if not data then
#     return
# end
# data[1200001][0]["Sex"] = 1
# ksbc_enable_patch(false)
# print("hotfix xxxx end")

# print("hotfix xxxx start")
# ksbc_enable_patch(true)
# local fashionData = Game.TableData.GetFashionDataTable()\
# fashionData[4220150].IsHideInUI = true
# fashionData[4220151].IsHideInUI = true
# ksbc_enable_patch(false)
# print("hotfix xxxx end")