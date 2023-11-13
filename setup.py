from setuptools import setup

__version__ = "0.31.0"

# Default to PyQt6 if no other Qt binding is installed
qt_dependency = "PyQt6>=6.0"
try:
    import PyQt5
except ImportError:
    try:
        import PySide2
    except ImportError:
        try:
            import PySide6
        except ImportError:
            pass
        else:
            qt_dependency = "PySide6>=6.0"
    else:
        qt_dependency = "PySide2>=5.9"
else:
    qt_dependency = "PyQt5>=5.9"

if __name__ == "__main__":
    setup(
        install_requires=["pydantic", qt_dependency, "qtpy", "pyqtgraph", "bec_lib", "zmq", "h5py"],
        extras_require={
            "dev": ["pytest", "pytest-random-order", "coverage", "pytest-qt", "black"],
            "pyqt5": ["PyQt5>=5.9"],
            "pyqt6": ["PyQt6>=6.0"],
            "pyside2": ["PySide2>=5.9"],
            "pyside6": ["PySide6>=6.0"],
        },
        version=__version__,
    )
