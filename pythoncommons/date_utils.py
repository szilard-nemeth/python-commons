import datetime
import logging
import time

LOG = logging.getLogger(__name__)

DATEFORMAT_DASH_COLON = "%Y-%m-%d %H:%M:%S"


# https://medium.com/pythonhive/python-decorator-to-measure-the-execution-time-of-methods-fa04cb6bb36d
def timeit(method):
    def timed(*args, **kw):
        def print_time(method_name, time_value):
            pretty_time = TimeUtilities.prettify_time(time_value)
            LOG.info("Method runtime: %s: %s", method_name, pretty_time)

        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        if "log_time" in kw:
            name = kw.get("log_name", method.__name__.upper())
            kw["log_time"][name] = int((te - ts) * 1000)
        else:
            print_time(method.__name__, (te - ts))
        return result

    return timed


class TimeUtilities:
    SECONDS = "seconds"
    MINUTES = "minutes"
    HOURS = "hours"
    DAYS = "days"

    @classmethod
    def prettify_time(cls, seconds):
        # Credits: https://gist.github.com/thatalextaylor/7408395
        seconds = int(seconds)
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)

        # TODO generate pairs of curly braces with range()
        if days > 0:
            return "{} {}, {} {}, {} {}, {} {}".format(
                days, cls.DAYS, hours, cls.HOURS, minutes, cls.MINUTES, seconds, cls.SECONDS
            )
        elif hours > 0:
            return "{} {}, {} {}, {} {}".format(hours, cls.HOURS, minutes, cls.MINUTES, seconds, cls.SECONDS)
        elif minutes > 0:
            return "{} {}, {} {}".format(minutes, cls.MINUTES, seconds, cls.SECONDS)
        else:
            return "{} {}".format(seconds, cls.SECONDS)


class DateUtils:
    WIN_EPOCH = datetime.datetime(1601, 1, 1)

    @staticmethod
    def get_current_datetime(fmt="%Y%m%d_%H%M%S"):
        return DateUtils.now_formatted(fmt)

    @classmethod
    def now_formatted(cls, fmt):
        return DateUtils.now().strftime(fmt)

    @classmethod
    def from_iso_format(cls, date_str):
        return datetime.date.fromisoformat(date_str)

    @classmethod
    def now(cls):
        return datetime.datetime.now()

    @classmethod
    def create_datetime_from_timestamp(cls, timestamp: int):
        return datetime.datetime.fromtimestamp(timestamp)

    @classmethod
    def format_unix_timestamp(cls, timestamp: int):
        dt = DateUtils.create_datetime_from_timestamp(timestamp)
        return DateUtils.convert_datetime_to_str(dt, DATEFORMAT_DASH_COLON)

    @classmethod
    def add_microseconds_to_win_epoch(cls, microseconds):
        return DateUtils.WIN_EPOCH + datetime.timedelta(microseconds=microseconds)

    @classmethod
    def get_current_time_minus(cls, seconds=None, minutes=None, hours=None, days=None) -> datetime:
        now = datetime.datetime.now()
        return cls._datetime_minus(now, days, hours, minutes, seconds)

    @classmethod
    def datetime_minus(cls, dt: datetime, seconds=None, minutes=None, hours=None, days=None) -> datetime:
        return cls._datetime_minus(dt, days, hours, minutes, seconds)

    @classmethod
    def _datetime_minus(cls, dt: datetime, days, hours, minutes, seconds) -> datetime:
        kwargs = {}
        if seconds:
            kwargs["seconds"] = seconds
        if minutes:
            kwargs["minutes"] = minutes
        if hours:
            kwargs["hours"] = hours
        if days:
            kwargs["days"] = days
        return dt - datetime.timedelta(**kwargs)

    @classmethod
    def convert_to_datetime(cls, date_string, fmt):
        return datetime.datetime.strptime(date_string, fmt)

    @classmethod
    def convert_datetime_to_str(cls, datetime_obj, fmt):
        return datetime_obj.strftime(fmt)

    @classmethod
    def get_datetime(cls, y, m, d):
        return datetime.datetime(y, m, d)

    @classmethod
    def get_datetime_from_date(cls, date_obj, min_time=False, max_time=False):
        if not min_time and not max_time:
            raise ValueError("Either min_time or max_time had set to True!")

        if min_time:
            return datetime.datetime.combine(date_obj, datetime.datetime.min.time())
        if max_time:
            return datetime.datetime.combine(date_obj, datetime.datetime.max.time())

    @classmethod
    def reset_to_midnight(cls, dt: datetime.datetime):
        return datetime.datetime.combine(dt, datetime.datetime.min.time())
