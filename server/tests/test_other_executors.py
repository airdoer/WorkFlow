"""
Unit tests for Builder, Expression, Control Flow, and Expression Engine.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from Implement.workflowImpl.listBuilderExecutor import ListBuilderExecutor
from Implement.workflowImpl.objectBuilderExecutor import ObjectBuilderExecutor
from Implement.workflowImpl.dictBuilderExecutor import DictBuilderExecutor
from Implement.workflowImpl.calculateExecutor import CalculateExecutor
from Implement.workflowImpl.templateExecutor import TemplateExecutor
from Implement.workflowImpl.conditionExecutor import ConditionExecutor
from Implement.workflowImpl.ifExecutor import IfExecutor
from Implement.workflowImpl.loopExecutor import LoopExecutor
from Implement.workflowImpl.switchExecutor import SwitchExecutor
from Implement.workflowImpl.expressionEngine import SimpleExpressionEngine


# ==================== Expression Engine Tests ====================

class TestExpressionEngine(unittest.TestCase):
    def setUp(self):
        self.engine = SimpleExpressionEngine()

    def test_simple_arithmetic(self):
        self.assertEqual(self.engine.evaluate("1 + 2", {}), 3)
        self.assertEqual(self.engine.evaluate("10 * 3", {}), 30)
        self.assertEqual(self.engine.evaluate("100 / 4", {}), 25.0)

    def test_variable_access(self):
        self.assertEqual(self.engine.evaluate("item * 2", {"item": 5}), 10)
        self.assertEqual(self.engine.evaluate("item + 1", {"item": 9}), 10)

    def test_dotted_access(self):
        result = self.engine.evaluate("item.name", {"item": {"name": "宝刀"}})
        self.assertEqual(result, "宝刀")

    def test_comparison(self):
        self.assertTrue(self.engine.evaluate("item > 2", {"item": 5}))
        self.assertFalse(self.engine.evaluate("item > 10", {"item": 5}))

    def test_template_interpolation(self):
        result = self.engine.evaluate("Hello {{name}}, count={{count}}", {"name": "world", "count": 5})
        self.assertEqual(result, "Hello world, count=5")

    def test_boolean_expression(self):
        self.assertTrue(self.engine.evaluate_boolean("score >= 60", {"score": 85}))
        self.assertFalse(self.engine.evaluate_boolean("score >= 60", {"score": 30}))

    def test_empty_expression(self):
        self.assertIsNone(self.engine.evaluate("", {}))
        self.assertIsNone(self.engine.evaluate("  ", {}))


# ==================== Builder Tests ====================

class TestListBuilderExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = ListBuilderExecutor()

    def test_build_from_arguments(self):
        result = self.executor.execute(
            config={"arguments": [
                {"name": "item1", "value": 100},
                {"name": "item2", "value": "宝刀"},
                {"name": "item3", "value": True},
            ]},
            input_data={}
        )
        self.assertEqual(result["value"], [100, "宝刀", True])
        self.assertEqual(result["__runtime_type__"], "list")

    def test_build_from_input_data(self):
        result = self.executor.execute(
            config={},
            input_data={"a": 1, "b": 2}
        )
        self.assertEqual(result["count"], 2)


class TestObjectBuilderExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = ObjectBuilderExecutor()

    def test_build_from_arguments(self):
        result = self.executor.execute(
            config={"arguments": [
                {"name": "id", "value": "1001"},
                {"name": "name", "value": "宝刀"},
                {"name": "quality", "value": "5"},
            ]},
            input_data={}
        )
        self.assertEqual(result["value"]["id"], 1001)
        self.assertEqual(result["value"]["name"], "宝刀")
        self.assertEqual(result["value"]["quality"], 5)
        self.assertEqual(result["__runtime_type__"], "object")


class TestDictBuilderExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = DictBuilderExecutor()

    def test_build_dict(self):
        result = self.executor.execute(
            config={"arguments": [
                {"name": "1001", "value": '{"name":"宝刀","quality":5}'},
            ]},
            input_data={}
        )
        self.assertIn("1001", result["value"])
        self.assertEqual(result["__runtime_type__"], "object")


# ==================== Expression Node Tests ====================

class TestCalculateExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = CalculateExecutor()

    def test_calculate_math(self):
        result = self.executor.execute(
            config={"expression": "price * count * discount", "arguments": [
                {"name": "price", "value": "100"},
                {"name": "count", "value": "2"},
                {"name": "discount", "value": "0.8"},
            ]},
            input_data={}
        )
        self.assertEqual(result["value"], 160)

    def test_calculate_from_input(self):
        result = self.executor.execute(
            config={"expression": "a + b"},
            input_data={"a": 10, "b": 20}
        )
        self.assertEqual(result["value"], 30)


class TestTemplateExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = TemplateExecutor()

    def test_template_interpolation(self):
        result = self.executor.execute(
            config={"template": "物品{{name}}，数量{{count}}", "arguments": [
                {"name": "name", "value": "宝刀"},
                {"name": "count", "value": "5"},
            ]},
            input_data={}
        )
        self.assertEqual(result["value"], "物品宝刀，数量5")


class TestConditionExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = ConditionExecutor()

    def test_condition_true(self):
        result = self.executor.execute(
            config={"expression": "score >= 60", "arguments": [
                {"name": "score", "value": "85"},
            ]},
            input_data={}
        )
        self.assertTrue(result["value"])
        self.assertEqual(result["branch"], "true")

    def test_condition_false(self):
        result = self.executor.execute(
            config={"expression": "score >= 60", "arguments": [
                {"name": "score", "value": "30"},
            ]},
            input_data={}
        )
        self.assertFalse(result["value"])
        self.assertEqual(result["branch"], "false")

    def test_condition_direct_input(self):
        result = self.executor.execute(
            config={},
            input_data={"condition": True}
        )
        self.assertTrue(result["value"])
        self.assertEqual(result["branch"], "true")


# ==================== Control Flow Tests ====================

class TestIfExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = IfExecutor()

    def test_if_true_branch(self):
        result = self.executor.execute(
            config={},
            input_data={"condition": True, "trueValue": "pass", "falseValue": "fail"}
        )
        self.assertEqual(result["value"], "pass")
        self.assertEqual(result["branch"], "true")

    def test_if_false_branch(self):
        result = self.executor.execute(
            config={},
            input_data={"condition": False, "trueValue": "pass", "falseValue": "fail"}
        )
        self.assertEqual(result["value"], "fail")
        self.assertEqual(result["branch"], "false")

    def test_if_with_expression(self):
        result = self.executor.execute(
            config={"expression": "score >= 60"},
            input_data={"score": 85, "trueValue": "及格", "falseValue": "不及格"}
        )
        self.assertEqual(result["value"], "及格")
        self.assertEqual(result["branch"], "true")


class TestLoopExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = LoopExecutor()

    def test_loop_for_each(self):
        result = self.executor.execute(
            config={"mode": "for_each"},
            input_data={"list": [1, 2, 3]}
        )
        self.assertEqual(result["value"], [1, 2, 3])
        self.assertEqual(result["iterations"], 3)

    def test_loop_count(self):
        result = self.executor.execute(
            config={"mode": "count", "count": "5"},
            input_data={}
        )
        self.assertEqual(result["iterations"], 5)
        self.assertEqual(result["value"], [0, 1, 2, 3, 4])


class TestSwitchExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = SwitchExecutor()

    def test_switch_match_rule(self):
        result = self.executor.execute(
            config={"rules": [
                {"id": "1", "expression": "value == 'A'", "output": 1},
                {"id": "2", "expression": "value == 'B'", "output": 2},
            ]},
            input_data={"value": "A"}
        )
        self.assertEqual(result["branch"], "case1")

    def test_switch_no_match(self):
        result = self.executor.execute(
            config={"rules": [
                {"id": "1", "expression": "value == 'A'", "output": 1},
            ]},
            input_data={"value": "C"}
        )
        self.assertEqual(result["branch"], "default")


if __name__ == '__main__':
    unittest.main()
