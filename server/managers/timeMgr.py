import time
import logging
import re
from lib.Singleton import singleton
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import uuid
import g

logger = logging.getLogger('apscheduler')
logger.setLevel(logging.WARNING)

TIMESTAMP_FLAG: int = 0
TIMEDELTA: timedelta = datetime.fromtimestamp(0) - datetime.utcfromtimestamp(0)
# 需要知道时间进行校准，目前windows是8，Linux开发机是0
TIMEZONE: int = int(TIMEDELTA.total_seconds() / 60 / 60)

# 默认的云主机或者线上机器都是0时区，所以我们统一增加时区变量，用于后续部署在国内或海外
TARGET_TIMEZONE: int = 8

# 需要调整的时间量，要再当前时间加上这个小时量
DELTA_TIMEZONE: int = TARGET_TIMEZONE - TIMEZONE


DATE_FORMAT = "%Y/%m/%d %H:%M:%S"


def getDateFromString(dateString: str) -> datetime:
    return datetime.strptime(dateString, DATE_FORMAT)


def getStringFromDate(dt: datetime) -> str:
    return dt.strftime(DATE_FORMAT)


def getCurrentDateTime() -> datetime:
    return datetime.now() + timedelta(hours=DELTA_TIMEZONE)


def getCurrentTimeStamp() -> float:
    return (datetime.now() + timedelta(hours=DELTA_TIMEZONE)).timestamp()


_decorated_cron_infos = []


def get_decorated_cron_infos():
    return list(_decorated_cron_infos)


def _normalize_weekday_token(token: str) -> str:
    t = token.strip().lower()
    if not t:
        return ''
    if t in ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'):
        return t
    if t.startswith('mon'):
        return 'mon'
    if t.startswith('tue'):
        return 'tue'
    if t.startswith('wed'):
        return 'wed'
    if t.startswith('thu'):
        return 'thu'
    if t.startswith('fri'):
        return 'fri'
    if t.startswith('sat'):
        return 'sat'
    if t.startswith('sun'):
        return 'sun'
    return t


def _parse_time_of_day(spec: str):
    m = re.match(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$', spec.strip())
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2))
    second = int(m.group(3)) if m.group(3) is not None else 0
    if hour < 0 or hour > 23 or minute < 0 or minute > 59 or second < 0 or second > 59:
        return None
    return hour, minute, second


def _parse_cron_spec(spec):
    if isinstance(spec, dict):
        if 'type' not in spec:
            raise ValueError('cron spec dict missing type')
        return dict(spec)

    s = str(spec or '').strip()
    if not s:
        raise ValueError('cron spec is empty')

    m = re.match(r'^every\s+(\d+)\s*([a-zA-Z]+)\s*$', s, flags=re.IGNORECASE)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        if unit in ('second', 'seconds', 'sec', 'secs', 's'):
            return {'type': 'interval', 'second': n}
        if unit in ('minute', 'minutes', 'min', 'mins', 'm'):
            return {'type': 'interval', 'minute': n}
        if unit in ('hour', 'hours', 'h'):
            return {'type': 'interval', 'hour': n}
        if unit in ('day', 'days', 'd'):
            return {'type': 'interval', 'day': n}
        raise ValueError(f'unknown interval unit: {unit}')

    m = re.match(r'^daily\s+(.+)$', s, flags=re.IGNORECASE)
    if m:
        t = _parse_time_of_day(m.group(1))
        if not t:
            raise ValueError(f'invalid daily time: {m.group(1)}')
        hour, minute, second = t
        return {'type': 'cron', 'day': '*', 'hour': hour, 'minute': minute, 'second': second}

    m = re.match(r'^weekly\s+(.+?)\s+(.+)$', s, flags=re.IGNORECASE)
    if m:
        raw_days = m.group(1).strip()
        t = _parse_time_of_day(m.group(2))
        if not t:
            raise ValueError(f'invalid weekly time: {m.group(2)}')
        hour, minute, second = t
        if raw_days == '*':
            day_of_week = '*'
        else:
            day_tokens = [d for d in raw_days.split(',') if d.strip()]
            day_of_week = ','.join([_normalize_weekday_token(d) for d in day_tokens])
        return {'type': 'cron', 'day_of_week': day_of_week, 'hour': hour, 'minute': minute, 'second': second}

    raise ValueError(f'unsupported cron spec: {s}')


def cron(spec, job_id=None):
    def _decorator(func):
        info = _parse_cron_spec(spec)
        info['job_id'] = job_id or f"{func.__module__}.{func.__name__}"
        logger.info(f"czx register cron job: {info['job_id']} with spec: {spec} parsed as {info}")
        _decorated_cron_infos.append((info, func))
        return func
    return _decorator


@singleton
class TimeMgr(object):
    schedule = None

    def __init__(self):
        TimeMgr.start_tick()

    @staticmethod
    def initServerSchedule(cron_infos=None):
        if cron_infos is None:
            cron_infos = []
        cron_infos = list(get_decorated_cron_infos()) + list(cron_infos)
        logger.info(f'timeMgr initServerSchedule: {cron_infos}')
        idx = 0
        for cron_info in cron_infos:
            idx += 1
            job_id = cron_info[0].get('job_id') if isinstance(cron_info[0], dict) else None
            if cron_info[0].get('type', 'cron') == 'cron':
                TimeMgr.add_schedule_cron(cron_info[0], cron_info[1], job_id or f'serverCron_{idx}')
            else:  # interval
                TimeMgr.add_schedule_interval(cron_info[0], cron_info[1], job_id or f'serverInterval_{idx}')

    @staticmethod
    def start_tick():
        TimeMgr.scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
        TimeMgr.scheduler.start()

    @staticmethod
    def add_schedule_cron(cron_info, callback, job_id):
        kwargs = {k: v for k, v in cron_info.items() if k not in ('type', 'job_id') and v is not None}
        job = TimeMgr.scheduler.add_job(callback, trigger='cron', id=job_id, replace_existing=True, **kwargs)
        return job

    @staticmethod
    def add_schedule_interval(interval_info, callback, job_id):
        kwargs = {
            'days': interval_info.get('day', 0),
            'hours': interval_info.get('hour', 0),
            'minutes': interval_info.get('minute', 0),
            'seconds': interval_info.get('second', 0)
        }
        job = TimeMgr.scheduler.add_job(callback, trigger='interval', id=job_id, replace_existing=True, **kwargs)
        return job

    @staticmethod
    def add_schedule_once(delay, callback, job_id):
        # delay: second
        def _job_wrapper():
            print('czx add_schedule_once _job_wrapper', time.time())
            TimeMgr.remove_schedule(job_id)
            callback()
        job = TimeMgr.scheduler.add_job(_job_wrapper, trigger='interval', seconds=delay, id=job_id, replace_existing=True)
        return job

    @staticmethod
    def add_timer(delay, callback):
        # 用schedule实现类似addTimer的效果
        job_id = str(uuid.uuid4())

        def _job_wrapper():
            print('czx add_timer _job_wrapper', time.time())
            TimeMgr.remove_schedule(job_id)
            callback()

        TimeMgr.scheduler.add_job(_job_wrapper, trigger='interval', seconds=delay, id=job_id, replace_existing=True)
        return job_id

    @staticmethod
    def cancel_timer(job_id):
        TimeMgr.scheduler.remove_job(job_id)

    @staticmethod
    def remove_schedule(job_id):
        TimeMgr.scheduler.remove_job(job_id)


timeMgr = TimeMgr()
g.timeMgr = timeMgr
