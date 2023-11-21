from setuptools import setup

__version__ = "0.31.0"

# Default to PyQt6 if no other Qt binding is installed
qt_dependency = "PyQt6>=6.0"
qscintilla_dependency = "PyQt6-QScintilla"
try:
    import PyQt5
except ImportError:
    pass
else:
    qt_dependency = "PyQt5>=5.9"
    qscintilla_dependency = "QScintilla"

if __name__ == "__main__":
    setup(
        install_requires=[
            "pydantic",
            qt_dependency,
            qscintilla_dependency,
            "jedi",
            "qtpy",
            "pyqtgraph",
            "bec_lib",
            "zmq",
            "h5py",
            "pyqtdarktheme",
        ],
        extras_require={
            "dev": ["pytest", "pytest-random-order", "coverage", "pytest-qt", "black"],
            "pyqt5": ["PyQt5>=5.9"],
            "pyqt6": ["PyQt6>=6.0"],
        },
        version=__version__,
    )
