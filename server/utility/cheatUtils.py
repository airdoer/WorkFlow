# @program c1
# @author chenzhixu@kuaishou.com
# @date 2024/12/4 11:19
# @description:
#   something

from utility.const import BattleCheatPriority


def cheatOpCanOverride(oldCheatOp, newCheatOp):
    if BattleCheatPriority[oldCheatOp] >= BattleCheatPriority[newCheatOp]:
        return False
    return True
