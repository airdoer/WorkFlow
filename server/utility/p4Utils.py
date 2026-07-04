import re
import os
import subprocess
from data.ClientSplitConfig import data as split_config
from typing import List, Dict

import logging
logger = logging.getLogger(__name__)

BATCH_SIZE = 100

def _run_p4(cmd: List[str]) -> str:
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False
    )
    return result.stdout.strip()


def _batch(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]

def parse_p4_path(p4_path: str):
    """
    从 p4 路径解析出：
    - depot 路径（含末尾斜杠）
    - 文件名（不带版本号）
    - 扩展名（含 .，若无则为空字符串）
    - 版本号（str，没有则为 None）
    支持：
      1) .../filename.lua#2
      2) .../filename#2.lua
      3) .../filename#2
      4) .../filename.lua
      5) .../filename
    """
    pattern = re.compile(
        r'^(?P<dir>.+/)'                         # 目录（至少有一个斜杠）
        r'(?P<name>[^/#]+?)'                     # 基础名（不含 / 和 #）
        r'(?:'                                   # 开始交替，覆盖两种顺序
        r'(?P<ext>\.[^/#]+)(?:#(?P<rev>\d+))?'   # A) 先扩展名，再可选 #rev
        r'|'                                     
        r'#(?P<rev2>\d+)(?P<ext2>\.[^/#]+)?'     # B) 先 #rev，再可选扩展名
        r')?$'                                   # 整段可选，以支持无扩展无版本
    )

    m = pattern.match(p4_path)
    if not m:
        return {}

    dir_path = m.group('dir')
    name = m.group('name')
    ext = m.group('ext') or m.group('ext2') or ""
    rev = m.group('rev') or m.group('rev2')

    return {
        "dir": dir_path,
        "name": name,
        "ext": ext,
        "rev": rev
    }


def normalize_p4_path(p4_path: str) -> str:
    """
    将路径转换成 Perforce 正规形式：filename.ext#rev
    """
    parts = parse_p4_path(p4_path)
    if parts["rev"]:
        return f"{parts['dir']}{parts['name']}{parts['ext']}#{parts['rev']}"
    else:
        return f"{parts['dir']}{parts['name']}{parts['ext']}"


def get_filename(p4_path: str) -> str:
    """
    获取文件名（含扩展名，不带版本号）
    """
    parts = parse_p4_path(p4_path)
    return f"{parts['name']}{parts['ext']}"


def get_table_data_name(p4_path: str) -> (str, bool):
    """
    获取表数据名称，支持分表功能
    如果是分表文件（如 SkillDataNew_split_1），则返回原始表名（如 SkillDataNew）
    """
    # //C7/Development/Mainline/Server/script_lua/Data/Excel/FStatePropData.lua#2 -> FStatePropData
    parts = parse_p4_path(p4_path)
    file_name = parts['name']
    
    # 检查是否为分表文件
    for table_name, split_count in split_config.items():
        # 检查文件名是否匹配分表模式：TableName_split_N
        split_pattern = f"{table_name}_split_"
        if file_name.startswith(split_pattern):
            # 提取分表编号
            suffix = file_name[len(split_pattern):]
            try:
                split_num = int(suffix)
                # 验证分表编号是否在有效范围内（1 到 split_count）
                if 1 <= split_num <= split_count:
                    return table_name, True
            except ValueError:
                # 如果后缀不是数字，继续检查其他可能的匹配
                continue
    
    # 如果不是分表文件，返回原始文件名
    return file_name, False

def get_space_data_name(p4_path: str) -> (str, str):
    # //C7/Development/Mainline/Client/Content/Script/Data/Config/SpaceData/LV_Tiengen_P/0202_LeaveUniversity.lua#10 -> LV_Tiengen_P 0202_LeaveUniversity
    parts = parse_p4_path(p4_path)
    dir = parts['dir']
    scene_name = dir.strip('/').split('/')[-1]
    group_name = parts['name']
    return scene_name, group_name


