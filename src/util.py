from typing import Callable, TypeVar, List

T = TypeVar("T")


def drop_both_ends(predicate: Callable[[T], bool], lst: List[T]) -> List[T]:
    """
    Drop elements from both ends of a list while a predicate is true.

    This function removes elements from the beginning and end of the list
    as long as they satisfy the given predicate.

    Args:
        predicate (Callable[[T], bool]): A function that takes an element and returns a boolean.
        lst (List[T]): The input list.

    Returns:
        List[T]: A new list with elements dropped from both ends.

    Example:
        >>> drop_both_ends(lambda x: x == 0, [0, 0, 1, 2, 3, 0, 0])
        [1, 2, 3]
    """
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
