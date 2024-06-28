import pytest
from pydantic import ValidationError

from bec_widgets.utils import Colors
from bec_widgets.widgets.figure.plots.waveform.waveform_curve import CurveConfig


def test_color_validation_CSS():
    # Test valid color
    color = Colors.validate_color("teal")
    assert color == "teal"

    # Test invalid color
    with pytest.raises(ValidationError) as excinfo:
        CurveConfig(color="invalid_color")

    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == ("unsupported color")
    assert "The color must be a valid HEX string or CSS Color." in str(excinfo.value)


def test_color_validation_hex():
    # Test valid color
    color = Colors.validate_color("#ff0000")
    assert color == "#ff0000"

    # Test invalid color
    with pytest.raises(ValidationError) as excinfo:
        CurveConfig(color="#ff00000")

    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == ("unsupported color")
    assert "The color must be a valid HEX string or CSS Color." in str(excinfo.value)


def test_color_validation_RGBA():
    # Test valid color
    color = Colors.validate_color((255, 0, 0, 255))
    assert color == (255, 0, 0, 255)

    # Test invalid color
    with pytest.raises(ValidationError) as excinfo:
        CurveConfig(color=(255, 0, 0))

    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == ("unsupported color")
    assert "The color must be a tuple of 4 elements (R, G, B, A)." in str(excinfo.value)

    with pytest.raises(ValidationError) as excinfo:
        CurveConfig(color=(255, 0, 0, 355))

    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == ("unsupported color")
    assert "The color values must be between 0 and 255 in RGBA format (R,G,B,A)" in str(
        excinfo.value
    )


def test_hex_to_rgba():
    assert Colors.hex_to_rgba("#FF5733") == (255, 87, 51, 255)
    assert Colors.hex_to_rgba("#FF573380") == (255, 87, 51, 128)
    assert Colors.hex_to_rgba("#FF5733", 128) == (255, 87, 51, 128)

    with pytest.raises(ValueError):
        Colors.hex_to_rgba("#FF573")


def test_rgba_to_hex():
    assert Colors.rgba_to_hex(255, 87, 51, 255) == "#FF5733FF"
    assert Colors.rgba_to_hex(255, 87, 51, 128) == "#FF573380"
    assert Colors.rgba_to_hex(255, 87, 51) == "#FF5733FF"
