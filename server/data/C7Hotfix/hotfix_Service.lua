LOG_INFO_FMT("Hotfix_Service begin")

local sa_report_utils = kg_require("Logic.Utils.ReportSADataUtils")
local champion_consts = kg_require("Shared.Const.ChampionConsts")
local championTroopService = kg_require("Logic.Service.ChampionTroopService")
function championTroopService.ChampionTroopService:onLoadTroopInfosForClear(rets)
    local ids = {}
    for _, ret in pairs(rets) do
        local troopID = ret.id
        local troopInfo = self:getTroopInfo(troopID)
        if troopInfo then
            self:disbandTroop(troopID, troopInfo)
            sa_report_utils.ReportSADataUtils.ReportChampionTroopAction(self, troopInfo, champion_consts.CHAMPION_TROOP_OP_TYPE.DISBAND, 0)
        end

        ids[#ids + 1] = troopID
    end

    Game.DBProxy:MongoDeleteMany(
            self:GetDatabaseName(),
            Enum.EDBCollectionName.CHAMPION_TROOP_INFO,
            { id = { ["$in"] = ids } },
            nil,
            nil,
            function(ret)
                local ok = ret[1]
                if not ok then
                    self:logErrorFmt("onLoadTroopInfosForClear MongoDeleteMany failed, errMsg:, ids:%v", ret, ids)
                    return
                end

                self:logInfoFmt("onLoadTroopInfosForClear MongoDeleteMany ok, errMsg:%v, ids:%v", ret, ids)
            end
    )
end

LOG_INFO_FMT("Hotfix_Service end")
