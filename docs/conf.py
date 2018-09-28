
import io
import re
import os
import sys


sys.path.insert(0, os.path.abspath('../'))

with io.open('../app/__init__.py', 'rt', encoding='utf8') as f:
    ver = re.search(r'__version__ = \'(.*?)\'', f.read()).group(1)


extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.autosummary',
    'sphinxcontrib.autohttp.flask',
    'sphinxcontrib.autohttp.flaskqref']

autosummary_generate = True
autodoc_default_flags = [':members:']
source_suffix = ['.rst']
master_doc = 'index'

show_authors = True
project = 'PushResume'
copyright = '2018'
author = 'Artem Ivashchenko, Vladimir Shabalin'

version = ver
release = ver

exclude_patterns = []
pygments_style = 'sphinx'
todo_include_todos = False

html_show_copyright = False
html_show_sourcelink = True
html_theme = 'sphinx_rtd_theme'
html_theme_options = {
    'collapse_navigation': False,
    'sticky_navigation': False,
    'navigation_depth': 3,
    'includehidden': False,
    'titles_only': False
}
html_sidebars = {'**': ['about.html', 'navigation.html', 'searchbox.html']}
htmlhelp_basename = 'pushresumedoc'
