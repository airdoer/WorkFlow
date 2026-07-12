"""
CronExecutor — Cron 定时触发节点

输入：cron 表达式字符串（如 "0 2 * * 0"）
行为：点击运行后，按 cron 表达式周期性触发下游节点执行
限制：最低频率 1 分钟（60 秒）
"""

import re
import time
import threading
import logging
from datetime import datetime
from Implement.workflowImpl.nodeExecutor import BaseNodeExecutor

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Cron expression parser (minimal, no external dependency)
# ─────────────────────────────────────────────────────────────────────────────

_CRON_FIELDS = ['minute', 'hour', 'dayOfMonth', 'month', 'dayOfWeek']

def parse_cron(expr: str) -> dict:
    """Parse a 5-field cron expression into a structured dict.
    Returns { field_name: field_value } where field_value is one of:
      - '*'   (any)
      - int   (specific value)
      - list  (specific values, e.g. "1,3,5")
      - tuple (range with step, e.g. (1,10,2) for "1-10/2")
    Raises ValueError on invalid expressions.
    """
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Cron 表达式必须有 5 个字段（分 时 日 月 周），当前有 {len(parts)} 个")

    field_ranges = {
        'minute':      (0, 59),
        'hour':        (0, 23),
        'dayOfMonth':  (1, 31),
        'month':       (1, 12),
        'dayOfWeek':   (0, 6),   # 0=Sunday
    }

    result = {}
    for i, field_name in enumerate(_CRON_FIELDS):
        raw = parts[i]
        lo, hi = field_ranges[field_name]
        result[field_name] = _parse_field(raw, lo, hi, field_name)

    return result


def _parse_field(raw: str, lo: int, hi: int, name: str):
    """Parse a single cron field."""
    # */step
    if raw.startswith('*/'):
        step = int(raw[2:])
        if step < 1:
            raise ValueError(f"{name}: 步长必须 >= 1")
        return (lo, hi, step)

    # * (every)
    if raw == '*':
        return (lo, hi, 1)

    # range with optional step: 1-10 or 1-10/2
    m = re.match(r'^(\d+)-(\d+)(?:/(\d+))?$', raw)
    if m:
        start, end = int(m.group(1)), int(m.group(2))
        step = int(m.group(3)) if m.group(3) else 1
        if start < lo or end > hi:
            raise ValueError(f"{name}: 范围 {start}-{end} 超出允许范围 {lo}-{hi}")
        if step < 1:
            raise ValueError(f"{name}: 步长必须 >= 1")
        return (start, end, step)

    # comma-separated: 1,3,5
    if ',' in raw:
        vals = []
        for v in raw.split(','):
            n = int(v)
            if n < lo or n > hi:
                raise ValueError(f"{name}: 值 {n} 超出允许范围 {lo}-{hi}")
            vals.append(n)
        return sorted(vals)

    # single number
    n = int(raw)
    if n < lo or n > hi:
        raise ValueError(f"{name}: 值 {n} 超出允许范围 {lo}-{hi}")
    return n


def cron_min_interval_seconds(parsed: dict) -> float:
    """Estimate the minimum interval (in seconds) for a parsed cron expression.
    We check the most frequent field to determine the fastest possible cycle.
    """
    minute = parsed['minute']
    # If minute is a range/tuple with step, or *, the minimum gap between
    # consecutive matches gives us the minimum interval.
    if isinstance(minute, tuple):
        # (start, end, step) → minimum gap = step * 60 seconds
        _, _, step = minute
        return step * 60
    elif isinstance(minute, list):
        # sort and find minimum gap
        sorted_vals = sorted(minute)
        if len(sorted_vals) <= 1:
            return 60 * 60  # at most once per hour
        min_gap = min(b - a for a, b in zip(sorted_vals, sorted_vals[1:]))
        if min_gap == 0:
            min_gap = 1
        return min_gap * 60
    elif isinstance(minute, int):
        # specific minute → once per hour minimum
        return 60 * 60
    else:
        return 60 * 60  # fallback


