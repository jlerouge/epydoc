#
# rst.py: ReStructuredText support for epydoc
# Edward Loper
#
# Created [06/28/03 02:52 AM]
# $Id$
#

"""
Epydoc parser for ReStructuredText strings.  ReStructuredText is the
standard markup language used by the Docutils project.


@todo: summary
@todo: to_plaintext, etc?
@warning: Epydoc only supports HTML output for ReStructuredText
docstrings.
"""
__docformat__ = 'epytext en'

# Imports
import re
from xml.dom.minidom import *

from docutils.core import publish_string
from docutils.writers import Writer
from docutils.writers.html4css1 import HTMLTranslator, Writer as HTMLWriter
from docutils.nodes import NodeVisitor, TextElement, SkipChildren, SkipNode

from epydoc.markup import *

def parse_docstring(docstring, errors):
    """
    Parse the given docstring, which is formatted using
    ReStructuredText; and return an XML representation of its
    contents.  The returned string is primarily composed of C{rawhtml}
    elements, with C{link} elements embedded for ReStructuredText
    interpreted text (C{`...`}), and with C{field} elements to encode
    ReStructuredText fields.  See L{the module
    documentation<epydoc.markup.restructuredtext>} for more information.

    @type docstring: C{string}
    @param docstring: The ReStructuredText docstring to parse.
    @rtype: L{xml.dom.minidom.Document}
    @return: An XML representation of C{docstring}'s contents.
    """
    writer = _DocumentPseudoWriter()
    writer.settings_spec = HTMLWriter.settings_spec
    publish_string(docstring, writer=writer)
    return ParsedRstDocstring(writer.document)
    
class ParsedRstDocstring(ParsedDocstring):
    def __init__(self, document):
        self._document = document

    def split_fields(self):
        visitor = _SplitFieldsTranslator(self._document)
        self._document.walk(visitor)
        return self, visitor.fields

    def summary(self):
        visitor = _SummaryExtractor(self._document)
        self._document.walk(visitor)
        return visitor.summary

    def to_html(self, docstring_linker, **options):
        visitor = _EpydocHTMLTranslator(self._document, docstring_linker)
        self._document.walkabout(visitor)
        return ''.join(visitor.body)

    def to_plaintext(self, docstring_linker, **options):
        raise NotImplementedError, 'ParsedDocstring.to_plaintext()'

    def __repr__(self): return '<ParsedRstDocstring: ...>'

class _DocumentPseudoWriter(Writer):
    """
    A pseudo-writer for the docutils framework, that can be used to
    access the document itself.  The output of C{_DocumentPseudoWriter}
    is just an empty string; but after it has been used, the most
    recently processed document is available as the instance variable
    C{document}

    @type document: L{docutils.nodes.document}
    @ivar document: The most recently processed document.
    """
    def __init__(self):
        self.document = None
        Writer.__init__(self)
        
    def translate(self):
        self.output = ''
        
class _SummaryExtractor(NodeVisitor):
    """
    A docutils node visitor that extracts the first sentence from
    the first paragraph in a document.
    """
    def __init__(self, document):
        NodeVisitor.__init__(self, document)
        self.summary = None
        
    def visit_document(self, node):
        self.summary = None
        
    def visit_paragraph(self, node):
        if self.summary is not None: return

        summary_pieces = []
        # Extract the first sentence.
        for child in node.children:
            if isinstance(child, Text):
                m = re.match(r'(\s*[\w\W]*?\.)(\s|$)', child.data)
                if m:
                    summary_pieces.append(Text(m.group(1)))
                    break
            summary_pieces.append(child)
            
        summary_doc = self.document.copy()
        summary_doc.children = summary_pieces
        self.summary = ParsedRstDocstring(summary_doc)

    def unknown_visit(self, node):
        'Ignore all unknown nodes'

class _SplitFieldsTranslator(NodeVisitor):
    """
    A docutils translator that removes all fields from a document, and
    collects them into the instance variable C{fields}

    @ivar fields: The fields of the most recently walked document.
    @type fields: C{list} of L{Field<markup.Field>}
    """
    def __init__(self, document):
        NodeVisitor.__init__(self, document)
        self.fields = []

    def visit_document(self, node):
        self.fields = []
        
    def visit_field_list(self, node):
        # Remove the field list from the tree.
        node.parent.remove(node)

        # Add each field to self.fields
        for field in node.children:
            # Extract the field name & optional argument
            tag = field.children[0].astext().split(None, 1)
            name = tag[0]
            if len(tag)>1: arg = name[1]
            else: arg = None

            # Extract the field body.
            body = self.document.copy()
            body.children = field.children[1].children
            body = ParsedRstDocstring(body)

            self.fields.append(Field(name, arg, body))
        
    def unknown_visit(self, node):
        'Ignore all unknown nodes'

class _EpydocHTMLTranslator(HTMLTranslator):
    def __init__(self, document, docstring_linker):
        HTMLTranslator.__init__(self, document)
        self._linker = docstring_linker

    # Handle interpreted text (crossreferences)
    def visit_title_reference(self, node):
        target = self.encode(node.astext())
        xref = self._linker.translate_identifier_xref(target, target)
        self.body.append(xref)
        raise SkipNode

    def visit_document(self, node): pass
    def depart_document(self, node): pass
        
    def starttag(self, node, tagname, suffix='\n', infix='', **attributes):
        """
        This modified version of starttag makes a few changes to HTML
        tags, to prevent them from conflicting with epydoc.  In particular:
          - existing class attributes are prefixed with C{'rst-'}
          - existing names are prefixed with C{'rst-'}
          - hrefs starting with C{'#'} are prefixed with C{'rst-'}
          - all headings (C{<hM{n}>}) are given the css class C{'heading'}
        """
        # Prefix all CSS classes with "rst-"
        if attributes.has_key('class'):
            attributes['class'] = 'rst-%s' % attributes['class']

        # Prefix all names with "rst-", to avoid conflicts
        if attributes.has_key('id'):
            attributes['id'] = 'rst-%s' % attributes['id']
        if attributes.has_key('name'):
            attributes['name'] = 'rst-%s' % attributes['name']
        if attributes.has_key('href') and attributes['href'][:1]=='#':
            attributes['href'] = '#rst-%s' % attributes['href'][1:]

        # For headings, use class="heading"
        if re.match(r'^h\d+$', tagname):
            attributes['class'] = 'heading'
        
        return HTMLTranslator.starttag(self, node, tagname, suffix,
                                       infix, **attributes)

