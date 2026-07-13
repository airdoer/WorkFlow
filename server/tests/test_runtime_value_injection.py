"""
Test that old executors automatically get Runtime Value markers injected.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from Implement.workflowImpl.nodeExecutor import ExecutorManager
from Implement.workflowImpl.stringExecutor import StringExecutor
from Implement.workflowImpl.boolExecutor import BoolExecutor
from Implement.workflowImpl.numberExecutor import NumberExecutor
from Implement.workflowImpl.boolGateExecutor import BoolGateExecutor


class TestRuntimeValueInjection(unittest.TestCase):
    """Test that ExecutorManager._inject_runtime_type works for old executors."""

    def test_string_executor_gets_runtime_type(self):
        result = ExecutorManager.run_node("string", {"value": "hello"}, {})
        self.assertIn("__runtime_type__", result)
        self.assertEqual(result["__runtime_type__"], "string")
        self.assertIn("__value__", result)
        self.assertEqual(result["__value__"], "hello")

    def test_bool_executor_gets_runtime_type(self):
        result = ExecutorManager.run_node("bool", {"value": True}, {})
        self.assertIn("__runtime_type__", result)
        self.assertEqual(result["__runtime_type__"], "boolean")

    def test_number_executor_gets_runtime_type(self):
        result = ExecutorManager.run_node("number", {"value": 42}, {})
        self.assertIn("__runtime_type__", result)
        self.assertEqual(result["__runtime_type__"], "number")

    def test_boolgate_executor_gets_runtime_type(self):
        result = ExecutorManager.run_node("boolgate", {}, {"valueIn": True})
        self.assertIn("__runtime_type__", result)
        self.assertEqual(result["__runtime_type__"], "boolean")

    def test_error_result_no_injection(self):
        """Error results should not get runtime type injection."""
        result = {"error": "Something went wrong"}
        injected = ExecutorManager._inject_runtime_type(result, "unknown")
        self.assertNotIn("__runtime_type__", injected)

    def test_new_executor_keeps_own_type(self):
        """New executors that already set __runtime_type__ should keep it."""
        result = {"value": [1, 2, 3], "__runtime_type__": "list", "__value__": [1, 2, 3]}
        injected = ExecutorManager._inject_runtime_type(result, "map")
        self.assertEqual(injected["__runtime_type__"], "list")

    def test_map_executor_type_via_run_node(self):
        """Map executor called via run_node should have __runtime_type__."""
        from Implement.workflowImpl.mapExecutor import MapExecutor
        ExecutorManager.register(MapExecutor())
        result = ExecutorManager.run_node("map", {"expression": "item * 2"}, {"list": [1, 2, 3]})
        self.assertEqual(result["__runtime_type__"], "list")
        self.assertEqual(result["__value__"], [2, 4, 6])


if __name__ == '__main__':
    unittest.main()
