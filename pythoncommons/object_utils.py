import inspect
import logging
import pickle
from typing import Any, List, Dict, Tuple, Iterable

LOG = logging.getLogger(__name__)


class ObjUtils:
    @staticmethod
    def print_properties(obj):
        LOG.info("Printing properties of obj: %s", obj)
        for prop, value in vars(obj).items():
            LOG.info("%s: %s", prop, value)

    @staticmethod
    def get_class_members(clazz):
        attributes = inspect.getmembers(clazz, lambda a: not (inspect.isroutine(a)))
        return [a for a in attributes if not (a[0].startswith("__") and a[0].endswith("__"))]

    @staticmethod
    def get_properties(obj):
        return [(prop, value) for prop, value in vars(obj).items()]

    @staticmethod
    def get_static_fields(clazz):
        return [v for v, m in vars(clazz).items() if not (v.startswith("_") or callable(m))]

    @staticmethod
    def get_static_fields_with_values(clazz):
        return {v: getattr(clazz, v) for v, m in vars(clazz).items() if not (v.startswith("_") or callable(m))}

    @staticmethod
    def ensure_all_attrs_present(obj, attrs: List[Tuple[str, str]]):
        not_found_attrs: List[Tuple[str, str]] = []

        for attr_tup in attrs:
            attr_name = attr_tup[0]
            if not hasattr(obj, attr_name):
                not_found_attrs.append(attr_tup)

        if not not_found_attrs:
            return
        if len(not_found_attrs) == 1:
            tup: Tuple[str, str] = not_found_attrs[0]
            raise ValueError("Attribute '{}' (name: {}) is not specified!".format(*tup))
        elif len(not_found_attrs) > 1:
            exc_message = "The following attributes are not specified: \n"
            for tup in not_found_attrs:
                exc_message += "Attribute '{}' (name: {})\n".format(*tup)
            raise ValueError(exc_message)

    @staticmethod
    def ensure_all_attrs_with_value(obj, attrs: Iterable[str], expected_value):
        not_found_attrs: List[str] = []
        attrs_with_different_value: List[Tuple[str, Any]] = []

        for attr_name in attrs:
            if not hasattr(obj, attr_name):
                not_found_attrs.append(attr_name)
            elif getattr(obj, attr_name) != expected_value:
                attrs_with_different_value.append((attr_name, getattr(obj, attr_name)))

        if not_found_attrs:
            raise ValueError("The following attributes are not found: {}".format(not_found_attrs))
        if attrs_with_different_value:
            raise ValueError(
                "The following attributes are not having value of '{}': {}".format(
                    expected_value, attrs_with_different_value
                )
            )


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

    @staticmethod
    def get_dict_keys_with_prefix(dictionary: Dict[Any, Any], prefix: str):
        return [key.startswith(prefix) for key in dictionary.keys()]

    @staticmethod
    def pairwise(iterable):
        "s -> (s0, s1), (s2, s3), (s4, s5), ..."
        a = iter(iterable)
        return zip(a, a)


class PickleUtils:
    @staticmethod
    def dump(data, file):
        with open(file, "wb") as f:
            pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def load(file):
        with open(file, "rb") as f:
            # The protocol version used is detected automatically, so we do not
            # have to specify it.
            return pickle.load(f)
