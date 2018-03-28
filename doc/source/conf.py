# -*- coding: utf-8 -*-
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath('../..'))
# -- General configuration ----------------------------------------------------

apidoc_module_dir = '../../networking_cisco'
apidoc_output_dir = 'contributor/api'
apidoc_excluded_paths = [
    "db/",
    "ml2_drivers/ncs",
    "ml2_drivers/n1kv",
    "plugins/cisco/db/l3/l3_router_appliance_db.py",
    "tests/unit/ml2_drivers/ncs",
    "tests/unit/ml2_drivers/n1kv"
]
apidoc_separate_modules = True

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    'sphinxcontrib.apidoc',
    'reno.sphinxext',
    'oslo_config.sphinxext',
    'oslo_config.sphinxconfiggen',
    #'sphinx.ext.intersphinx',
]

master_doc = 'index'

# autodoc generation is a bit aggressive and a nuisance when doing heavy
# text edit cycles.
# execute "export SPHINX_DEBUG=1" in your terminal to disable

# The suffix of source filenames.
source_suffix = '.rst'

# General information about the project.
project = u'networking-cisco'
copyright = u'2017, Cisco Systems, Inc'

# If true, '()' will be appended to :func: etc. cross-reference text.
add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
add_module_names = True

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# -- Options for HTML output --------------------------------------------------

# The theme to use for HTML and HTML Help pages.  Major themes that come with
# Sphinx are currently 'default' and 'sphinxdoc'.
# html_theme_path = ["."]
# html_theme = '_theme'
html_static_path = ['_static']

html_theme = "sphinx_rtd_theme"

# Output file base name for HTML help builder.
htmlhelp_basename = '%sdoc' % project

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass
# [howto/manual]).
latex_documents = [
    ('index',
     '%s.tex' % project,
     u'%s Documentation' % project,
     u'OpenStack Foundation', 'manual'),
]

# Example configuration for intersphinx: refer to the Python standard library.
#intersphinx_mapping = {'http://docs.python.org/': None}

# -- Options for oslo_config.sphinxconfiggen ---------------------------------

_config_generator_config_files = [
    'ml2_nexus.ini',
    'ml2_nexus_vxlan_type_driver.ini',
    'ml2_ucsm.ini'
]

def _get_config_generator_config_definition(config_file):
    config_file_path = '../../etc/oslo-config-generator/%s' % config_file
    # oslo_config.sphinxconfiggen appends '.conf.sample' to the filename,
    # strip file extentension (.conf or .ini).
    output_file_path = '_static/config-samples/%s' % config_file.rsplit('.', 1)[0]
    return (config_file_path, output_file_path)


config_generator_config_file = [
    _get_config_generator_config_definition(conf)
    for conf in _config_generator_config_files
]
