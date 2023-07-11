from setuptools import setup

__version__ = "0.0.0"

if __name__ == "__main__":
    setup(
        install_requires=[
            "pyqt5",
        ],
        extras_require={"dev": ["pytest", "pytest-random-order", "coverage", "pytest-qt"]},
        version=__version__,
    )