def p4_file_exists(p4FilePath: str) -> bool:
    p4Cmd = f"p4 files {p4FilePath}"
    p4Result = os.popen(p4Cmd).read().strip()

    error_keywords = [
        "no such file",
        "not under",
        "no file",
        "must refer",
        "not in client view",
    ]
    # p4 的输出是大小写不敏感的
    p4ResultLower = p4Result.lower()
    if any(err in p4ResultLower for err in error_keywords):
        return False
    
    # 如果匹配到 #<数字> 版本号，基本就是存在
    return bool(re.search(r"#\d+", p4Result))


def get_latest_revision(p4FilePath: str) -> str:
    """
    获取文件的最新版本号。
    例如：//.../file.txt -> //.../file.txt#5
    如果文件不存在或获取失败，返回空字符串。
    """
    # 移除可能存在的版本号后缀，确保查询的是最新状态
    base_path = p4FilePath.split('#')[0]
    
    # 使用 p4 files 命令获取文件信息
    p4Cmd = f"p4 files {base_path}"
    try:
        p4Result = os.popen(p4Cmd).read().strip()
        
        # 检查错误
        error_keywords = [
            "no such file",
            "not under",
            "no file",
            "must refer",
            "not in client view",
            "delete" # 如果文件被删除了，通常也会显示 delete
        ]
        p4ResultLower = p4Result.lower()
        if any(err in p4ResultLower for err in error_keywords):
            return ""

        # 解析输出中的版本号
        # 输出示例: //depot/path/file.txt#5 - edit change 12345 (text)
        match = re.search(r'(#\d+)', p4Result)
        if match:
            return f"{base_path}{match.group(1)}"
            
    except Exception as e:
        print(f"获取最新版本号出错: {e}")
        
    return ""

def get_latest_changelist(p4FilePath: str) -> int:
    base_path = p4FilePath.split("#")[0].split("@")[0]
    output = _run_p4(["p4", "filelog", "-m", "1", "-t", base_path])
    if not output:
        return 0

    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("... #"):
            continue
        if " delete on " in line:
            return 0
        m = re.search(r' change (\d+)(?: |$)', line)
        if m:
            return int(m.group(1))
        return 0

    return 0

def get_changelist_description(changelist: int) -> str:
    """通过 p4 describe 获取指定 CL 的描述文本（仅描述部分）。"""
    if not changelist or int(changelist) <= 0:
        return ""
    try:
        output = _run_p4(["p4", "describe", "-s", str(int(changelist))])
    except Exception as e:
        logger.warning(f"get_changelist_description({changelist}) failed: {e}")
        return ""
    if not output:
        return ""

    # p4 describe -s 输出格式（节选）：
    #   Change 12345 by user@workspace on 2025/01/01 12:00:00
    #
    #   <description, 每行前面有一个 \t>
    #
    #   Affected files ...
    desc_lines = []
    in_desc = False
    for line in output.splitlines():
        if line.startswith("Change "):
            in_desc = True
            continue
        if line.startswith("Affected files"):
            break
        if not in_desc:
            continue
        if line.startswith("\t"):
            desc_lines.append(line[1:])
        elif line.strip() == "":
            desc_lines.append("")
    return "\n".join(desc_lines).strip()


