import json
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor


class TableExecutor(BaseNodeExecutor):
    type = "table"

    def execute(self, config: dict, input_data: dict) -> dict:
        """
        Table 渲染节点：接收上游数据并解析为结构化表格。

        支持输入格式:
          1. JSON 数组 → 单表  [item1, item2, ...]
          2. JSON 对象 → 多表  { "groupA": [...], "groupB": {...}, ... }
          3. JSON 对象数组 → 单表（每个 key 是列）
          4. 纯字符串（非 JSON）→ 按行切分，单列表格

        输出:
          tables: [
            { title: str | None, columns: [str], rows: [[str]] },
            ...
          ]
          tableStr: str  (供下游连线使用的纯文本摘要)
        """
        # --- 获取输入内容 ---
        raw = (
            input_data.get("tableInput")
            or input_data.get("fileContent")
            or input_data.get("jsonStr")
            or input_data.get("value")
            or ""
        )

        # 如果上游直接传了 python 对象（已经解析过）
        if isinstance(raw, (dict, list)):
            data = raw
        else:
            raw_str = str(raw).strip()
            if not raw_str:
                return {"error": "No input data. Connect an upstream node."}
            try:
                data = json.loads(raw_str)
            except json.JSONDecodeError:
                # 非 JSON → 按行拆分做单列表
                lines = [l for l in raw_str.splitlines() if l.strip()]
                tables = [{"title": None, "columns": ["内容"], "rows": [[l] for l in lines]}]
                return {"success": True, "tables": tables, "tableStr": self._to_text(tables)}

        tables = self._parse_data(data)
        return {"success": True, "tables": tables, "tableStr": self._to_text(tables)}

    # ------------------------------------------------------------------
    def _parse_data(self, data) -> list:
        """将 Python 对象转换为 tables 列表。"""
        if isinstance(data, list):
            return [self._list_to_table(data, title=None)]
        elif isinstance(data, dict):
            # 判断 dict 的 value 是否全部是基础类型
            all_scalar = all(
                not isinstance(v, (dict, list)) for v in data.values()
            )
            if all_scalar:
                # 全部是基础类型 → 整体作为一个 K-V 表
                return [self._dict_to_table(data, title=None)]
            else:
                # 有复杂类型的 value → 每个 key 单独成表
                tables = []
                for key, val in data.items():
                    if isinstance(val, list):
                        tables.append(self._list_to_table(val, title=str(key)))
                    elif isinstance(val, dict):
                        tables.append(self._dict_to_table(val, title=str(key)))
                    else:
                        # 标量值 → 单行单列
                        tables.append({
                            "title": str(key),
                            "columns": ["值"],
                            "rows": [[str(val)]],
                        })
                return tables
        else:
            # 标量
            return [{"title": None, "columns": ["值"], "rows": [[str(data)]]}]

    def _list_to_table(self, lst: list, title) -> dict:
        """将列表转换为表格。"""
        if not lst:
            return {"title": title, "columns": ["(空)"], "rows": []}

        # 列表元素是 dict → 把所有 key 合并为列
        if any(isinstance(item, dict) for item in lst):
            all_keys = []
            seen = set()
            for item in lst:
                if isinstance(item, dict):
                    for k in item.keys():
                        if k not in seen:
                            all_keys.append(str(k))
                            seen.add(str(k))
            columns = all_keys if all_keys else ["值"]
            rows = []
            for item in lst:
                if isinstance(item, dict):
                    rows.append([str(item.get(k, "")) for k in all_keys])
                else:
                    rows.append([str(item)] + [""] * (len(columns) - 1))
            return {"title": title, "columns": columns, "rows": rows}

        # 普通列表 → 单列 "序号" + "值"
        return {
            "title": title,
            "columns": ["#", "值"],
            "rows": [[str(i + 1), str(item)] for i, item in enumerate(lst)],
        }

    def _dict_to_table(self, d: dict, title) -> dict:
        """将字典转换为 Key/Value 两列表格。"""
        return {
            "title": title,
            "columns": ["Key", "Value"],
            "rows": [[str(k), str(v)] for k, v in d.items()],
        }

    def _to_text(self, tables: list) -> str:
        """将 tables 转换为纯文本（供下游节点使用）。"""
        lines = []
        for t in tables:
            if t.get("title"):
                lines.append(f"=== {t['title']} ===")
            header = " | ".join(t.get("columns", []))
            lines.append(header)
            lines.append("-" * max(len(header), 10))
            for row in t.get("rows", []):
                lines.append(" | ".join(row))
            lines.append("")
        return "\n".join(lines).strip()
