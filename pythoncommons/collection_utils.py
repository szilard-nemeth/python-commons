from typing import Dict, List, Any


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
