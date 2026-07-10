from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor
import json
import difflib


class DiffExecutor(BaseNodeExecutor):
    type = "diff"

    def execute(self, config: dict, input_data: dict) -> dict:
        """
        Diff node: compares two string inputs (内容1 / 内容2) and returns whether they are
        identical plus the data needed for the front-end Monaco DiffEditor.

        Input ports:
          - contentA  (string)  内容1 — original text
          - contentB  (string)  内容2 — modified text

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

        # Coerce to string
        content_a = str(content_a) if content_a is not None else ""
        content_b = str(content_b) if content_b is not None else ""

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
