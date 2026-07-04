#!/bin/bash

# dumpData.sh - 导出玩家数据脚本
# 用法: ./dumpData.sh [-ts SERVER] [-ta AVATARID] [-fp FILEPATH]

set -e  # 任何命令出错则退出

# ===== 参数配置 =====
# 可以在这里设置默认值，或通过命令行参数覆盖
TARGET_SERVER=""
TARGET_AVATARID=""
FILE_PATH=""

# ===== 解析命令行参数 =====
while [[ $# -gt 0 ]]; do
    case $1 in
        -ts|--targetserver)
            TARGET_SERVER="$2"
            shift 2
            ;;
        -ta|--targetavatarid)
            TARGET_AVATARID="$2"
            shift 2
            ;;
        -fp|--filepath)
            FILE_PATH="$2"
            shift 2
            ;;
        -h|--help)
            echo "用法: $0 [-ts SERVER] [-ta AVATARID] [-fp FILEPATH]"
            echo ""
            echo "参数说明:"
            echo "  -ts, --targetserver    目标服务器名称（必须）"
            echo "  -ta, --targetavatarid  目标玩家ID，多个用逗号分隔（必须）"
            echo "  -fp, --filepath        导出文件位置（可选）"
            echo ""
            echo "示例："
            echo "  $0 -ts c7_personal_17220205 -ta aVnOtJ9QYZdALIx7 -fp /app/Implement/pickImpl/data/data_jydtest.json"
            exit 0 
            ;;
        *)
            echo "未知参数: $1"
            echo "使用 -h 或 --help 查看帮助"
            exit 1
            ;;
    esac
done

# ===== 验证必要参数 =====
if [[ -z "$TARGET_SERVER" ]]; then
    echo "错误: 必须指定目标服务器 (-ts)"
    exit 1
fi

if [[ -z "$TARGET_AVATARID" ]]; then
    echo "错误: 必须指定目标玩家ID (-ta)"
    exit 1
fi

# ===== 获取脚本目录 =====
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/script/dumpData.py"

# ===== 设置默认导出路径 =====
if [[ -z "$FILE_PATH" ]]; then
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    FILE_PATH="${SCRIPT_DIR}/data/data_${TIMESTAMP}.json"
    
    # 创建导出目录
    mkdir -p "$(dirname "$FILE_PATH")"
fi

# ===== 验证Python脚本存在 =====
if [[ ! -f "$PYTHON_SCRIPT" ]]; then
    echo "错误: 找不到Python脚本 $PYTHON_SCRIPT"
    exit 1
fi

# ===== 打印配置信息 =====
echo "============================================"
echo "导出玩家数据配置"
echo "============================================"
echo "目标服务器:  $TARGET_SERVER"
echo "目标玩家ID:  $TARGET_AVATARID"
echo "导出路径:    $FILE_PATH"
echo "============================================"
echo ""

# ===== 执行Python脚本 =====
echo "开始导出..."
python3 "$PYTHON_SCRIPT" \
    --targetserver "$TARGET_SERVER" \
    --targetavatarid "$TARGET_AVATARID" \
    --filepath "$FILE_PATH"

PYTHON_EXIT_CODE=$?

if [[ $PYTHON_EXIT_CODE -eq 0 ]]; then
    echo ""
    echo "✓ 导出成功！"
    echo "数据已保存至: $FILE_PATH"
    exit 0
else
    echo ""
    echo "✗ 导出失败，请查看上述错误信息"
    exit $PYTHON_EXIT_CODE
fi
