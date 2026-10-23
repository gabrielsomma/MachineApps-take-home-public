import pytest

from app.geometry import TableId, is_on_table, table_point_to_robot_frame


@pytest.mark.parametrize(
    "point, expected",
    [
        ((0, 0), (-900, 400)),
        ((500, 0), (-400, 400)),
        ((0, 500), (-900, 900)),
        ((250, 250), (-650, 650)),
    ],
)
def test_table_a_is_translated_only(point, expected):
    assert table_point_to_robot_frame(TableId.A, *point) == pytest.approx(expected)


@pytest.mark.parametrize(
    "point, expected",
    [
        ((0, 0), (250, -550)),
        # X axis points down-right.
        ((500, 0), (603.553, -903.553)),
        # Y axis points up-right.
        ((0, 500), (603.553, -196.447)),
        ((500, 500), (957.107, -550)),
    ],
)
def test_table_b_is_rotated_minus_45_degrees(point, expected):
    assert table_point_to_robot_frame(TableId.B, *point) == pytest.approx(expected, abs=1e-3)


@pytest.mark.parametrize("table", list(TableId))
def test_whole_tables_fit_inside_robot_limits(table):
    for corner in [(0, 0), (500, 0), (0, 500), (500, 500)]:
        x, y = table_point_to_robot_frame(table, *corner)
        assert -1000 <= x <= 1000 and -1000 <= y <= 1000


@pytest.mark.parametrize("point", [(0, 0), (500, 500), (250, 0), (12.5, 499.9)])
def test_points_on_table_are_accepted(point):
    assert is_on_table(TableId.A, *point) is True


@pytest.mark.parametrize("point", [(-1, 0), (0, -0.1), (500.1, 0), (0, 600)])
def test_points_off_table_are_rejected(point):
    assert is_on_table(TableId.B, *point) is False
