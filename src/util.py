from typing import Callable, TypeVar, List

T = TypeVar('T')


def drop_both_ends(predicate: Callable[[T], bool], lst: List[T]):
    # Drop from the beginning
    start = 0
    for i, item in enumerate(lst):
        if not predicate(item):
            start = i
            break
    else:  # entire list matches predicate
        return []

    # Drop from the end
    end = len(lst)
    for i, item in enumerate(reversed(lst)):
        if not predicate(item):
            end = len(lst) - i
            break

    return lst[start:end]
