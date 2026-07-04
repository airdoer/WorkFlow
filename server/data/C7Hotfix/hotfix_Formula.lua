LOG_INFO_FMT("-----------> hotfix_fuzuotao_185257 start, formula hotfix---------------")

local math = math
local math_round = function(num) return math.floor(num + 0.5) end
local math_pow = function(x, y) return x ^ y end
local max = math.max
local Max = math.max
local min = math.min
local Min = math.min
local ceil = math.ceil
local Ceil = math.ceil
local floor = math.floor
local Floor = math.floor
local round = math_round
local Round = math_round
local abs = math.abs
local Abs = math.abs
local random = math.random
local Random = math.random
local pow = math_pow
local Pow = math_pow
local power = math_pow
local Power = math_pow
local Ln = math.log
local Cos = math.cos

local formulaFuncData = kg_require("Data.Formula.FightFormulaFuncData").AllformulaFunc

function __Rate_Dizzy(a, d, FDIn, FDOut)
    if a.DizzyAcc-d.DizzyEva+850==0 then
        return 851
    elseif a.DizzyAcc-d.DizzyEva+850>0 then
        return min(1,max(-0.5,0.5*(a.DizzyAcc-d.DizzyEva)/(a.DizzyAcc-d.DizzyEva+850)))+1
    else
        return -min(1,max(-0.5,0.5*(a.DizzyAcc-d.DizzyEva)/(a.DizzyAcc-d.DizzyEva+850)))+1
    end
end

function __Rate_HitDown(a, d, FDIn, FDOut)
    if a.HitDownAcc-d.HitDownEva+850==0 then
        return 851
    elseif a.HitDownAcc-d.HitDownEva+850>0 then
        return min(1,max(-0.5,0.5*(a.HitDownAcc-d.HitDownEva)/(a.HitDownAcc-d.HitDownEva+850)))+1
    else
        return -min(1,max(-0.5,0.5*(a.HitDownAcc-d.HitDownEva)/(a.HitDownAcc-d.HitDownEva+850)))+1
    end
end

formulaFuncData.Rate_Dizzy = __Rate_Dizzy
formulaFuncData.Rate_DodgeLimit = __Rate_DodgeLimit


local FormulaMgr = kg_require("Logic.Utils.Formula.FormulaMgr")

FormulaMgr.GetFormulaFuncByName = function(formulaName)
    -- return FormulaEnv[formulaName]
    return formulaFuncData[formulaName]
end

FormulaMgr.CallFormula = function(formulaName, ...)
    -- local formulaFunc = FormulaEnv[formulaName]
    local formulaFunc = formulaFuncData[formulaName]
    if formulaFunc == nil then
        LOG_WARN_FMT("CallFormula %s, not found the formula", formulaName)
        return false
    end

    return FormulaMgr.CheckFormulaReturn(formulaName, xpcall(formulaFunc, FormulaMgr.__FormulaErrorHandler, ...))
end

FormulaMgr.CallFormulaNoSafe = function(formulaName, ...)
    -- local formulaFunc = FormulaEnv[formulaName]
    local formulaFunc = formulaFuncData[formulaName]
    if formulaFunc == nil then
        LOG_ERROR_FMT("CallFormula %s, not found the formula", formulaName)
        return false
    end

    return formulaFunc(...)
end

LOG_INFO_FMT("-----------> hotfix_fuzuotao_185257 start, formula hotfix---------------")