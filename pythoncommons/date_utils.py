import datetime
import logging
LOG = logging.getLogger(__name__)


class DateUtils:
    WIN_EPOCH = datetime.datetime(1601, 1, 1)

    @staticmethod
    def get_current_datetime(fmt="%Y%m%d_%H%M%S"):
        return DateUtils.now_formatted(fmt)

    @classmethod
    def now_formatted(cls, fmt):
        return DateUtils.now().strftime(fmt)

    @classmethod
    def from_iso_format(cls):
        return datetime.date.fromisoformat

    @classmethod
    def now(cls):
        return datetime.datetime.now()

    @classmethod
    def add_microseconds_to_win_epoch(cls, microseconds):
        return DateUtils.WIN_EPOCH + datetime.timedelta(microseconds=microseconds)

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
