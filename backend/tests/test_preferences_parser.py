from src.utils.preferences_parser import parse_structured_preferences


def test_parser_preserves_home_lodging_selection_from_form():
    """The structured form must retain the explicit no-hotel choice."""
    assert parse_structured_preferences({"lodging_mode": "home"}) == {"lodging_mode": "home"}
