from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor
import json


class DiffExecutor(BaseNodeExecutor):
    type = "diff"

    def execute(self, config: dict, input_data: dict) -> dict:
        """
        Diff node: compares two string inputs and outputs diff result + isSame boolean.
        - stringA and stringB come from input_data (connected upstream)
        - Output:
          - stringA: original string (for frontend diff display)
          - stringB: modified string (for frontend diff display)
          - isSame: whether the two strings are identical
          - diffResult: JSON string containing diff details
        """
        string_a = input_data.get("stringA", "")
        string_b = input_data.get("stringB", "")

        # Ensure both are strings
        string_a = str(string_a) if string_a is not None else ""
        string_b = str(string_b) if string_b is not None else ""

        is_same = string_a == string_b

        # Build diff result JSON
        diff_info = {
            "stringA": string_a,
            "stringB": string_b,
            "isSame": is_same,
            "lengthA": len(string_a),
            "lengthB": len(string_b),
        }

        return {
            "stringA": string_a,
            "stringB": string_b,
            "isSame": is_same,
            "diffResult": json.dumps(diff_info, ensure_ascii=False),
        }
