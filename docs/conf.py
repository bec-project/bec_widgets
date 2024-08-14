# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import pathlib

import tomli

project = "BEC Widgets"
copyright = "2023, Paul Scherrer Institute"
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
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    # "sphinx.ext.coverage",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx_toolbox.collapse",
    "sphinx_copybutton",
    "myst_parser",
    "sphinx_design",
    "sphinx_inline_tabs",
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

autosummary_generate = True  # Turn on sphinx.ext.autosummary
add_module_names = False  # Remove namespaces from class/method signatures
autodoc_inherit_docstrings = True  # If no docstring, inherit from base class
set_type_checking_flag = True  # Enable 'expensive' imports for sphinx_autodoc_typehints
autoclass_content = "both"  # Include both class docstring and __init__
autodoc_mock_imports = ["pyqtgraph"]

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
