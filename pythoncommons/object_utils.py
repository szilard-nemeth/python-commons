import logging
from typing import Any, List

LOG = logging.getLogger(__name__)


class ObjUtils:
    @staticmethod
    def print_properties(obj):
        LOG.info("Printing properties of obj: %s", obj)
        for prop, value in vars(obj).items():
            LOG.info("%s: %s", prop, value)

    @staticmethod
    def get_properties(obj):
        return [(prop, value) for prop, value in vars(obj).items()]

    @staticmethod
    def get_static_fields(clazz):
        return [v for v, m in vars(clazz).items() if not (v.startswith("_") or callable(m))]

    @staticmethod
    def get_static_fields_with_values(clazz):
        return {v: getattr(clazz, v) for v, m in vars(clazz).items() if not (v.startswith("_") or callable(m))}


class ListUtils:
    @staticmethod
    def get_duplicates(lst: List[Any]):
        seen = set()
        dupes = set()
        for x in lst:
            if x not in seen:
                seen.add(x)
            elif x not in dupes:
                dupes.add(x)
        return dupes
