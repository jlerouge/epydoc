#
# javadoc.py: javadoc docstring parsing
# Edward Loper
#
# Created [07/03/03 12:37 PM]
# $Id$
#

"""
Epydoc parser for U{Javadoc<http://java.sun.com/j2se/javadoc/>}
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
from epydoc.markup import *

def parse_docstring(docstring, errors, **options):
    return ParsedJavadocDocstring(docstring)

class ParsedJavadocDocstring(ParsedDocstring):
    def __init__(self, docstring):
        self._docstring = docstring

    # Which fields take arguments?
    _ARG_FIELDS = ('group variable var type cvariable cvar ivariable '+
                   'ivar return returns returntype rtype param '+
                   'parameter arg argument raise raises exception '+
                   'except deffield newfield').split()
    _FIELD_RE = re.compile(r'(^\s*\@\w+[\s$])', re.MULTILINE)
    def split_fields(self, errors=None):
        descr = None
        fields = []
        
        pieces = self._FIELD_RE.split(self._docstring)
        descr = ParsedJavadocDocstring(pieces[0])
        for i in range(1, len(pieces)):
            if i%2 == 1:
                tag = pieces[i].strip()[1:]
            else:
                if tag in self._ARG_FIELDS:
                    (arg, body) = pieces[i].strip().split(None, 1)
                else:
                    (arg, body) = (None, pieces[i])
                fields.append(Field(tag, arg, ParsedJavadocDocstring(body)))
        return (descr, fields)

    _LINK_SPLIT_RE = re.compile(r'({@link(?:plain)? [^}]+})')
    _LINK_RE = re.compile(r'{@link(?:plain)? ' + r'([^\s\(]+)' +
                          r'(?:\([^\)]*\))?' + r'(\s+.*)?' + r'}')
    def to_html(self, docstring_linker, **options):
        html = ''
        pieces = _LINK_SPLIT_RE.split(self._docstring)
        for i in range(len(pieces)):
            if i%2 == 0:
                html += pieces[i]
            else:
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
                html += docstring_linker.translate_identifier_xref(target,
                                                                   name)
        return html

    def to_plaintext(self, docstring_linker, **options):
        return self._docstring

