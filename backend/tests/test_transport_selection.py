import pytest

from src.services.transport_selection import select_local_transport


@pytest.mark.parametrize(
    ("distance_km", "modes", "hour", "expected"),
    [
        (0.6, ["walking", "metro", "bus"], 10, "walking"),
        (3.0, ["walking", "metro", "bus"], 10, "metro"),
        (8.0, ["metro", "taxi"], 10, "taxi"),
        (3.0, ["metro", "taxi"], 23, "taxi"),
        (3.0, ["bus"], 10, "bus"),
    ],
)
def test_select_local_transport_uses_allowed_modes_by_distance_and_time(distance_km, modes, hour, expected):
    assert select_local_transport(distance_km, modes, hour) == expected
