from setuptools import setup

__version__ = "0.21.0"

if __name__ == "__main__":
    setup(
        install_requires=["pyqt5", "pyqtgraph", "bec_lib"],
        extras_require={"dev": ["pytest", "pytest-random-order", "coverage", "pytest-qt", "black"]},
        version=__version__,
    )
