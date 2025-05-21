# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import datetime
import pathlib

import tomli

project = "BEC Widgets"
copyright = f"{datetime.datetime.today().year}, Paul Scherrer Institute"
author = "Paul Scherrer Institute"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

current_path = pathlib.Path(__file__).parent.parent.resolve()
version_path = f"{current_path}/pyproject.toml"


def get_version():
    """load the version from the version file"""
    with open(version_path, "r", encoding="utf-8") as file:
        res = tomli.loads(file.read())
    return res["project"]["version"]


release = get_version()

extensions = [
    # "sphinx.ext.coverage",
    "sphinx.ext.napoleon",
    "sphinx_toolbox.collapse",
    "sphinx_copybutton",
    "myst_parser",
    "sphinx_design",
    "sphinx_inline_tabs",
    "autoapi.extension",
    "sphinx.ext.viewcode",
]

myst_enable_extensions = [
    "amsmath",
    "attrs_inline",
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "html_admonition",
    "html_image",
    "replacements",
    "smartquotes",
    "strikethrough",
    "substitution",
    "tasklist",
]

# AutoAPI configuration
autoapi_dirs = ["../bec_widgets"]
autoapi_type = "python"
autoapi_generate_api_docs = True
autoapi_add_toctree_entry = False  # We'll control the toctree manually
autoapi_keep_files = False
autoapi_python_class_content = "both"  # Include both class docstring and __init__
autoapi_member_order = "groupwise"

add_module_names = False  # Remove namespaces from class/method signatures
autodoc_inherit_docstrings = True  # If no docstring, inherit from base class
set_type_checking_flag = True  # Enable 'expensive' imports for sphinx_autodoc_typehints
autoclass_content = "both"  # Include both class docstring and __init__
autodoc_mock_imports = ["pyqtgraph", "qtpy", "PySide6"]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

language = "Python"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "pydata_sphinx_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_logo = "../bec_widgets/assets/app_icons/bec_widgets_icon.png"


def skip_submodules(app, what, name, obj, skip, options):
    if what == "module":
        if not name.startswith("bec_widgets"):
            skip = True
        # print(f"Checking module: {name}")
        if "bec_widgets.widgets" in name:
            widget = name.split(".")[-2]
            submodule = name.split(".")[-1]
            if submodule in [f"register_{widget}", f"{widget}_plugin"]:
                # print(f"Skipping submodule: {name}")
                skip = True
    elif what in ["data", "attribute"]:
        obj_name = name.split(".")[-1]
        if obj_name.startswith("_") or obj_name in ["__all__", "logger", "bec_logger", "app"]:
            skip = True

    elif what == "class":
        class_name = name.split(".")[-1]
        if class_name.startswith("Demo"):
            skip = True
    return skip


def setup(app):
    app.connect("autoapi-skip-member", skip_submodules)
