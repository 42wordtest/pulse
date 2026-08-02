from pulse.regression import detect_availability_regression, AvailabilityWindow


def test_detects_an_availability_drop() -> None:
    recent = AvailabilityWindow(healthy_checks=95, total_checks=100)
    baseline = AvailabilityWindow(healthy_checks=100, total_checks=100)

    result = detect_availability_regression(recent, baseline)

    assert result is not None
    assert result.regressed is True
    assert result.drop_percentage_points == 5.0