def get_file_history(p4FilePath: str, max_count: int = 50) -> List[Dict]:
    """获取P4文件的提交历史
    
    Args:
        p4FilePath: P4文件路径
        max_count: 最多返回的历史记录数量
    
    Returns:
        历史记录列表，每项包含: changelist, revision, time, user, description
    """
    base_path = p4FilePath.split("#")[0].split("@")[0]
    output = _run_p4(["p4", "filelog", "-m", str(max_count), "-l", "-t", base_path])
    if not output:
        return []
    
    history = []
    current_record = None
    description_lines = []
    
    for line in output.splitlines():
        # 匹配版本行: ... #1 change 12345 edit on 2025/01/01 by user@workspace (text)
        if line.startswith("... #"):
            # 保存上一条记录
            if current_record:
                current_record['description'] = '\n'.join(description_lines).strip()
                history.append(current_record)
                description_lines = []
            
            # 解析新记录
            # 示例: ... #5 change 12345 edit on 2025/01/01 12:00:00 by user@workspace (text)
            match = re.search(r'#(\d+)\s+change\s+(\d+)\s+\w+\s+on\s+([\d/]+\s+[\d:]+)\s+by\s+([\w@.]+)', line)
            if match:
                revision = match.group(1)
                changelist = int(match.group(2))
                time_str = match.group(3)
                user = match.group(4).split('@')[0]  # 只取用户名部分
                
                current_record = {
                    'revision': int(revision),
                    'changelist': changelist,
                    'time': time_str,
                    'user': user,
                    'description': ''
                }
        # 描述行（以\t开头）
        elif line.startswith('\t') and current_record:
            description_lines.append(line[1:])  # 去掉开头的\t
    
    # 保存最后一条记录
    if current_record:
        current_record['description'] = '\n'.join(description_lines).strip()
        history.append(current_record)
    
    return history


def list_dir(p4FileDir: str, changelist: int = 0) -> List[Dict]:
    # 兼容调用方传入带尾部斜杠的路径，避免出现 //...//* 双斜杠导致 p4 返回空
    p4FileDir = (p4FileDir or "").rstrip("/")
    if not p4FileDir:
        logger.info("p4 list_dir: empty p4FileDir")
        return []

    suffix = f"@{changelist}" if changelist > 0 else ""

    # 1. 精确获取文件列表
    p4_pattern = f"{p4FileDir}/*{suffix}"
    logger.info(f"p4 list_dir: p4 files -e {p4_pattern}")
    files_output = _run_p4(["p4", "files", "-e", p4_pattern])
    if not files_output:
        logger.info(f"p4 list_dir: empty output from p4 files for {p4_pattern}")
        return []

    files = []
    for line in files_output.splitlines():
        depot_file = line.split("#", 1)[0].strip()
        if depot_file:
            files.append(depot_file)

    if not files:
        logger.info(f"p4 list_dir 没有获取到文件列表: {p4FileDir}")
        return []

    # p4 files -e 已经过滤了已删除文件，直接用 files 结果做 filelog
    # 2. filelog 获取 author/changelist/time
    file_infos = []

    for batch in _batch(files, BATCH_SIZE):
        cmd = ["p4", "filelog", "-m", "1", "-t"] + batch
        output = _run_p4(cmd)
        if not output:
            continue

        current_file = None
        current_name = None

        for line in output.splitlines():
            if line.startswith("//"):
                current_file = line.strip()
                current_name = current_file.split("/")[-1]

            elif line.startswith("... #"):
                if not current_file:
                    continue
                if " delete on " in line:
                    continue

                time_match = re.search(
                    r'on (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})', line
                )
                author_match = re.search(r' by (.*?)@', line)
                change_match = re.search(r' change (\d+) ', line)

                file_infos.append({
                    "name": current_name,
                    "time": time_match.group(1) if time_match else "",
                    "author": author_match.group(1) if author_match else "",
                    "changelist": int(change_match.group(1)) if change_match else 0
                })

    return file_infos

