from unittest import mock

import pyqtgraph as pg
import pytest

from bec_widgets.widgets.plots.image.image_base import ImageLayerManager
from bec_widgets.widgets.plots.image.image_item import ImageItem


@pytest.fixture()
def image_layer_manager():
    """Fixture to create an instance of ImageLayer."""
    layer = ImageLayerManager(parent=None, plot_item=mock.MagicMock(spec=pg.PlotItem))
    yield layer
    layer.clear()


def test_image_layer_manager_initialization(image_layer_manager):
    """Test the initialization of the ImageLayer."""
    assert isinstance(image_layer_manager, ImageLayerManager)
    assert image_layer_manager.plot_item is not None


def test_add_image_layer(image_layer_manager):
    """Test adding an image layer to the ImageLayerManager."""
    layer = image_layer_manager.add(name="Test Layer")
    assert layer.image.zValue() == 0

    layer2 = image_layer_manager.add(name="Test Layer 2")
    assert layer2.image.zValue() == 1

    layer3 = image_layer_manager.add(name="Test Layer 3", z_position="top")
    assert layer3.image.zValue() == 2

    layer4 = image_layer_manager.add(name="Test Layer 4", z_position="bottom")
    assert layer4.image.zValue() == -1


def test_remove_image_layer(image_layer_manager):
    """Test removing an image layer from the ImageLayerManager."""
    layer = image_layer_manager.add(name="Test Layer")
    assert len(image_layer_manager) == 1

    image_layer_manager.remove(layer)
    assert len(image_layer_manager) == 0


def test_clear_image_layers(image_layer_manager):
    """Test clearing all image layers from the ImageLayerManager."""
    layer = image_layer_manager.add(name="Test Layer")
    assert len(image_layer_manager) == 1

    image_layer_manager.clear()
    assert len(image_layer_manager) == 0


def test_image_layer_manager_getitem(image_layer_manager):
    """Test getting an image layer by index."""
    layer = image_layer_manager.add(name="Test Layer")
    assert image_layer_manager["Test Layer"] == layer

    with pytest.raises(TypeError):
        _ = image_layer_manager[1]

    image_layer_manager.remove("Test Layer")
    assert len(image_layer_manager) == 0


def test_image_layer_iteration(image_layer_manager):
    """Test iterating over image layers."""
    layer = image_layer_manager.add(name="Test Layer")
    assert list(image_layer_manager) == [layer]

    layer2 = image_layer_manager.add(name="Test Layer 2")
    assert list(image_layer_manager) == [layer, layer2]
