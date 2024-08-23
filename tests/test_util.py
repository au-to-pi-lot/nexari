from src.util import drop_both_ends


def test_drop_both_ends_drops():
    assert drop_both_ends(lambda x: x == 0, [0, 0, 0, 2, 2, 2, 0, 0, 0]) == [2, 2, 2]


def test_drop_both_ends_leaves_middle():
    assert drop_both_ends(lambda x: x == 0, [0, 0, 0, 2, 0, 2, 0, 0, 0]) == [2, 0, 2]


def test_drop_both_ends_leaves_nonmatching():
    assert drop_both_ends(lambda x: x == 0, [2, 1, 2]) == [2, 1, 2]


def test_drop_both_ends_leaves_empty():
    assert drop_both_ends(lambda x: x == 0, []) == []


def test_drop_both_ends_removes_all():
    assert drop_both_ends(lambda x: x == 0, [0, 0, 0, 0]) == []
