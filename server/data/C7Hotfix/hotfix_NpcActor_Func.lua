LOG_INFO_FMT("Hotfix_NpcActor_Func begin")

local npcActor = kg_require("Logic.Entities.NpcActor")
npcActor.NpcActor.testHotfixComponent = function(self)
    self:logInfoFmt("NpcActor testHotfixComponent %s", self.__cname)
    return "NpcActor testHotfixComponent " .. self.__cname
end

LOG_INFO_FMT("Hotfix_NpcActor_Func end")
