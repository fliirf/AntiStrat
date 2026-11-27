import pytest

from antistrat.config import REPO_ROOT, assert_outside_repo


def test_refuses_output_inside_repo():
    with pytest.raises(ValueError):
        assert_outside_repo(REPO_ROOT / "engine" / "rounds.csv")


def test_allows_output_outside_repo():
    assert_outside_repo(REPO_ROOT.parent / "antistrat-out" / "rounds.csv")
