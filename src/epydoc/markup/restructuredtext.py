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


@todo: Implement to_plaintext.
@todo: Add to_latex??
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
from docutils.nodes import NodeVisitor, Text, SkipChildren, SkipNode
import docutils.nodes

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
            if isinstance(child, docutils.nodes.Text):
                m = re.match(r'(\s*[\w\W]*?\.)(\s|$)', child.data)
                if m:
                    summary_pieces.append(docutils.nodes.Text(m.group(1)))
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

    def visit_field(self, node):
        # Remove the field from the tree.
        node.parent.remove(node)

        # Extract the field name & optional argument
        tag = node.children[0].astext().split(None, 1)
        tagname = tag[0]
        if len(tag)>1: arg = tag[1]
        else: arg = None

        # Handle special fields:
        fbody = node.children[1].children
        if tagname.lower() == 'parameters' and arg is None:
            if self.handle_consolidated_field(fbody, 'param'):
                return
        if tagname.lower() == 'exceptions' and arg is None:
            if self.handle_consolidated_field(fbody, 'except'):
                return

        self._add_field(tagname, arg, fbody)

    def _add_field(self, tagname, arg, fbody):
        field_doc = self.document.copy()
        field_doc.children = fbody
        field_pdoc = ParsedRstDocstring(field_doc)
        self.fields.append(Field(tagname, arg, field_pdoc))
            
    def visit_field_list(self, node):
        # Remove the field list from the tree.  The visitor will still walk
        # over the node's children.
        node.parent.remove(node)

    def handle_consolidated_field(self, body, tagname):
        """
        Attempt to handle a consolidated :Parameters: section, which
        should contain a single list.  Any standard format for it??
        """
        # Check that it contains a bulleted list.
        if len(body) != 1 or body[0].tagname != 'bullet_list':
            print 'a'
            return 0

        # Check that each list item begins with interpreted text
        for item in body[0].children:
            if item.tagname != 'list_item': return 0
            if len(item.children) == 0: return 0
            if item.children[0].tagname != 'paragraph': return 0
            if len(item.children[0].children) == 0: return 0
            if item.children[0].children[0].tagname != 'title_reference':
                return 0

        # Everything looks good; convert to multiple :param: fields.
        for item in body[0].children:
            # Extract the arg
            arg = item.children[0].children[0].astext()

            # Extract the field body, and remove the arg
            fbody = item.children[:]
            fbody[0] = fbody[0].copy()
            fbody[0].children = item.children[0].children[1:]

            # Remove the separating ":", if present
            if (len(fbody[0].children) > 0 and
                isinstance(fbody[0].children[0], docutils.nodes.Text)):
                child = fbody[0].children[0]
                if child.data[:1] in ':-':
                    child.data = child.data[1:].lstrip()
                elif child.data[:2] == ' -':
                    child.data = child.data[2:].lstrip()

            # Wrap the field body, and add a new field
            self._add_field(tagname, arg, fbody)
        return 1
        
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

