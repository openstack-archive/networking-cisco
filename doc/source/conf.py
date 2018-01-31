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

on_rtd = os.environ.get('READTHEDOCS', None) == 'True'
if on_rtd and not os.path.isdir("contributor/api"):
    print("On Read the Docs and autodoc python module docs aren't built. "
          "Building...")
    os.environ['READTHEDOCS'] = 'False'
    os.environ['JUST_BUILD_AUTO_DOC'] = 'True'
    subprocess.check_call(
        [sys.executable, 'setup.py', 'build_sphinx', '-b', 'dummy'],
        cwd=os.path.join(os.path.dirname(__file__), os.path.pardir,
                         os.path.pardir),
    )
    os.environ['JUST_BUILD_AUTO_DOC'] = 'False'
    os.environ['READTHEDOCS'] = 'True'

ignore_everything = os.environ.get('JUST_BUILD_AUTO_DOC', None) == 'True'
if ignore_everything:
    master_doc = 'dummy'
    exclude_patterns = ['index.rst', '*/*']
else:
    # The master toctree document.
    master_doc = 'index'
    exclude_patterns = ['dummy.rst', 'api/networking_cisco_tempest_plugin.*']

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    'sphinx.ext.autodoc',
    'reno.sphinxext',
    'oslo_config.sphinxext',
    'oslo_config.sphinxconfiggen',
    #'sphinx.ext.intersphinx',
]

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
