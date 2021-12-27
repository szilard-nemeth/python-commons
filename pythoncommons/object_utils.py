import logging
from typing import Any, List, Dict

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

    @staticmethod
    def split_to_chunks(lst, n):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i : i + n]


class CollectionUtils:
    @staticmethod
    def sum_len_of_lists_in_dict(d: Dict):
        return sum([len(lst) for lst in d.values()])

    @staticmethod
    def partition(pred, iterable):
        trues = []
        falses = []
        for item in iterable:
            if pred(item):
                trues.append(item)
            else:
                falses.append(item)
        return trues, falses

    @staticmethod
    def partition_multi(predicates, iterable) -> List[List[Any]]:
        lists = []
        for i in range(len(predicates)):
            lists.append([])

        for item in iterable:
            for idx, pred in enumerate(predicates):
                if pred(item):
                    lists[idx].append(item)
        return lists
