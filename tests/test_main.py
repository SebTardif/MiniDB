"""Demo output formatting."""

from main import _cell


def test_finite_float_hides_binary_dust():
    """89.97 + 49.95 prints as 139.92, and a whole float stays compact."""
    assert _cell(89.97 + 49.95) == '139.92'
    assert _cell(75000.0) == '75000'


def test_non_finite_float_is_not_rewritten():
    """NaN and infinities stay readable. Other types are unchanged."""
    assert _cell(float('nan')) == 'nan'
    assert _cell(float('inf')) == 'inf'
    assert _cell(float('-inf')) == '-inf'
    assert _cell(1) == '1'
    assert _cell(True) == 'True'
    assert _cell(None) == 'None'
