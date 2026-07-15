from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor
import json
import difflib
import os


class DiffExecutor(BaseNodeExecutor):
    type = "diff"

    def execute(self, config: dict, input_data: dict) -> dict:
        """
        Diff node: compares two string inputs (内容1 / 内容2) and returns whether they are
        identical plus the data needed for the front-end Monaco DiffEditor.

        Input ports:
          - contentA  (any)  内容1 — original text / file reference / object
          - contentB  (any)  内容2 — modified text / file reference / object

        Output ports:
          - isSame    (boolean) 是否相同 — True if contentA == contentB byte-for-byte
          - _diffData (hidden)  passthrough bundle consumed by the front-end renderer only;
                                contains { contentA, contentB, stats, unifiedDiff }
                                NOT exposed as a user-visible output port

        The unified diff and statistics are also carried in the output so the front-end
        DiffRenderer and property panel can render the Monaco side-by-side view.
        """
        content_a = input_data.get("contentA", "")
        content_b = input_data.get("contentB", "")

        # Coerce to string — if input is a JSON object/list, pretty-print it
        # so the diff shows meaningful multi-line differences.
        # For JSON strings (str), try to parse and re-format for multi-line diff.
        # For file references (dict with localPath), read actual file content.
        def _to_string(val):
            if val is None:
                return ""
            # File reference (P4File/ExcelSearch output): read from disk
            if isinstance(val, dict) and 'localPath' in val:
                lp = val['localPath']
                if os.path.isfile(lp):
                    try:
                        raw = open(lp, 'r', encoding='utf-8', errors='replace').read()
                        # If it looks like JSON, pretty-print for readable diff
                        stripped = raw.strip()
                        if (stripped.startswith('{') and stripped.endswith('}')) or \
                           (stripped.startswith('[') and stripped.endswith(']')):
                            try:
                                parsed = json.loads(stripped)
                                return json.dumps(parsed, indent=2, ensure_ascii=False, sort_keys=True)
                            except (json.JSONDecodeError, ValueError):
                                pass
                        return raw
                    except (IOError, OSError):
                        pass
                # localPath doesn't exist as file — fall through to dict serialization
            if isinstance(val, (dict, list)):
                try:
                    return json.dumps(val, indent=2, ensure_ascii=False, sort_keys=True)
                except (TypeError, ValueError):
                    return str(val)
            if isinstance(val, str):
                stripped = val.strip()
                # Heuristic: try to parse as JSON for pretty-printing
                if (stripped.startswith('{') and stripped.endswith('}')) or \
                   (stripped.startswith('[') and stripped.endswith(']')):
                    try:
                        parsed = json.loads(stripped)
                        return json.dumps(parsed, indent=2, ensure_ascii=False, sort_keys=True)
                    except (json.JSONDecodeError, ValueError):
                        pass
            return str(val)

        content_a = _to_string(content_a)
        content_b = _to_string(content_b)

        is_same = content_a == content_b

        # ---- git-style unified diff ------------------------------------------------
        lines_a = content_a.splitlines(keepends=True)
        lines_b = content_b.splitlines(keepends=True)
        if lines_a and not lines_a[-1].endswith("\n"):
            lines_a[-1] += "\n"
        if lines_b and not lines_b[-1].endswith("\n"):
            lines_b[-1] += "\n"

        unified_lines = list(
            difflib.unified_diff(
                lines_a,
                lines_b,
                fromfile="内容1",
                tofile="内容2",
                lineterm="\n",
            )
        )
        unified_diff = "".join(unified_lines)

        # ---- basic stats -----------------------------------------------------------
        additions = sum(1 for ln in unified_lines if ln.startswith("+") and not ln.startswith("+++"))
        deletions = sum(1 for ln in unified_lines if ln.startswith("-") and not ln.startswith("---"))

        stats = {
            "additions": additions,
            "deletions": deletions,
            "changedLines": additions + deletions,
            "lengthA": len(content_a),
            "lengthB": len(content_b),
        }

        return {
            # User-visible output port
            "isSame": is_same,
            # Hidden renderer data (read by front-end DiffRenderer via runOutput)
            "contentA": content_a,
            "contentB": content_b,
            "unifiedDiff": unified_diff,
            "stats": stats,
        }
