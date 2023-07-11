from setuptools import setup

__version__ = "0.1.0"

if __name__ == "__main__":
    setup(
        install_requires=[
            "pyqt5",
            "pyqtgraph",
        ],
        extras_require={"dev": ["pytest", "pytest-random-order", "coverage", "pytest-qt"]},
        version=__version__,
    )
