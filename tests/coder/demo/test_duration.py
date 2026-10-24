from duration import parse_duration


def test_single_units():
    assert parse_duration("45s") == 45
    assert parse_duration("2h") == 7200
    assert parse_duration("1m") == 60
    assert parse_duration("30s") == 30
    assert parse_duration("0s") == 0
    assert parse_duration("0h") == 0


def test_combined_units():
    assert parse_duration("1h30m") == 5400
    assert parse_duration("1h5m10s") == 4210
    assert parse_duration("0h0m0s") == 0


def test_whitespace_handling():
    assert parse_duration(" 1h ") == 3600
    assert parse_duration("  2h30m  ") == 9000


def test_empty_input():
    # Empty string → ValueError
    try:
        parse_duration("")
        assert False, "empty string should raise ValueError"
    except ValueError:
        pass

    # Whitespace-only → ValueError
    try:
        parse_duration("   ")
        assert False, "whitespace string should raise ValueError"
    except ValueError:
        pass

    # None → TypeError (not a str)
    try:
        parse_duration(None)
        assert False, "None should raise TypeError"
    except TypeError:
        pass


def test_malformed():
    for bad in ("1x", "h", "1h1h", "30m1h", "1h2m3s4", "abc", "1hh",
                "1h2m3", "1 2", "-1h", "1.5h"):
        try:
            parse_duration(bad)
            assert False, f"Should raise ValueError for {bad!r}"
        except ValueError:
            pass


def test_invalid_order():
    # m before h — not in h→m→s order
    with pytest.raises(ValueError):
        parse_duration("30m1h")

    # s before m — not in order
    with pytest.raises(ValueError):
        parse_duration("10s1m")


def test_repeated_unit():
    # Same unit twice
    with pytest.raises(ValueError):
        parse_duration("1h1h")
    with pytest.raises(ValueError):
        parse_duration("1h2h30m")
