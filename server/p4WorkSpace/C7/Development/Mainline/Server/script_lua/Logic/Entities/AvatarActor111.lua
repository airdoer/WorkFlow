local math = math
local timerConst = kg_require("Logic.Const.TimerConst")

function AvatarActor:IsInSameLogic(serverId)
    return self.LogicServerID == serverId
end
