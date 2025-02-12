import pyqtgraph as pg
import pytest
from pydantic import ValidationError
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.utils import Colors, ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import apply_theme
from bec_widgets.widgets.containers.figure.plots.waveform.waveform_curve import CurveConfig
from tests.unit_tests.client_mocks import mocked_client
from tests.unit_tests.conftest import create_widget


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


@pytest.mark.parametrize("num", [10, 100, 400])
def test_evenly_spaced_colors(num):
    colors_qcolor = Colors.evenly_spaced_colors(colormap="magma", num=num, format="QColor")
    colors_hex = Colors.evenly_spaced_colors(colormap="magma", num=num, format="HEX")
    colors_rgb = Colors.evenly_spaced_colors(colormap="magma", num=num, format="RGB")

    assert len(colors_qcolor) == num
    assert len(colors_hex) == num
    assert len(colors_rgb) == num

    assert all(isinstance(color, QColor) for color in colors_qcolor)
    assert all(isinstance(color, str) for color in colors_hex)
    assert all(isinstance(color, tuple) for color in colors_rgb)

    assert all(color.isValid() for color in colors_qcolor)
    assert all(color.startswith("#") for color in colors_hex)


@pytest.mark.parametrize("num", [10, 100, 400])
def test_golder_angle_colors(num):
    colors_qcolor = Colors.golden_angle_color(colormap="magma", num=num, format="QColor")
    colors_hex = Colors.golden_angle_color(colormap="magma", num=num, format="HEX")
    colors_rgb = Colors.golden_angle_color(colormap="magma", num=num, format="RGB")

    assert len(colors_qcolor) == num
    assert len(colors_hex) == num
    assert len(colors_rgb) == num

    assert all(isinstance(color, QColor) for color in colors_qcolor)
    assert all(isinstance(color, str) for color in colors_hex)
    assert all(isinstance(color, tuple) for color in colors_rgb)

    assert all(color.isValid() for color in colors_qcolor)
    assert all(color.startswith("#") for color in colors_hex)


##################################################
# Testing of the ExamplePlotWidget theme change
##################################################


class ExamplePlotWidget(BECWidget, QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        config: ConnectionConfig | None = None,
        client=None,
        gui_id: str | None = None,
    ) -> None:
        if config is None:
            config = ConnectionConfig(widget_class=self.__class__.__name__)
        super().__init__(client=client, gui_id=gui_id, config=config)
        QWidget.__init__(self, parent=parent)

        self.layout = QVBoxLayout(self)
        self.glw = pg.GraphicsLayoutWidget()
        self.pi = pg.PlotItem()

        self.layout.addWidget(self.glw)
        self.glw.addItem(self.pi)
        self.pi.plot([1, 2, 3, 4, 5], pen="r")


def test_apply_theme(qtbot, mocked_client):
    widget = create_widget(qtbot, ExamplePlotWidget, client=mocked_client)
    apply_theme("dark")

    # Get the default state of dark theme
    dark_bg = widget.glw.backgroundBrush().color().name()
    dark_axis_color = widget.pi.getAxis("left").pen().color().name()
    dark_label_color = widget.pi.getAxis("left").textPen().color().name()

    assert dark_bg == "#141414"
    assert dark_axis_color == "#cccccc"
    assert dark_label_color == "#ffffff"

    apply_theme("light")

    # Get the default state of light theme
    light_bg = widget.glw.backgroundBrush().color().name()
    light_axis_color = widget.pi.getAxis("left").pen().color().name()
    light_label_color = widget.pi.getAxis("left").textPen().color().name()

    assert light_bg == "#e9ecef"
    assert light_axis_color == "#666666"
    assert light_label_color == "#000000"
