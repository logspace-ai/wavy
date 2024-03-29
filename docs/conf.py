# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
import sys
from pathlib import Path

import toml

sys.path.append("../src/")


# -- Project information -----------------------------------------------------

project = "Wavy"
copyright = "2022, Logspace"
author = "Logspace"

# The full version, including alpha/beta/rc tags
path = Path(__file__).resolve().parents[1] / "pyproject.toml"
pyproject = toml.loads(open(str(path)).read())
version = pyproject["tool"]["poetry"]["version"]
release = version


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinxcontrib.napoleon",
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.todo",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.autosummary",
    "sphinx_automodapi.automodapi",
    "nbsphinx",
]
numpydoc_show_class_members = False

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "__init__.py"]

# cmd_line_template = "sphinx-apidoc --module-first -f -o {outputdir} {moduledir}"
# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# -- Options for todo extension ----------------------------------------------

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True

add_module_names = False
autodoc_member_order = "bysource"

autosummary_generate = False
autosummary_imported_members = False

autodoc_mock_imports = [
    "toml",
    "numpy",
    "pandas",
    "tqdm",
    "plotly",
    "plotlab",
    "tensorflow",
    "sklearn",
    "wavy.panel.deepcopy",
]

from sphinx_automodapi import automodsumm
from sphinx_automodapi.utils import find_mod_objs


def find_mod_objs_patched(*args, **kwargs):
    return find_mod_objs(args[0], onlylocals=True)


def patch_automodapi(app):
    """Monkey-patch the automodapi extension to exclude imported members"""
    automodsumm.find_mod_objs = find_mod_objs_patched


def setup(app):
    app.connect("builder-inited", patch_automodapi)
