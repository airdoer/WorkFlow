"""
Unit tests for Collection executors: Map, Filter, Reduce, Sort, Join,
Lookup, Split, Distinct, Flatten, GroupBy.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from Implement.workflowImpl.mapExecutor import MapExecutor
from Implement.workflowImpl.filterExecutor import FilterExecutor
from Implement.workflowImpl.reduceExecutor import ReduceExecutor
from Implement.workflowImpl.sortExecutor import SortExecutor
from Implement.workflowImpl.joinExecutor import JoinExecutor
from Implement.workflowImpl.lookupExecutor import LookupExecutor
from Implement.workflowImpl.splitExecutor import SplitExecutor
from Implement.workflowImpl.distinctExecutor import DistinctExecutor
from Implement.workflowImpl.flattenExecutor import FlattenExecutor
from Implement.workflowImpl.groupbyExecutor import GroupByExecutor


class TestMapExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = MapExecutor()

    def test_map_multiply(self):
        result = self.executor.execute(
            config={"expression": "item * 2"},
            input_data={"list": [1, 2, 3]}
        )
        self.assertEqual(result["value"], [2, 4, 6])
        self.assertEqual(result["__runtime_type__"], "list")

    def test_map_extract_field(self):
        result = self.executor.execute(
            config={"expression": "item['name']"},
            input_data={"list": [{"name": "a"}, {"name": "b"}]}
        )
        self.assertEqual(result["value"], ["a", "b"])

    def test_map_with_index(self):
        result = self.executor.execute(
            config={"expression": "item * index"},
            input_data={"list": [10, 20, 30]}
        )
        self.assertEqual(result["value"], [0, 20, 60])

    def test_map_empty_list(self):
        result = self.executor.execute(
            config={"expression": "item * 2"},
            input_data={"list": []}
        )
        self.assertEqual(result["value"], [])

    def test_map_no_expression(self):
        result = self.executor.execute(
            config={},
            input_data={"list": [1, 2]}
        )
        self.assertIn("error", result)


class TestFilterExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = FilterExecutor()

    def test_filter_greater_than(self):
        result = self.executor.execute(
            config={"expression": "item > 2"},
            input_data={"list": [1, 2, 3, 4]}
        )
        self.assertEqual(result["value"], [3, 4])

    def test_filter_empty_result(self):
        result = self.executor.execute(
            config={"expression": "item > 100"},
            input_data={"list": [1, 2, 3]}
        )
        self.assertEqual(result["value"], [])

    def test_filter_all_match(self):
        result = self.executor.execute(
            config={"expression": "item > 0"},
            input_data={"list": [1, 2, 3]}
        )
        self.assertEqual(result["value"], [1, 2, 3])


class TestReduceExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = ReduceExecutor()

    def test_reduce_sum(self):
        result = self.executor.execute(
            config={"expression": "acc + item", "initialValue": "0"},
            input_data={"list": [1, 2, 3]}
        )
        self.assertEqual(result["value"], 6)

    def test_reduce_with_initial(self):
        result = self.executor.execute(
            config={"expression": "acc + item", "initialValue": "10"},
            input_data={"list": [1, 2, 3]}
        )
        self.assertEqual(result["value"], 16)

    def test_reduce_concat(self):
        result = self.executor.execute(
            config={"expression": "acc + item", "initialValue": "''"},
            input_data={"list": ["a", "b", "c"]}
        )
        self.assertEqual(result["value"], "abc")


class TestSortExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = SortExecutor()

    def test_sort_asc(self):
        result = self.executor.execute(
            config={"order": "asc"},
            input_data={"list": [3, 1, 2]}
        )
        self.assertEqual(result["value"], [1, 2, 3])

    def test_sort_desc(self):
        result = self.executor.execute(
            config={"order": "desc"},
            input_data={"list": [1, 3, 2]}
        )
        self.assertEqual(result["value"], [3, 2, 1])

    def test_sort_by_key(self):
        result = self.executor.execute(
            config={"key": "age", "order": "asc"},
            input_data={"list": [{"name": "c", "age": 30}, {"name": "a", "age": 10}, {"name": "b", "age": 20}]}
        )
        self.assertEqual(result["value"][0]["name"], "a")
        self.assertEqual(result["value"][1]["name"], "b")
        self.assertEqual(result["value"][2]["name"], "c")


class TestJoinExecutor(unittest.TestCase):
    """Core tests for Join node — the user's key requirement."""

    def setUp(self):
        self.executor = JoinExecutor()

    def test_join_combine_by_key_inner(self):
        """{1:100} + {1:"宝刀"} → {1:[100,"宝刀"]}"""
        result = self.executor.execute(
            config={"mode": "combine_by_key", "joinType": "inner"},
            input_data={"source1": {1: 100, 2: 200}, "source2": {1: "宝刀", 2: "长剑"}}
        )
        self.assertEqual(result["value"], {1: [100, "宝刀"], 2: [200, "长剑"]})
        self.assertEqual(result["__runtime_type__"], "object")
        self.assertEqual(result["mode"], "combine_by_key")

    def test_join_combine_by_key_outer(self):
        result = self.executor.execute(
            config={"mode": "combine_by_key", "joinType": "outer"},
            input_data={"source1": {1: 100, 2: 200}, "source2": {1: "宝刀", 3: "匕首"}}
        )
        self.assertIn(1, result["value"])
        self.assertIn(2, result["value"])
        self.assertIn(3, result["value"])
        self.assertEqual(result["value"][2], [200, None])
        self.assertEqual(result["value"][3], [None, "匕首"])

    def test_join_combine_by_key_left(self):
        result = self.executor.execute(
            config={"mode": "combine_by_key", "joinType": "left"},
            input_data={"source1": {1: 100, 4: 400}, "source2": {1: "宝刀"}}
        )
        self.assertIn(1, result["value"])
        self.assertIn(4, result["value"])
        self.assertEqual(result["value"][4], [400, None])

    def test_join_combine_by_position(self):
        result = self.executor.execute(
            config={"mode": "combine_by_position"},
            input_data={"source1": [100, 200], "source2": ["宝刀", "长剑"]}
        )
        self.assertEqual(result["value"], [[100, "宝刀"], [200, "长剑"]])

    def test_join_append(self):
        result = self.executor.execute(
            config={"mode": "append"},
            input_data={"source1": [1, 2], "source2": [3, 4]}
        )
        self.assertEqual(result["value"], [1, 2, 3, 4])

    def test_join_zip(self):
        result = self.executor.execute(
            config={"mode": "zip"},
            input_data={"source1": [100, 200, 300], "source2": ["宝刀", "长剑"]}
        )
        self.assertEqual(result["value"], [[100, "宝刀"], [200, "长剑"], [300, None]])

    def test_join_unknown_mode(self):
        result = self.executor.execute(
            config={"mode": "unknown"},
            input_data={"source1": [1], "source2": [2]}
        )
        self.assertIn("error", result)

    def test_join_combine_by_field_inner(self):
        """SQL JOIN: two lists of dicts on a shared field."""
        source1 = [
            {"装备ID": "1", "装备名": "宝刀"},
            {"装备ID": "2", "装备名": "护甲"},
        ]
        source2 = [
            {"装备ID": "1", "数量": 100},
            {"装备ID": "2", "数量": 50},
        ]
        result = self.executor.execute(
            config={"mode": "combine_by_field", "joinField": "装备ID", "joinType": "inner"},
            input_data={"source1": source1, "source2": source2}
        )
        self.assertEqual(result["__runtime_type__"], "list")
        self.assertEqual(result["count"], 2)
        # First merged row
        self.assertEqual(result["value"][0]["装备ID"], "1")
        self.assertEqual(result["value"][0]["装备名"], "宝刀")
        self.assertEqual(result["value"][0]["数量"], 100)
        # Second merged row
        self.assertEqual(result["value"][1]["装备ID"], "2")
        self.assertEqual(result["value"][1]["装备名"], "护甲")
        self.assertEqual(result["value"][1]["数量"], 50)

    def test_join_combine_by_field_left(self):
        """Left join: include all source1 rows, null for missing source2."""
        source1 = [
            {"装备ID": "1", "装备名": "宝刀"},
            {"装备ID": "3", "装备名": "灵药"},
        ]
        source2 = [
            {"装备ID": "1", "数量": 100},
        ]
        result = self.executor.execute(
            config={"mode": "combine_by_field", "joinField": "装备ID", "joinType": "left"},
            input_data={"source1": source1, "source2": source2}
        )
        self.assertEqual(result["count"], 2)
        # Matched row
        self.assertEqual(result["value"][0]["装备名"], "宝刀")
        self.assertEqual(result["value"][0]["数量"], 100)
        # Unmatched source1 row (null for source2 field)
        self.assertEqual(result["value"][1]["装备名"], "灵药")
        self.assertIsNone(result["value"][1]["数量"])

    def test_join_combine_by_field_duplicate_keys(self):
        """When both sources have same non-join field, prefix with s1_/s2_."""
        source1 = [{"id": "1", "value": 100}]
        source2 = [{"id": "1", "value": "宝刀"}]
        result = self.executor.execute(
            config={"mode": "combine_by_field", "joinField": "id", "joinType": "inner"},
            input_data={"source1": source1, "source2": source2}
        )
        row = result["value"][0]
        self.assertEqual(row["id"], "1")
        self.assertEqual(row["s1_value"], 100)
        self.assertEqual(row["s2_value"], "宝刀")

    def test_join_combine_by_field_no_field_error(self):
        """combine_by_field without joinField should return error."""
        result = self.executor.execute(
            config={"mode": "combine_by_field"},
            input_data={"source1": [{"id": "1"}], "source2": [{"id": "1"}]}
        )
        self.assertIn("error", result)

    def test_join_combine_by_field_dict_source2(self):
        """source2 is a plain dict → auto-convert to list-of-dicts."""
        source1 = [
            {"装备ID": "3010603", "装备名": "宝刀"},
            {"装备ID": "3010623", "装备名": "护甲"},
        ]
        source2 = {"3010603": 2, "3010623": 5}  # {装备ID: 数量}
        result = self.executor.execute(
            config={"mode": "combine_by_field", "joinField": "装备ID", "joinType": "inner"},
            input_data={"source1": source1, "source2": source2}
        )
        self.assertEqual(result["count"], 2)
        # First row: 装备ID=3010603 merged
        row0 = result["value"][0]
        self.assertEqual(row0["装备ID"], "3010603")
        self.assertEqual(row0["装备名"], "宝刀")
        self.assertEqual(row0["value"], 2)


class TestLookupExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = LookupExecutor()

    def test_lookup_found(self):
        result = self.executor.execute(
            config={"key": "name"},
            input_data={"source": {"name": "宝刀", "quality": 5}}
        )
        self.assertEqual(result["value"], "宝刀")
        self.assertTrue(result["found"])

    def test_lookup_not_found(self):
        result = self.executor.execute(
            config={"key": "missing"},
            input_data={"source": {"name": "宝刀"}}
        )
        self.assertFalse(result["found"])


class TestSplitExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = SplitExecutor()

    def test_split_by_chunk(self):
        result = self.executor.execute(
            config={"chunkSize": "2"},
            input_data={"list": [1, 2, 3, 4, 5]}
        )
        self.assertEqual(result["value"], [[1, 2], [3, 4], [5]])

    def test_split_by_field(self):
        result = self.executor.execute(
            config={"field": "items"},
            input_data={"list": [{"items": [1, 2]}, {"items": [3, 4]}]}
        )
        self.assertEqual(result["value"], [1, 2, 3, 4])


class TestDistinctExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = DistinctExecutor()

    def test_distinct_primitives(self):
        result = self.executor.execute(
            config={},
            input_data={"list": [1, 2, 2, 3, 3, 3]}
        )
        self.assertEqual(result["value"], [1, 2, 3])

    def test_distinct_strings(self):
        result = self.executor.execute(
            config={},
            input_data={"list": ["a", "b", "a", "c"]}
        )
        self.assertEqual(result["value"], ["a", "b", "c"])

    def test_distinct_by_key(self):
        result = self.executor.execute(
            config={"key": "id"},
            input_data={"list": [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}, {"id": 1, "v": "c"}]}
        )
        self.assertEqual(len(result["value"]), 2)


class TestFlattenExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = FlattenExecutor()

    def test_flatten_nested(self):
        result = self.executor.execute(
            config={},
            input_data={"list": [[1, 2], [3, [4, 5]]]}
        )
        self.assertEqual(result["value"], [1, 2, 3, 4, 5])

    def test_flatten_already_flat(self):
        result = self.executor.execute(
            config={},
            input_data={"list": [1, 2, 3]}
        )
        self.assertEqual(result["value"], [1, 2, 3])


class TestGroupByExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = GroupByExecutor()

    def test_groupby_category(self):
        result = self.executor.execute(
            config={"expression": "item['cat']"},
            input_data={"list": [
                {"cat": "A", "v": 1},
                {"cat": "B", "v": 2},
                {"cat": "A", "v": 3}
            ]}
        )
        self.assertIn("A", result["value"])
        self.assertIn("B", result["value"])
        self.assertEqual(len(result["value"]["A"]), 2)
        self.assertEqual(len(result["value"]["B"]), 1)
        self.assertEqual(result["groupCount"], 2)


if __name__ == '__main__':
    unittest.main()