def update_file(p4FilePath: str, targetPath: str, force: bool = False, version: int = 0, changelist: int = 0) -> bool:
    """
    更新 Perforce 中的文件到本地指定路径。
    如果文件不存在，会返回 False。
    p4FilePath是没有版本信息的，//C7/Development/Mainline/Server/script_lua/Data/Flowchart/FileNameToFlowchartName.txt
    如果version为0，则获取最新版本号；否则使用指定版本。
    实现逻辑与 download_file 一致，使用 p4 print 直接覆盖写入。
    如果本地文件已经存在，则直接返回 True，不再下载。
    """
    # 0. 检查本地文件是否已存在
    if not force and os.path.exists(targetPath):
        return True

    # 1. 获取带版本号的路径
    base_path = p4FilePath.split('#')[0]
    
    if version > 0:
        p4_path_with_rev = f"{base_path}#{version}"
    elif changelist > 0:
        p4_path_with_rev = f"{base_path}@{changelist}"
    else:
        p4_path_with_rev = get_latest_revision(p4FilePath)
        if not p4_path_with_rev:
            # 如果获取不到最新版本（可能文件不存在），则直接返回 False
            return False
    
    # 2. 使用带版本号的路径进行下载
    return download_file(p4_path_with_rev, targetPath)
    


def download_file(p4FilePath: str, targetPath: str) -> bool:
    """
    从 Perforce 直接下载文件到 targetPath，不依赖本地 client root。
    如果 targetPath 的目录不存在，会递归创建。
    """
    # 确保目标目录存在
    os.makedirs(os.path.dirname(targetPath), exist_ok=True)

    # p4 print -q 会静默输出文件内容（不加文件头信息）
    p4Cmd = ["p4", "print", "-q", p4FilePath]

    try:
        with open(targetPath, "wb") as f:
            result = subprocess.run(p4Cmd, stdout=f, stderr=subprocess.PIPE, check=False)

        # 判断是否报错
        if result.returncode != 0:
            errMsg = result.stderr.decode("utf-8", errors="ignore").lower()
            error_keywords = [
                "no such file",
                "no file",
                "not under",
                "must refer",
                "not in client view",
                "file(s) not on client",
            ]
            if any(err in errMsg for err in error_keywords):
                return False
            # 如果 returncode != 0 但 stderr 没有这些关键字，可能是其他原因
            return False
        return True

    except Exception as e:
        print(f"下载文件出错: {e}")
        return False

def update_dir(p4DirPath: str, localBaseDir: str, force: bool = True) -> int:
    p4_dir = p4DirPath.rstrip("/")
    output = _run_p4(["p4", "files", "-e", f"{p4_dir}/..."])
    if not output:
        return 0

    updated = 0
    for line in output.splitlines():
        s = (line or "").strip()
        if not s.startswith("//"):
            continue
        if " delete " in s.lower():
            continue
        depot_file = s.split("#", 1)[0].strip()
        if not depot_file:
            continue
        target_path = os.path.join(localBaseDir, depot_file.replace("//", ""))
        if not force and os.path.exists(target_path):
            continue
        ok = download_file(depot_file, target_path)
        if ok:
            updated += 1

    return updated

# ==== 示例 ====
if __name__ == "__main__":
    p1 = "//C7/Development/Mainline/Server/script_lua/Data/Excel/FStatePropData.lua#2"
    p2 = "//C7/Development/Mainline/Server/script_lua/Data/Excel/FStatePropData#2.lua"
    p3 = "//C7/Development/Mainline/Server/script_lua/Data/Excel/SkillDataNew_split_1.lua#2"
    p4 = "//C7/Development/Mainline/Server/script_lua/Data/Excel/SkillDataNew_split_4.lua#2"

    print("解析路径:")
    print(parse_p4_path(p1))
    print(parse_p4_path(p2))

    print("\n标准化路径:")
    print(normalize_p4_path(p1))  # //.../FStatePropData.lua#2
    print(normalize_p4_path(p2))  # //.../FStatePropData.lua#2

    print("\n获取文件名:")
    print(get_filename(p1))  # FStatePropData.lua
    print(get_filename(p2))  # FStatePropData.lua

    print("\n获取表数据名称（支持分表）:")
    print(f"{p1} -> {get_table_data_name(p1)}")  # FStatePropData
    print(f"{p3} -> {get_table_data_name(p3)}")  # SkillDataNew
    print(f"{p4} -> {get_table_data_name(p4)}")  # SkillDataNew
