local math = math

local formulaUtilApi = kg_require("Logic.Utils.Formula.FormulaUtilApi")

function __Arena_12V12ScoreCalc(_arg1, _arg2, _arg3, _arg4, _arg5, _arg6)
    local ScoreHigh = _arg1*_arg1*_arg1+ _arg2*_arg2*_arg2+ _arg3*_arg3*_arg3 + _arg4*_arg4*_arg4  + _arg5*_arg5*_arg5 + _arg6*_arg6*_arg6
    local ScoreLow  = _arg1*_arg1 +_arg2*_arg2 + _arg3*_arg3 + _arg4*_arg4 + _arg5*_arg5 + _arg6*_arg6
    
    if ScoreLow == 0 then
       return 0
    end
    
    return ScoreHigh/ScoreLow
end


CommonFormula = CommonFormula or {}
for k, _ in pairs(CommonFormula) do CommonFormula[k] = nil end
CommonFormula.Arena_12V12ScoreCalc = __Arena_12V12ScoreCalc