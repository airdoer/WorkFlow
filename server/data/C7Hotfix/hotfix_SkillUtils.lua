function GetRoleSkillRowBySkillId(tableData, skillId)
    local skillId2UniqueIdMap = tableData.Get_skillId2UniqueIdMap()
    local uniqueIdRow = skillId2UniqueIdMap[skillId]
    if uniqueIdRow == nil then
        local newSkillId2UniqueIdMap = tableData.Get_newSkillId2UniqueIdMap()
        local newUniqueIdRow = newSkillId2UniqueIdMap[skillId]
        if newUniqueIdRow then
            return tableData.GetFellowSkillUnlockDataRow(newUniqueIdRow.ID)
        end
    else
        return tableData.GetRoleSkillUnlockDataRow(uniqueIdRow.ID)
    end
end

local skillUtils = kg_require("Shared.Utils.SkillUtils")
skillUtils.GetRoleSkillRowBySkillId = GetRoleSkillRowBySkillId