ASASMoveByAnim = {}
Game = {}
Game.TableData = {}
Game.TableDataManager = {}
Game.WorldManager = {}

function Game.TableDataManager:GetLangStr(_val)
    return LuaLangString(_val)
end

function Game.TableDataManager:GetLangStrSplit(_val, _tag)
    return LuaLangStrSplit(_val, _tag)
end

function FVector(x, y, z)
    return LuaFVector(x or 0, y or 0, z or 0)
end

function FRotator(pitch, yaw, roll)
    return LuaFRotator(pitch or 0, yaw or 0, roll or 0)
end

function FVector2D(x, y)
    return LuaFVector2D(x or 0, y or 0)
end

function FQuat(x, y, z, w)
    return LuaFQuat(x or 0, y or 0, z or 0, w or 0)
end

function FColor(x, y, z, w)
    return LuaFColor(x or 0, y or 0, z or 0, w or 0)
end 

function unpack(t, i)
    i = i or 1
    if t[i] then
        return t[i], unpack(t, i + 1)
    end
end

function FTransform(...)
    local args = {...}
    local type = "FTransform"
    return LuaFTransform(type, unpack(args))
end
