#
# javadoc.py: javadoc docstring parsing
# Edward Loper
#
# Created [07/03/03 12:37 PM]
# $Id$
#

"""
Epydoc parser for L{Javadoc<http://java.sun.com/j2se/javadoc/>}
docstrings.  Javadoc is an HTML-based markup language that was
developed for documenting Java APIs.  The returned DOM tree will
conform to the following Document Type Description::

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
integrate Javadoc output into epydoc, while still supporting both
crossreferences (marked with Javadoc C{{@link}}s) and fields (marked
with Javadoc C{@tags}).

@warning: This module does not exactly mimic Javadoc syntax.  In
particular, the syntax for some fields (such as C{@see}) is different;
and some fields (such as C{@value} and C{@docRoot}) are not
implemented.
@warning: Epydoc only supports HTML output for Javadoc docstrings.
"""
__docformat__ = 'epytext en'

# Imports
import re
from xml.dom.minidom import *

def parse(docstring, field_warnings):
    """
    Parse the given docstring, which is formatted using JavaDoc
    markup; and return an XML representation of its contents.  The
    returned string is primarily composed of C{rawhtml} elements, with
    C{link} elements embedded for Javadoc C{{@link}}s, and with
    C{field} elements to encode Javadoc tagged fields.  See L{the
    module documentation<epydoc.javadoc>} for more information.
    """
    doc = Document()
    html_elt = doc.createElement('html')
    doc.appendChild(html_elt)
    docstring = docstring.strip()
    if not docstring: return

    # Split the docstring into a description and a list of fields.
    (descr, fields) = _split_fields(docstring)

    # Add the description
    descr_elt = doc.createElement('rawhtml')
    html_elt.appendChild(descr_elt)
    _javadoc_to_dom(descr, html_elt, doc, field_warnings)

    # Add the fields
    if fields:
        fieldlist_elt = doc.createElement('fieldlist')
        html_elt.appendChild(fieldlist_elt)
        for (tag, arg, body) in fields:
            field_elt = doc.createElement('field')
            tag_elt = doc.createElement('tag')
            fieldlist_elt.appendChild(field_elt)
            field_elt.appendChild(tag_elt)
            tag_elt.appendChild(doc.createTextNode(tag))
            if arg is not None:
                arg_elt = doc.createElement('arg')
                field_elt.appendChild(arg_elt)
                arg_elt.appendChild(doc.createTextNode(arg))
            body_elt = doc.createElement('html')
            field_elt.appendChild(body_elt)
            _javadoc_to_dom(body, body_elt, doc, field_warnings)
    
    # Return the document
    return doc

# Which fields take arguments?
_ARG_FIELDS = ('group variable var type cvariable cvar ivariable '+
               'ivar return returns returntype rtype param parameter '+
               'arg argument raise raises exception except '+
               'deffield newfield').split()

_FIELD_RE = re.compile(r'(^\s*\@\w+[\s$])', re.MULTILINE)
def _split_fields(docstring):
    descr = None
    fields = []
    
    pieces = _FIELD_RE.split(docstring)
    descr = pieces[0]
    for i in range(1, len(pieces)):
        if i%2 == 1:
            tag = pieces[i].strip()[1:]
        else:
            if tag in _ARG_FIELDS:
                (arg, val) = pieces[i].strip().split(None, 1)
            else:
                (arg, val) = (None, pieces[i])
            fields.append((tag, arg, val))
    return (descr, fields)

_LINK_SPLIT_RE = re.compile(r'({@link(?:plain)? [^}]+})')
_LINK_RE = re.compile(r'{@link(?:plain)? ' + r'([^\s\(]+)' +
                      r'(?:\([^\)]*\))?' + r'(\s+.*)?' + r'}')

def _javadoc_to_dom(docstring, parent, doc, field_warnings):
    pieces = _LINK_SPLIT_RE.split(docstring)

    for i in range(len(pieces)):
        if i%2 == 0:
            rawhtml_elt = doc.createElement('rawhtml')
            parent.appendChild(rawhtml_elt)
            rawhtml_elt.appendChild(doc.createTextNode(pieces[i]))
        else:
            # Extract the name & the target.
            m = _LINK_RE.match(pieces[i])
            if m is None:
                field_warnings.append('Bad link: %r' % pieces[i])
                continue
            (target, name) = m.groups()
            if target[0] == '#': target = target[1:]
            target = target.replace('#', '.')
            target = re.sub(r'\(.*\)', '', target)
            if name is None: name = target
            else: name = name.strip()

            # Construct the link element
            link_elt = doc.createElement('link')
            name_elt = doc.createElement('name')
            target_elt = doc.createElement('target')
            parent.appendChild(link_elt)
            link_elt.appendChild(name_elt)
            link_elt.appendChild(target_elt)
            name_elt.appendChild(doc.createTextNode(name))
            target_elt.appendChild(doc.createTextNode(target))

