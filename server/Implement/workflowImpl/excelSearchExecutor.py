import json
import os
import openpyxl
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


_EXCEL_FILES_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'Excel', 'excelFiles.json')


def _load_excel_files() -> dict:
    """读取 excelFiles.json，返回原始 dict。"""
    try:
        with open(_EXCEL_FILES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # 过滤掉 _comment 等非条目字段
        return {k: v for k, v in data.items() if not k.startswith('_') and isinstance(v, dict)}
    except Exception:
        return {}


def load_excelsearch_options() -> list:
    """
    转换 excelFiles.json → 下拉选项列表，供前端 /api/workflow/excelsearch/list 使用。
    """
    files = _load_excel_files()
    options = []
    for key, info in files.items():
        options.append({
            'label': info.get('name', key),
            'value': key,
            'localPath': info.get('local_path', ''),
            'p4Path': info.get('p4_path', ''),
            'description': info.get('description', ''),
        })
    return options


class ExcelSearchExecutor(BaseNodeExecutor):
    type = "excelsearch"

    def execute(self, config: dict, input_data: dict) -> dict:
        """
        ExcelSearch 节点：根据选中的 fileKey 定位 Excel 文件，输出文件内容及元信息。

        优先使用 local_path（文件存在时）；
        若 local_path 不存在或为空，尝试通过 p4_path 同步（p4Utils.update_file）。

        输出：
          fileContent : str          文件二进制内容（latin-1 编码的字符串，供 Excel 节点用 openpyxl 打开）
          localPath   : str          文件本地绝对路径
          fileName    : str          文件名（不含路径）
          sheetNames  : list[str]    工作表名称列表
        """
        file_key = config.get('fileKey', '').strip()
        if not file_key:
            return {'error': 'fileKey 不能为空，请在节点中选择一个 Excel 文件。'}

        files = _load_excel_files()
        entry = files.get(file_key)
        if entry is None:
            return {'error': f"未找到 fileKey='{file_key}' 的 Excel 文件配置，请检查 excelFiles.json。"}

        local_path = entry.get('local_path', '').strip()
        p4_path = entry.get('p4_path', '').strip()

        # --- 1. 优先使用本地路径 ---
        resolved_path = ''
        if local_path and os.path.exists(local_path):
            resolved_path = local_path
        elif p4_path:
            # --- 2. 尝试从 P4 同步 ---
            try:
                from tools.p4Utils import update_file  # type: ignore
                result = update_file(p4_path)
                if result and os.path.exists(result):
                    resolved_path = result
                else:
                    return {'error': f"P4 同步失败或文件不存在：{p4_path}"}
            except ImportError:
                return {'error': f"p4Utils 模块未找到，无法同步 P4 路径：{p4_path}"}
            except Exception as e:
                return {'error': f"P4 同步出错：{e}"}
        else:
            return {'error': f"文件 '{file_key}' 既无可用的 local_path，也无 p4_path，请更新 excelFiles.json。"}

        # --- 3. 读取文件 + 获取 sheetNames ---
        try:
            wb = openpyxl.load_workbook(resolved_path, data_only=True, read_only=True)
            sheet_names = wb.sheetnames
            wb.close()

            with open(resolved_path, 'rb') as f:
                raw_bytes = f.read()
            # 用 latin-1 编码，保证字节透明传输（excelExecutor 用 latin-1 解码还原）
            file_content = raw_bytes.decode('latin-1')

            return {
                'fileContent': file_content,
                'localPath': resolved_path,
                'fileName': os.path.basename(resolved_path),
                'sheetNames': sheet_names,
            }
        except Exception as e:
            return {'error': f"读取文件失败：{e}"}
