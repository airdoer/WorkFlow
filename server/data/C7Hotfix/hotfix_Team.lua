local groupClass = kg_require("Logic.Service.Team.Group")
function groupClass.Group:GetAllGroupMembers()
    local team
    local members = {}
    local teamInfos = self.owner.teamInfos
    for _, teamID in pairs(self.teamIDs) do
        team = teamInfos[teamID]
        for memberID, memberInfo in pairs(team.teamMemberIDList) do
            members[memberID] = memberInfo
        end
    end

    return members
end
