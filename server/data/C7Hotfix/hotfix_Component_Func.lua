LOG_INFO_FMT("Hotfix_Component_Func begin")

function testHotfixComponent(self)
    self:logInfoFmt("Hotfix_Component_Func DebugComponent testHotfixComponent %s", self.__cname)
    return "Hotfix_Component_Func DebugComponent testHotfixComponent " .. self.__cname
end
HotfixComponentFunction("DebugComponent", "testHotfixComponent", testHotfixComponent)

LOG_INFO_FMT("Hotfix_Component_Func end")