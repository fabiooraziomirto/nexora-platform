# Configuration for Sphinx documentation

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'sphinx.ext.intersphinx',
]

templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'

project = 'Nxr SDK'
copyright = '2024, Nxr Team'
author = 'Nxr Team'
version = '0.1.0'
release = '0.1.0'

language = 'en'
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
pygments_style = 'sphinx'

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'httpx': ('https://www.python-httpx.org/', None),
    'grpc': ('https://grpc.io/docs/languages/python/', None),
}

