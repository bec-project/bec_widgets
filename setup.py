# pylint: disable= missing-module-docstring
from setuptools import find_packages, setup

__version__ = "0.50.2"

# Default to PyQt6 if no other Qt binding is installed
QT_DEPENDENCY = "PyQt6>=6.7"

# pylint: disable=unused-import
try:
    import PyQt5
except ImportError:
    pass
else:
    QT_DEPENDENCY = "PyQt5>=5.9"

if __name__ == "__main__":
    setup(
        install_requires=[
            "pydantic",
            "qtconsole",
            QT_DEPENDENCY,
            "jedi",
            "qtpy",
            "pyqtgraph",
            "bec_lib",
            "zmq",
            "h5py",
            "pyqtdarktheme",
            "black",
        ],
        extras_require={
            "dev": [
                "pytest",
                "pytest-random-order",
                "pytest-timeout",
                "coverage",
                "pytest-qt",
                "black",
                "isort",
                "fakeredis",
            ],
            "pyqt5": ["PyQt5>=5.9"],
            "pyqt6": ["PyQt6>=6.7"],
        },
        version=__version__,
        packages=find_packages(),
        include_package_data=True,
        package_data={
            "": [
                "*.ui",
                "*.yaml",
                "*.png",
            ]
        },
    )
