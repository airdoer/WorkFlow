import logging
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)


class JoinExecutor(BaseNodeExecutor):
    """
    Join node: merge data from multiple sources.

    Modes:
    - combine_by_key: merge dicts by key → {key: [val1, val2]}
    - combine_by_field: SQL-like JOIN on a shared field in two lists of dicts
    - combine_by_position: merge lists by index → [[item1_a, item1_b], ...]
    - append: concatenate lists → [a1, a2, b1, b2]
    - zip: pair items by index → [[a1, b1], [a2, b2]]

    Join types (combine_by_key and combine_by_field):
    - inner: only keys present in both sources
    - outer: all keys from both sources (null for missing)
    - left: all keys from source1 (null for missing in source2)
    - right: all keys from source2 (null for missing in source1)
    """

    type = "join"

    def execute(self, config: dict, input_data: dict) -> dict:
        mode = config.get("mode", "combine_by_key")
        join_type = config.get("joinType", "inner")
        join_field = config.get("joinField", "")

        source1 = input_data.get("source1", input_data.get("list", []))
        source2 = input_data.get("source2", [])

        if not source1 and not source2:
            return {"error": "Both sources are empty. Connect upstream nodes to source1 and source2."}

        if mode == "combine_by_key":
            return self._combine_by_key(source1, source2, join_type)
        elif mode == "combine_by_field":
            if not join_field:
                return {"error": "combine_by_field mode requires a 'joinField' (the shared field name to join on)."}
            return self._combine_by_field(source1, source2, join_field, join_type)
        elif mode == "combine_by_position":
            return self._combine_by_position(source1, source2)
        elif mode == "append":
            return self._append(source1, source2)
        elif mode == "zip":
            return self._zip(source1, source2)
        else:
            return {"error": f"Unknown join mode: {mode}"}

    def _combine_by_key(self, source1, source2, join_type: str) -> dict:
        """
        Combine two dicts by key.
        {1: 100, 2: 200} + {1: "宝刀", 2: "长剑"} → {1: [100, "宝刀"], 2: [200, "长剑"]}
        """
        # Convert lists of key-value pairs to dicts if needed
        dict1 = self._to_dict(source1)
        dict2 = self._to_dict(source2)

        keys1 = set(dict1.keys())
        keys2 = set(dict2.keys())

        if join_type == "inner":
            keys = keys1 & keys2
        elif join_type == "outer":
            keys = keys1 | keys2
        elif join_type == "left":
            keys = keys1
        elif join_type == "right":
            keys = keys2
        else:
            keys = keys1 & keys2  # default to inner

        result = {}
        for key in keys:
            v1 = dict1.get(key, None)
            v2 = dict2.get(key, None)
            result[key] = [v1, v2]

        return {
            "__runtime_type__": "object",
            "__value__": result,
            "value": result,
            "result": result,
            "count": len(result),
            "mode": "combine_by_key",
            "joinType": join_type,
        }

    def _combine_by_field(self, source1, source2, join_field: str, join_type: str) -> dict:
        """
        SQL-like JOIN: merge two lists of dicts on a shared field.

        Example:
          source1 = [{"装备ID": "1", "装备名": "宝刀"}, {"装备ID": "2", "装备名": "护甲"}]
          source2 = [{"装备ID": "1", "数量": 100}, {"装备ID": "2", "数量": 50}]
          join_field = "装备ID", join_type = "inner"
          → [{"装备ID": "1", "装备名": "宝刀", "数量": 100},
             {"装备ID": "2", "装备名": "护甲", "数量": 50}]

        Also supports source2 being a plain dict (auto-converts to list-of-dicts):
          source2 = {"3010603": 2, "3010623": 5}  with join_field="装备ID"
          → auto-converts to [{"装备ID": "3010603", "value": 2}, {"装备ID": "3010623", "value": 5}]
        """
        list1 = self._to_list(source1)
        list2 = self._to_list(source2)

        # Auto-convert: if source2 is a dict (not list-of-dicts), convert to list-of-dicts
        # where each {key: val} becomes [{join_field: key, "value": val}, ...]
        if isinstance(source2, dict) and list2 and not isinstance(list2[0], dict):
            list2 = [{join_field: str(k), "value": v} for k, v in source2.items()]
        # Also check source1
        if isinstance(source1, dict) and list1 and not isinstance(list1[0], dict):
            list1 = [{join_field: str(k), "value": v} for k, v in source1.items()]

        # Build lookup index for source2
        index2: dict[str, list[dict]] = {}
        for item in list2:
            if isinstance(item, dict):
                key_val = str(item.get(join_field, ""))
                if key_val not in index2:
                    index2[key_val] = []
                index2[key_val].append(item)

        # Also build index for source1 (needed for outer/right joins)
        index1: dict[str, list[dict]] = {}
        for item in list1:
            if isinstance(item, dict):
                key_val = str(item.get(join_field, ""))
                if key_val not in index1:
                    index1[key_val] = []
                index1[key_val].append(item)

        result = []
        matched_keys_s2 = set()

        # Process source1 items
        for item1 in list1:
            if not isinstance(item1, dict):
                continue
            key_val = str(item1.get(join_field, ""))
            matches = index2.get(key_val, [])

            if matches:
                matched_keys_s2.add(key_val)
                for item2 in matches:
                    merged = self._merge_dicts(item1, item2, join_field)
                    result.append(merged)
            elif join_type in ("left", "outer"):
                # No match in source2 — include with null values for s2 fields
                merged = dict(item1)
                # Add null placeholders for source2 fields (sample first item)
                if list2 and isinstance(list2[0], dict):
                    for k, v in list2[0].items():
                        if k != join_field and k not in merged:
                            merged[k] = None
                result.append(merged)

        # For outer/right joins, include unmatched source2 items
        if join_type in ("right", "outer"):
            for item2 in list2:
                if not isinstance(item2, dict):
                    continue
                key_val = str(item2.get(join_field, ""))
                if key_val not in matched_keys_s2:
                    merged = dict(item2)
                    # Add null placeholders for source1 fields
                    if list1 and isinstance(list1[0], dict):
                        for k, v in list1[0].items():
                            if k != join_field and k not in merged:
                                merged[k] = None
                    result.append(merged)

        return {
            "__runtime_type__": "list",
            "__value__": result,
            "value": result,
            "result": result,
            "rows": result,  # alias for Table compatibility
            "count": len(result),
            "mode": "combine_by_field",
            "joinField": join_field,
            "joinType": join_type,
        }

    @staticmethod
    def _merge_dicts(item1: dict, item2: dict, join_field: str) -> dict:
        """Merge two dicts, handling duplicate keys by prefixing with s1_/s2_."""
        merged = {join_field: item1.get(join_field)}
        for k, v in item1.items():
            if k == join_field:
                continue
            if k in item2 and k != join_field:
                merged[f"s1_{k}"] = v
            else:
                merged[k] = v
        for k, v in item2.items():
            if k == join_field:
                continue
            if k in item1 and k != join_field:
                merged[f"s2_{k}"] = v
            else:
                merged[k] = v
        return merged

    def _combine_by_position(self, source1, source2) -> dict:
        """
        Combine two lists by position.
        [100, 200] + ["宝刀", "长剑"] → [[100, "宝刀"], [200, "长剑"]]
        """
        list1 = self._to_list(source1)
        list2 = self._to_list(source2)

        max_len = max(len(list1), len(list2))
        result = []
        for i in range(max_len):
            v1 = list1[i] if i < len(list1) else None
            v2 = list2[i] if i < len(list2) else None
            result.append([v1, v2])

        return {
            "__runtime_type__": "list",
            "__value__": result,
            "value": result,
            "result": result,
            "count": len(result),
            "mode": "combine_by_position",
        }

    def _append(self, source1, source2) -> dict:
        """
        Append two lists.
        [1, 2] + [3, 4] → [1, 2, 3, 4]
        """
        list1 = self._to_list(source1)
        list2 = self._to_list(source2)

        result = list1 + list2

        return {
            "__runtime_type__": "list",
            "__value__": result,
            "value": result,
            "result": result,
            "count": len(result),
            "mode": "append",
        }

    def _zip(self, source1, source2) -> dict:
        """
        Zip two lists by index (like Python's zip_longest).
        [100, 200, 300] + ["宝刀", "长剑"] → [[100, "宝刀"], [200, "长剑"], [300, null]]
        """
        list1 = self._to_list(source1)
        list2 = self._to_list(source2)

        max_len = max(len(list1), len(list2))
        result = []
        for i in range(max_len):
            v1 = list1[i] if i < len(list1) else None
            v2 = list2[i] if i < len(list2) else None
            result.append([v1, v2])

        return {
            "__runtime_type__": "list",
            "__value__": result,
            "value": result,
            "result": result,
            "count": len(result),
            "mode": "zip",
        }

    @staticmethod
    def _to_list(data) -> list:
        """Convert data to list."""
        if isinstance(data, list):
            return list(data)
        if isinstance(data, dict):
            return list(data.values())
        if data is None:
            return []
        return [data]

    @staticmethod
    def _to_dict(data) -> dict:
        """Convert data to dict."""
        if isinstance(data, dict):
            return dict(data)
        if isinstance(data, list):
            # Try to convert list of [key, value] pairs
            result = {}
            for i, item in enumerate(data):
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    result[item[0]] = item[1]
                else:
                    result[str(i)] = item
            return result
        if data is None:
            return {}
        return {"0": data}
