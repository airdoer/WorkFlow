class ReviewStatusRetCode:
    ReviewSuccess = 0  # 设置重新校验成功
    UpSuccess = 1  # 设置优先级成功
    CheckSuccess = 2  # 更新校验结果成功
    CommentSuccess = 3  # 更新备注成功
    SetReviewNotYet = 1001  # 设置机器重新校验但是状态还是未校验
    SetUpButAlready = 1002  # 设置机器优先校验但是已经校验
    BattleNotExist = 1003  # 战斗不存在

    RequestArgsError = 1999  # 请求参数有误


class CheatStatusRetCode:
    UpdateSuccess = 0  # 设置更新成功
    AlreadyHasCheatFlag = 1  # 已有cheatOp
    BattleNotExist = 1003  # 战斗不存在
