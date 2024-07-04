import os
import sys

import pytest
import qdarktheme
from PIL import Image, ImageChops
from qtpy.QtGui import QPixmap

from bec_widgets.widgets.spinner.spinner import SpinnerWidget


@pytest.fixture
def spinner_widget(qtbot):
    qdarktheme.setup_theme("light")
    spinner = SpinnerWidget()
    qtbot.addWidget(spinner)
    qtbot.waitExposed(spinner)
    yield spinner


def save_pixmap(widget, filename):
    pixmap = QPixmap(widget.size())
    widget.render(pixmap)
    pixmap.save(str(filename))
    return pixmap


def compare_images(image1_path: str, reference_image_path: str):
    image1 = Image.open(image1_path)
    image2 = Image.open(reference_image_path)
    if image1.size != image2.size:
        raise ValueError("Image size has changed")
    diff = ImageChops.difference(image1, image2)
    if diff.getbbox():
        # copy image1 to the reference directory to upload as artifact
        output_dir = os.path.join(os.path.dirname(__file__), "reference_failures")
        os.makedirs(output_dir, exist_ok=True)
        image_name = os.path.join(output_dir, os.path.basename(image1_path))
        image1.save(image_name)
        print(f"Image saved to {image_name}")

        raise ValueError("Images are different")


def test_spinner_widget_paint_event(spinner_widget, qtbot):
    spinner_widget.paintEvent(None)


def snap_and_compare(widget, tmpdir, suffix=""):
    os_suffix = sys.platform

    name = (
        f"{widget.__class__.__name__}_{suffix}_{os_suffix}.png"
        if suffix
        else f"{widget.__class__.__name__}_{os_suffix}.png"
    )

    # Save the widget to a pixmap
    test_image_path = str(tmpdir / name)
    pixmap = QPixmap(widget.size())
    widget.render(pixmap)
    pixmap.save(test_image_path)

    try:
        references_path = os.path.join(os.path.dirname(__file__), "references")
        reference_image_path = os.path.join(references_path, name)

        if not os.path.exists(reference_image_path):
            raise ValueError(f"Reference image not found: {reference_image_path}")

        compare_images(test_image_path, reference_image_path)

    except ValueError:
        image = Image.open(test_image_path)
        output_dir = os.path.join(os.path.dirname(__file__), "reference_failures")
        os.makedirs(output_dir, exist_ok=True)
        image_name = os.path.join(output_dir, name)
        image.save(image_name)
        print(f"Image saved to {image_name}")
        raise


def test_spinner_widget_rendered(spinner_widget, qtbot, tmpdir):
    spinner_widget.update()
    qtbot.wait(200)
    snap_and_compare(spinner_widget, tmpdir, suffix="")

    spinner_widget._started = True
    spinner_widget.update()
    qtbot.wait(200)

    snap_and_compare(spinner_widget, tmpdir, suffix="started")
