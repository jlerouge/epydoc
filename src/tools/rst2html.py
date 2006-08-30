#!/usr/bin/python

r"""
A customized driver for converting docutils reStructuredText documents
into HTML.  This is used to generated HTML versions of the regression
files, for the webpage.
"""

# Docutils imports
from docutils.core import publish_cmdline, default_description
from docutils.writers.html4css1 import HTMLTranslator, Writer as HTMLWriter
import docutils.nodes

# Epydoc imports.  Make sure path contains the 'right' epydoc.
import sys
sys.path.insert(0, '../')
from epydoc.markup.doctest import doctest_to_html

class CustomizedHTMLWriter(HTMLWriter):
    settings_defaults = (HTMLWriter.settings_defaults or {}).copy()
    settings_defaults.update({
        'stylesheet': 'doctest.css',
        'stylesheet_path': None,
        'output_encoding': 'ascii',
        'output_encoding_error_handler': 'xmlcharrefreplace',
        })
        
    def __init__(self):
        HTMLWriter.__init__(self)
        self.translator_class = CustomizedHTMLTranslator

class CustomizedHTMLTranslator(HTMLTranslator):
    def visit_doctest_block(self, node):
        self.body.append(doctest_to_html(str(node[0])))
        raise docutils.nodes.SkipNode

description = ('Generates HTML documents from reStructuredText '
               'documents.  ' + default_description)
writer = CustomizedHTMLWriter()
docutils.core.publish_cmdline(writer=writer, description=description)
