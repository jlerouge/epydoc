#
# rst.py: ReStructuredText support for epydoc
# Edward Loper
#
# Created [06/28/03 02:52 AM]
# $Id$
#

"""
Epydoc parser for ReStructuredText strings.  ReStructuredText is the
markup language used by the Docutils project.

This module defines a parser that converts ReStructuredText into an
XML/DOM representation (using L{docutils}).  The returned DOM tree
will conform to the following Document Type Description::

   <!ELEMENT html ((rawhtml | link)*, fieldlist?)>
   <!ELEMENT rawhtml (#PCDATA)>
   
   <!ELEMENT fieldlist (field+)>
   <!ELEMENT field (tag, arg?, html)>
   <!ELEMENT tag (#PCDATA)>
   <!ELEMENT arg (#PCDATA)>
   
   <!ELEMENT link    (name, target)>
   <!ELEMENT name    (#PCDATA)>
   <!ELEMENT target  (#PCDATA)>

This representation was chosen because it allows me to easily
integrate ReStructuredText output into epydoc, while still supporting
both crossreferences (marked with ReStructuredText interpreted text)
and fields (marked with ReStructuredText fields).

"""

# Imports
import re
from xml.dom.minidom import *
from docutils.core import publish_string
from docutils.writers.html4css1 import Writer as HTMLWriter
from docutils.writers.html4css1 import HTMLTranslator
from docutils.nodes import SkipChildren, SkipNode

def parse(docstring):
    """
    Parse the given docstring, which is formatted using
    ReStructuredText; and return an XML representation of its
    contents.  The returned string is primarily composed of C{rawhtml}
    elements, with C{link} elements embedded for ReStructuredText
    interpreted text (C{`...`}), and with C{field} elements to encode
    ReStructuredText fields.  See L{the module
    documentation<epydoc.rst>} for more information.

    @type docstring: C{string}
    @param docstring: The ReStructuredText docstring to parse.
    @rtype: L{xml.dom.minidom.Document}
    @return: An XML representation of C{docstring}'s contents.
    """
    writer = _EpydocWriter()
    publish_string(docstring, writer=writer)
    return writer.dom_document

class _EpydocWriter(HTMLWriter):
    """
    
    A simple writer class that uses an L{_EpydocTranslator} to produce
    an XML representation of a ReStructuredText, which can be used by
    epydoc to generate html output.

    C{_EpydocWriter} is I{not} meant to be used in the \"standard\"
    way with the docutils classes.  A typical writer would produce an
    output as a string.  However, since we want our output to be an
    XML tree, not a string, C{_EpydocWriter} generates its output as a
    side-effect.  In paricular, C{_EpydocWriter} returns an empty
    string; but the XML output can be accessed using the
    L{dom_document} instance variable, after the writer has finished
    processing the string.

    I'm sure that there's a more standard way to generate XML output;
    If someone who understands docutils better wants to rewrite this
    code, I'd be happy to accept patches.

    @type dom_document: C{xml.dom.minidom.Document}
    @ivar dom_document: An XML document encoding the contents of the
        most recently published string.
    """
    def __init__(self):
        HTMLWriter.__init__(self)
        self.translator_class = _EpydocTranslator
        self.dom_document = None

    def translate(self):
        visitor = self.translator_class(self.document)
        self.document.walkabout(visitor)
        self.dom_document = visitor.doc
        self.output = ''

