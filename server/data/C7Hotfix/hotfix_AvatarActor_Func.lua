LOG_INFO_FMT("Hotfix_AvatarActor_Func begin")

local avatarActor = kg_require("Logic.Entities.AvatarActor")
avatarActor.AvatarActor.testHotfixComponent = function(self)
    self:logInfoFmt("AvatarActor testHotfixComponent %s", self.__cname)
    return "AvatarActor testHotfixComponent " .. self.__cname
end

LOG_INFO_FMT("Hotfix_AvatarActor_Func end")
