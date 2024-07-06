import os
import sys

from PIL import Image, ImageChops
from qtpy.QtGui import QPixmap

import bec_widgets

REFERENCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(bec_widgets.__file__)), "tests/references"
)
REFERENCE_DIR_FAILURES = os.path.join(
    os.path.dirname(os.path.dirname(bec_widgets.__file__)), "tests/reference_failures"
)


def compare_images(image1_path: str, reference_image_path: str):
    """
    Load two images and compare them pixel by pixel

    Args:
        image1_path(str): The path to the first image
        reference_image_path(str): The path to the reference image

    Raises:
        ValueError: If the images are different
    """
    image1 = Image.open(image1_path)
    image2 = Image.open(reference_image_path)
    if image1.size != image2.size:
        raise ValueError("Image size has changed")
    diff = ImageChops.difference(image1, image2)
    if diff.getbbox():
        # copy image1 to the reference directory to upload as artifact
        os.makedirs(REFERENCE_DIR_FAILURES, exist_ok=True)
        image_name = os.path.join(REFERENCE_DIR_FAILURES, os.path.basename(image1_path))
        image1.save(image_name)
        print(f"Image saved to {image_name}")

        raise ValueError("Images are different")


def snap_and_compare(widget: any, output_directory: str, suffix: str = ""):
    """
    Save a rendering of a widget and compare it to a reference image

    Args:
        widget(any): The widget to render
        output_directory(str): The directory to save the image to
        suffix(str): A suffix to append to the image name

    Raises:
        ValueError: If the images are different

    Examples:
        snap_and_compare(widget, tmpdir, suffix="started")

    """

    if not isinstance(output_directory, str):
        output_directory = str(output_directory)

    os_suffix = sys.platform

    name = (
        f"{widget.__class__.__name__}_{suffix}_{os_suffix}.png"
        if suffix
        else f"{widget.__class__.__name__}_{os_suffix}.png"
    )

    # Save the widget to a pixmap
    test_image_path = os.path.join(output_directory, name)
    pixmap = QPixmap(widget.size())
    widget.render(pixmap)
    pixmap.save(test_image_path)

    try:
        reference_path = os.path.join(REFERENCE_DIR, f"{widget.__class__.__name__}")
        reference_image_path = os.path.join(reference_path, name)

        if not os.path.exists(reference_image_path):
            raise ValueError(f"Reference image not found: {reference_image_path}")

        compare_images(test_image_path, reference_image_path)

    except ValueError:
        image = Image.open(test_image_path)
        os.makedirs(REFERENCE_DIR_FAILURES, exist_ok=True)
        image_name = os.path.join(REFERENCE_DIR_FAILURES, name)
        image.save(image_name)
        print(f"Image saved to {image_name}")
        raise