class _EpydocTranslator(HTMLTranslator):
    """
    EpydocTranslator only makes a few changes to HTMLTranslator:

      - Interpreted text nodes are converted to XML DOM C{link}
        elements, instead of to html.
      - Fields are converted to XML DOM C{field} elements, and stored
        in the C{_fields} dictionary.
      - All HTML is post-processed by L{_fixup} to ensure that it
        doesn't conflict with epydoc.  In paritcular, local anchors
        are renamed, css classes are renamed, and headings are
        marked with css classes.
      - Once the entire document has been processed (in
        L{depart_document}), an XML DOM tree is generated to encode
        the entire document.  The body is assembled from the HTML
        strings and C{link} elements in the C{body} list; and the
        fields are copied from the C{_fields} dictionary.  The final
        result is stored in C{doc}
    
    @type doc: C{xml.dom.minidom.Document}
    @ivar doc: An XML document encoding the contents of the
        string that we're translating.
    @ivar _fields: A dictionary mapping from (tag, arg) to
        field contents.
    @ivar _body_stack: A stack containing saved body contents.
        When a field is entered, the current body contents are
        pushed onto this stack; and when the field is exited,
        they are popped back off.  This allows L{depart_field}
        to get access to the html text for the field's contents.
    """

    def __init__(self, document):
        HTMLTranslator.__init__(self, document)
        self._body_stack = []
        self._fields = []
        self.doc = Document()

    ##//////////////////////////////////////////////////
    ## DOM Assmbly
    ##//////////////////////////////////////////////////
    
    def visit_document(self, node): pass
    def depart_document(self, node):
        # Handle all fields
        if self._fields:
            fieldlist_elt = self.doc.createElement('fieldlist')
            self.body.append(fieldlist_elt)
            for (tag, arg, body) in self._fields:
                field_elt = self.doc.createElement('field')
                
                tag_elt = self.doc.createElement('tag')
                tag_elt.appendChild(self.doc.createTextNode(tag))
                field_elt.appendChild(tag_elt)
    
                if arg is not None:
                    arg_elt = self.doc.createElement('arg')
                    arg_elt.appendChild(self.doc.createTextNode(arg))
                    field_elt.appendChild(arg_elt)
    
                field_elt.appendChild(body)
                fieldlist_elt.appendChild(field_elt)
    
        # Construc the final dom tree
        self.doc.appendChild(self._body_to_dom(self.body))

    def _body_to_dom(self, body, parent=None):
        if parent is None:
            parent = self.doc.createElement('html')
        
        rawhtml_elt = None
        for elt in body:
            if type(elt) == type('') or type(elt) == type(u''):
                # Raw HTML
                if rawhtml_elt is None:
                    rawhtml_elt = self.doc.createElement('rawhtml')
                    parent.appendChild(rawhtml_elt)
                    rawhtml_elt.appendChild(self.doc.createTextNode(''))
                elt = self._fixup(elt)
                rawhtml_elt.childNodes[-1].data += elt
            elif isinstance(elt, xml.dom.minidom.Element):
                # Link or Field.
                rawhtml_elt = None
                parent.appendChild(elt)
            else:
                raise ValueError, ('Bad body element %r' % elt)
            
        return parent

    def _fixup(self, elt):
        """
        Post-process a piece of html that was generated by HTMLWriter,
        to ensure that it doesn't conflict with epydoc.  In
        particular, this adds a css class to headings, and prefixes
        existing css classes, names, and local hrefs with C{'rst-'}.
        """
        # Prefix all classes, names, and local hrefs with "rst-"
        elt = re.sub(r'(<[^>]+class=")([^"]+)', r'\1rst-\2', elt)
        elt = re.sub(r'(<[^>]+name=")([^"]+)', r'\1rst-\2', elt)
        elt = re.sub(r'(<[^>]+href="#)([^"]+)', r'\1rst-\2', elt)

        # Mark all headings with 'class="heading"'.
        elt = re.sub(r'<h(\d+)>', r'<h\1 class="heading">', elt)
        
        return elt
                
    ##//////////////////////////////////////////////////
    ## Interpreted Text
    ##//////////////////////////////////////////////////
    
    def visit_title_reference(self, node):
        # Get the target string.
        target_str = self.encode(node.astext())
        
        # Create the link DOM elt (name=target=target_str)
        link_elt = self.doc.createElement('link')
        name_elt = self.doc.createElement('name')
        name_elt.appendChild(self.doc.createTextNode(target_str))
        target_elt = self.doc.createElement('target')
        target_elt.appendChild(self.doc.createTextNode(target_str))
        link_elt.appendChild(name_elt)
        link_elt.appendChild(target_elt)

        # Add the link to the body.
        self.body.append(link_elt)

        raise SkipNode

    ##//////////////////////////////////////////////////
    ## Field Lists
    ##//////////////////////////////////////////////////
    
    # Field lists are handled entirely by visit_field & depart_field
    def visit_field_list(self, node): pass
    def visit_field_body(self, node): pass
    def depart_field_list(self, node): pass
    def depart_field_body(self, node): pass
    def visit_field_name(self, node): raise SkipNode

    def visit_field(self, node):
        self._body_stack.append(self.body)
        self.body = []
        
    def depart_field(self, node):
        name=node.children[0].astext().split(None, 1)
        tag = name[0]
        if len(name)>1: arg = name[1]
        else: arg = None
        
        self._fields.append( (tag, arg, self._body_to_dom(self.body)) )
        self.body = self._body_stack.pop()
        
def summary(epytext_doc):
    """
    Given a DOM document representing formatted documentation, return
    a new DOM document containing the documentation's first sentence.

    @param epytext_doc: A DOM document representing formatted
        documentation, as produced by L{parse}.
    @type epytext_doc: L{xml.dom.minidom.Document} or
        L{xml.dom.minidom.Element}
    @return: A DOM document containing the first sentence of the
        documentation.
    @rtype: L{xml.dom.minidom.Document}
    """
    doc = Document()
    html = doc.createElement('html')
    doc.appendChild(html)

    if isinstance(epytext_doc, Document):
        tree = epytext_doc.childNodes[0]
    else:
        tree = epytext_doc

    # Extract the raw text (no html tags)
    text = ''
    for child in tree.childNodes:
        if child.tagName == 'rawhtml':
            text += re.sub('<[^>]*>', '', child.childNodes[0].data)
        elif child.tagName == 'link':
            text += child.childNodes[0].childNodes[0].data

    # If we didn't find anything, return an empty document.
    if text == '': return doc

    # Extract the first sentence.
    m = re.match(r'^(\s*[\w\W]*?[\.:])(\s|$)', text)
    if m: text = m.group(1)

    # Return an element containing the text.
    rawhtml = doc.createElement('rawhtml')
    html.appendChild(rawhtml)
    rawhtml.appendChild(doc.createTextNode(text))
    return doc
