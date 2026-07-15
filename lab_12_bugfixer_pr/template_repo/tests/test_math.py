from src.math import factorial


def test_factorial_zero():
    assert factorial(0) == 1


def test_factorial_one():
    assert factorial(1) == 1


def test_factorial_five():
    # 5! = 120. With the planted off-by-one this returns 24 and fails.
    assert factorial(5) == 120


def test_factorial_negative_raises():
    import pytest

    with pytest.raises(ValueError):
        factorial(-1)