# ─────────────────────────────────────────────────────────────────────────────
# Global Cron Registry
# ─────────────────────────────────────────────────────────────────────────────

class CronRegistry:
    """Thread-safe registry of all running cron jobs."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._crons: dict = {}  # cron_id → { ... }
        self._lock = threading.Lock()

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, cron_id: str, cron_expr: str, workflow_id: str, node_id: str,
                 callback, stop_event: threading.Event, thread: threading.Thread):
        with self._lock:
            self._crons[cron_id] = {
                'cron_id': cron_id,
                'cron_expr': cron_expr,
                'workflow_id': workflow_id,
                'node_id': node_id,
                'callback': callback,
                'stop_event': stop_event,
                'thread': thread,
                'started_at': datetime.now().isoformat(),
                'last_run': None,
                'run_count': 0,
                'status': 'running',
            }
        logger.info("[CronRegistry] Registered cron %s: expr=%s wf=%s node=%s",
                     cron_id, cron_expr, workflow_id, node_id)

    def unregister(self, cron_id: str):
        with self._lock:
            if cron_id in self._crons:
                self._crons[cron_id]['status'] = 'stopped'
                logger.info("[CronRegistry] Unregistered cron %s", cron_id)

    def stop(self, cron_id: str) -> bool:
        with self._lock:
            entry = self._crons.get(cron_id)
            if not entry or entry['status'] != 'running':
                return False
            entry['stop_event'].set()
            entry['status'] = 'stopping'
            logger.info("[CronRegistry] Stopping cron %s", cron_id)
            return True

    def list_all(self) -> list:
        with self._lock:
            return [
                {
                    'cron_id': c['cron_id'],
                    'cron_expr': c['cron_expr'],
                    'workflow_id': c['workflow_id'],
                    'node_id': c['node_id'],
                    'started_at': c['started_at'],
                    'last_run': c['last_run'],
                    'run_count': c['run_count'],
                    'status': c['status'],
                }
                for c in self._crons.values()
            ]

    def update_run(self, cron_id: str):
        with self._lock:
            entry = self._crons.get(cron_id)
            if entry:
                entry['last_run'] = datetime.now().isoformat()
                entry['run_count'] += 1

    def cleanup_stopped(self):
        """Remove entries that have been stopped for a while."""
        with self._lock:
            to_remove = [cid for cid, c in self._crons.items() if c['status'] in ('stopped', 'stopping')]
            for cid in to_remove:
                del self._crons[cid]


# ─────────────────────────────────────────────────────────────────────────────
# CronExecutor
# ─────────────────────────────────────────────────────────────────────────────

MIN_INTERVAL_SECONDS = 60  # Minimum 1 minute


class CronExecutor(BaseNodeExecutor):
    type = "cron"

    def execute(self, config: dict, input_data: dict) -> dict:
        """
        Validate and start a cron schedule.

        config: { cronExpr: "0 2 * * 0", workflowId: "...", nodeId: "..." }
        input_data: (unused, cron is a trigger node)

        Returns:
          { success: true, cronId: "...", message: "..." }
          or { error: "..." }
        """
        cron_expr = config.get('cronExpr', '').strip()
        workflow_id = config.get('workflowId', '')
        node_id = config.get('nodeId', '')

        if not cron_expr:
            return {'error': '请输入 Cron 表达式（如: 0 2 * * 0）'}

        # Parse and validate
        try:
            parsed = parse_cron(cron_expr)
        except ValueError as e:
            return {'error': f'Cron 表达式无效: {e}'}

        # Check minimum interval
        min_interval = cron_min_interval_seconds(parsed)
        if min_interval < MIN_INTERVAL_SECONDS:
            return {'error': f'Cron 频率过高（最小间隔 {min_interval:.0f} 秒），最低要求 {MIN_INTERVAL_SECONDS} 秒（1 分钟）'}

        # Generate cron_id
        import uuid
        cron_id = f"cron_{uuid.uuid4().hex[:8]}"

        # Create stop event and start background thread
        stop_event = threading.Event()

        def cron_loop():
            """Background thread that triggers callback at cron intervals."""
            logger.info("[CronLoop] Started cron_id=%s expr=%s", cron_id, cron_expr)
            while not stop_event.is_set():
                # Calculate next run time
                now = datetime.now()
                next_run = _next_cron_time(parsed, now)
                wait_seconds = max(0, (next_run - now).total_seconds())

                # Wait until next run (or stop)
                logger.info("[CronLoop] cron_id=%s next_run=%s wait=%.0fs", cron_id, next_run, wait_seconds)
                if stop_event.wait(timeout=wait_seconds):
                    break  # stop requested

                # Execute callback
                if not stop_event.is_set():
                    try:
                        CronRegistry.instance().update_run(cron_id)
                        logger.info("[CronLoop] cron_id=%s triggering at %s", cron_id, datetime.now().isoformat())
                        # The callback is provided by the API layer to trigger downstream execution
                        cb = CronRegistry.instance()._crons.get(cron_id, {}).get('callback')
                        if cb:
                            cb()
                    except Exception as e:
                        logger.exception("[CronLoop] cron_id=%s callback error: %s", cron_id, e)

            CronRegistry.instance().unregister(cron_id)
            logger.info("[CronLoop] Stopped cron_id=%s", cron_id)

        thread = threading.Thread(target=cron_loop, daemon=True, name=f"cron-{cron_id}")
        thread.start()

        # Register in global registry (callback will be set by API layer)
        CronRegistry.instance().register(
            cron_id=cron_id,
            cron_expr=cron_expr,
            workflow_id=workflow_id,
            node_id=node_id,
            callback=None,  # Will be set by API route
            stop_event=stop_event,
            thread=thread,
        )

        return {
            'success': True,
            'cronId': cron_id,
            'cronExpr': cron_expr,
            'message': f'Cron 已启动: {cron_expr}（ID: {cron_id}）',
        }


# ─────────────────────────────────────────────────────────────────────────────
# Next cron time calculator
# ─────────────────────────────────────────────────────────────────────────────

def _field_matches(field_val, current_val: int) -> bool:
    """Check if current value matches the cron field specification."""
    if isinstance(field_val, tuple):
        start, end, step = field_val
        if current_val < start or current_val > end:
            return False
        return (current_val - start) % step == 0
    elif isinstance(field_val, list):
        return current_val in field_val
    elif isinstance(field_val, int):
        return current_val == field_val
    return False


def _next_cron_time(parsed: dict, after: datetime) -> datetime:
    """Calculate the next time that matches the parsed cron expression, after `after`."""
    # Start from the next minute
    dt = after.replace(second=0, microsecond=0)
    dt = dt.replace(minute=dt.minute + 1) if dt.minute < 59 else dt.replace(minute=0, hour=dt.hour + 1)

    # Brute-force search (max 366*24*60 = 527040 iterations for a year)
    max_iterations = 527040
    for _ in range(max_iterations):
        if (_field_matches(parsed['minute'], dt.minute)
                and _field_matches(parsed['hour'], dt.hour)
                and _field_matches(parsed['dayOfMonth'], dt.day)
                and _field_matches(parsed['month'], dt.month)
                and _field_matches(parsed['dayOfWeek'], dt.weekday() % 7 if dt.weekday() == 6 else dt.weekday() + 1)):
            return dt
        # Advance by 1 minute
        dt = _add_minutes(dt, 1)

    # Fallback: 1 year from now
    return after.replace(year=after.year + 1)


def _add_minutes(dt: datetime, minutes: int) -> datetime:
    """Add minutes to a datetime, handling overflow."""
    from datetime import timedelta
    return dt + timedelta(minutes=minutes)
