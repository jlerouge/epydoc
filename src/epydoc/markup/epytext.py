#
# epytext.py: epydoc formatted docstring parsing
# Edward Loper
#
# Created [04/10/01 12:00 AM]
# $Id$
#

"""
Parser for epytext strings.  Epytext is a lightweight markup whose
primary intended application is Python documentation strings.  This
parser converts Epytext strings to a XML/DOM representation.  Epytext
strings can contain the following X{structural blocks}:

    - X{epytext}: The top-level element of the DOM tree.
    - X{para}: A paragraph of text.  Paragraphs contain no newlines, 
      and all spaces are soft.
    - X{section}: A section or subsection.
    - X{field}: A tagged field.  These fields provide information
      about specific aspects of a Python object, such as the
      description of a function's parameter, or the author of a
      module.
    - X{literalblock}: A block of literal text.  This text should be
      displayed as it would be displayed in plaintext.  The
      parser removes the appropriate amount of leading whitespace 
      from each line in the literal block.
    - X{doctestblock}: A block containing sample python code,
      formatted according to the specifications of the C{doctest}
      module.
    - X{ulist}: An unordered list.
    - X{olist}: An ordered list.
    - X{li}: A list item.  This tag is used both for unordered list
      items and for ordered list items.

Additionally, the following X{inline regions} may be used within
C{para} blocks:
    
    - X{code}:   Source code and identifiers.
    - X{math}:   Mathematical expressions.
    - X{index}:  A term which should be included in an index, if one
                 is generated.
    - X{italic}: Italicized text.
    - X{bold}:   Bold-faced text.
    - X{uri}:    A Universal Resource Indicator (URI) or Universal
                 Resource Locator (URL)
    - X{link}:   A Python identifier which should be hyperlinked to
                 the named object's documentation, when possible.

The returned DOM tree will confirm to the the following Document Type
Description::

   <!ENTITY % colorized '(code | math | index | italic |
                          bold | uri | link)*'>

   <!ELEMENT epytext ((para | literalblock | doctestblock |
                      section | ulist | olist)*, fieldlist?)>

   <!ELEMENT para (#PCDATA | %colorized;)*>

   <!ELEMENT section (para | listblock | doctestblock |
                      section | ulist | olist)+>

   <!ELEMENT fieldlist (field+)>
   <!ELEMENT field (tag, (para | listblock | doctestblock)
                          ulist | olist)+)>
   <!ELEMENT tag (#PCDATA)>
   
   <!ELEMENT literalblock (#PCDATA)>
   <!ELEMENT doctestblock (#PCDATA)>

   <!ELEMENT ulist (li+)>
   <!ELEMENT olist (li+)>
   <!ELEMENT li (para | literalblock | doctestblock | ulist | olist)+>
   <!ATTLIST li bullet NMTOKEN #IMPLIED>
   <!ATTLIST olist start NMTOKEN #IMPLIED>

   <!ELEMENT uri     (name, target)>
   <!ELEMENT link    (name, target)>
   <!ELEMENT name    (#PCDATA | %colorized;)*>
   <!ELEMENT target  (#PCDATA)>
   
   <!ELEMENT code    (#PCDATA | %colorized;)*>
   <!ELEMENT math    (#PCDATA | %colorized;)*>
   <!ELEMENT italic  (#PCDATA | %colorized;)*>
   <!ELEMENT bold    (#PCDATA | %colorized;)*>
   <!ELEMENT indexed (#PCDATA | %colorized;)>

@var SCRWIDTH: The default width with which text will be wrapped
      when formatting the output of the parser.
@type SCRWIDTH: C{int}
"""
__docformat__ = 'epytext en'

# Code organization..
#   1. parse()
#   2. tokenize()
#   3. colorize()
#   4. helpers
#   5. testing

import re, epydoc.uid, string, types, sys
from xml.dom.minidom import Document, Text

##################################################
## Constants
##################################################

# Default screen width, for word-wrapping
SCRWIDTH = 73

# The possible heading underline characters, listed in order of
# heading depth. 
_HEADING_CHARS = "=-~"

# Escape codes.  These should be needed very rarely.
_ESCAPES = {'lb':'{', 'rb': '}'}

# Tags for colorizing text.
_COLORIZING_TAGS = {
    'C': 'code',
    'M': 'math',
    'X': 'indexed',
    'I': 'italic', 
    'B': 'bold',
    'U': 'uri',
    'L': 'link',       # A Python identifier that should be linked to 
    'E': 'escape',     # "escape" is a special tag.
    }

# Which tags can use "link syntax" (e.g., U{Python<www.python.org>})?
_LINK_COLORIZING_TAGS = ['link', 'uri']

##################################################
## Structuring (Top Level)
##################################################

def parse(str, errors = None, warnings = None):
    """
    Return a DOM tree encoding the contents of an epytext string.
    Any errors or warnings generated during parsing will be stored in
    the C{errors} and C{warnings} parameters.

    @param str: The epytext string to parse.
    @type str: C{string}

    @param errors: A list where any errors generated during parsing
        will be stored.  If no list is specified, then errors will 
        generate exceptions.
    @type errors: C{list} of L{ParseError}

    @param warnings: A list where any warnings generated during parsing 
        will be stored.  If no list is specified, then warnings will
        be silently ignored.
    @type warnings: C{list} of L{ParseError}

    @return: a DOM tree encoding the contents of an epytext string.
    @rtype: L{xml.dom.minidom.Document}
    
    @raise ParseError: If C{errors} is C{None} and an error is
        encountered while parsing.

    @see: L{xml.dom.minidom.Document}
    """
    # Initialize warning and error lists.
    if warnings == None: warnings = []
    if errors == None:
        errors = []
        raise_on_error = 1
    else:
        raise_on_error = 0

    # Preprocess the string.
    str = re.sub('\015\012', '\012', str)
    str = string.expandtabs(str)

    # Tokenize the input string.
    tokens = _tokenize(str, warnings, errors)

    # Have we encountered a field yet?
    encountered_field = 0

    # Create an XML document to hold the epytext.
    doc = Document()

    # Maintain two parallel stacks: one contains DOM elements, and
    # gives the ancestors of the current block.  The other contains
    # indentation values, and gives the indentation of the
    # corresponding DOM elements.  An indentation of "None" reflects
    # an unknown indentation.  However, the indentation must be
    # greater than, or greater than or equal to, the indentation of
    # the prior element (depending on what type of DOM element it
    # corresponds to).  No 2 consecutive indent_stack values will be
    # ever be "None."  Use initial dummy elements in the stack, so we
    # don't have to worry about bounds checking.
    stack = [None, doc.createElement('epytext')]
    indent_stack = [-1, None]

    for token in tokens:
        # Uncomment these for debugging:
        #print ''.join(['%11s' % (t and t.tagName) for t in stack]),':',token.tag
        #print ''.join(['%11s' % i for i in indent_stack]),':',token.indent
        
        # Pop any completed blocks off the stack.
        _pop_completed_blocks(token, stack, indent_stack)

        # If Token has type PARA, colorize and add the new paragraph
        if token.tag == Token.PARA:
            _add_para(doc, token, stack, indent_stack, errors, warnings)
                     
        # If Token has type HEADING, add the new section
        elif token.tag == Token.HEADING:
            _add_section(doc, token, stack, indent_stack, errors, warnings)

        # If Token has type LBLOCK, add the new literal block
        elif token.tag == Token.LBLOCK:
            stack[-1].appendChild(token.to_dom(doc))

        # If Token has type DTBLOCK, add the new doctest block
        elif token.tag == Token.DTBLOCK:
            stack[-1].appendChild(token.to_dom(doc))

        # If Token has type BULLET, add the new list/list item/field
        elif token.tag == Token.BULLET:
            _add_list(doc, token, stack, indent_stack, errors, warnings)
        else:
            assert 0, 'Unknown token type: '+token.tag

        # Check if the DOM element we just added was a field..
        if stack[-1].tagName == 'field':
            encountered_field = 1
        elif encountered_field == 1:
            if len(stack) <= 3:
                estr = ("Fields must be the final elements in an "+
                        "epytext string.")
                errors.append(StructuringError(estr, token))

    # If there was an error, then signal it!
    if errors != []:
        if raise_on_error:
            raise errors[0]
        else:
            return None
        
    # Return the top-level epytext DOM element.
    doc.appendChild(stack[1])
    return doc

def _pop_completed_blocks(token, stack, indent_stack):
    """
    Pop any completed blocks off the stack.  This includes any
    blocks that we have dedented past, as well as any list item
    blocks that we've dedented to.  The top element on the stack 
    should only be a list if we're about to start a new list
    item (i.e., if the next token is a bullet).
    """
    indent = token.indent
    if indent != None:
        while (len(stack) > 2):
            pop = 0
            
            # Dedent past a block
            if indent_stack[-1]!=None and indent<indent_stack[-1]: pop=1
            elif indent_stack[-1]==None and indent<indent_stack[-2]: pop=1

            # Dedent to a list item, if it is follwed by another list
            # item with the same indentation.
            elif (token.tag == 'bullet' and indent==indent_stack[-2] and 
                  stack[-1].tagName in ('li', 'field')): pop=1

            # End of a list (no more list items available)
            elif (stack[-1].tagName in ('ulist', 'olist') and
                  (token.tag != 'bullet' or token.contents[-1] == ':')):
                pop=1

            # Pop the block, if it's complete.  Otherwise, we're done.
            if pop == 0: return
            stack.pop()
            indent_stack.pop()

def _add_para(doc, para_token, stack, indent_stack, errors, warnings):
    """Colorize the given paragraph, and add it to the DOM tree."""
    # Check indentation, and update the parent's indentation
    # when appropriate.
    if indent_stack[-1] == None:
        indent_stack[-1] = para_token.indent
    if para_token.indent == indent_stack[-1]:
        # Colorize the paragraph and add it.
        para = _colorize(doc, para_token, errors, warnings)
        stack[-1].appendChild(para)
    else:
        estr = "Improper paragraph indentation."
        errors.append(StructuringError(estr, para_token))

def _add_section(doc, heading_token, stack, indent_stack, errors, warnings):
    """Add a new section to the DOM tree, with the given heading."""
    if indent_stack[-1] == None:
        indent_stack[-1] = heading_token.indent
    elif indent_stack[-1] != heading_token.indent:
        estr = "Improper heading indentation."
        errors.append(StructuringError(estr, heading_token))

    # Check for errors.
    for tok in stack[2:]:
        if tok.tagName != "section":
            estr = "Headings must occur at the top level."
            errors.append(StructuringError(estr, heading_token))
            break
    if (heading_token.level+2) > len(stack):
        estr = "Wrong underline character for heading."
        errors.append(StructuringError(estr, heading_token))

    # Pop the appropriate number of headings so we're at the
    # correct level.
    stack[heading_token.level+2:] = []
    indent_stack[heading_token.level+2:] = []

    # Colorize the heading
    head = _colorize(doc, heading_token, errors, warnings, 'heading')

    # Add the section's and heading's DOM elements.
    sec = doc.createElement("section")
    stack[-1].appendChild(sec)
    stack.append(sec)
    sec.appendChild(head)
    indent_stack.append(None)
        
def _add_list(doc, bullet_token, stack, indent_stack, errors, warnings):
    """
    Add a new list item or field to the DOM tree, with the given
    bullet or field tag.  When necessary, create the associated
    list.
    """
    # Determine what type of bullet it is.
    if bullet_token.contents[-1] == '-':
        list_type = 'ulist'
    elif bullet_token.contents[-1] == '.':
        list_type = 'olist'
    elif bullet_token.contents[-1] == ':':
        list_type = 'fieldlist'
    else:
        raise AssertionError('Bad Bullet: %r' % bullet_token.contents)

    # Is this a new list?
    newlist = 0
    if stack[-1].tagName != list_type:
        newlist = 1
    elif list_type == 'olist' and stack[-1].tagName == 'olist':
        old_listitem = stack[-1].childNodes[-1]
        old_bullet = old_listitem.getAttribute("bullet").split('.')[:-1]
        new_bullet = bullet_token.contents.split('.')[:-1]
        if (new_bullet[:-1] != old_bullet[:-1] or
            int(new_bullet[-1]) != int(old_bullet[-1])+1):
            newlist = 1

    # Create the new list.
    if newlist:
        if stack[-1].tagName in ('ulist', 'olist', 'fieldlist'):
            stack.pop()
            indent_stack.pop()

        if (list_type != 'fieldlist' and indent_stack[-1] is not None and
            bullet_token.indent == indent_stack[-1]):
            # Ignore this error if there's text on the same line as
            # the comment-opening quote -- epydoc can't reliably
            # determine the indentation for that line.
            if bullet_token.startline != 1 or bullet_token.indent != 0:
                estr = "Lists must be indented."
                errors.append(StructuringError(estr, bullet_token))

        if list_type == 'fieldlist':
            # Fieldlist should be at the top-level.
            for tok in stack[2:]:
                if tok.tagName != "section":
                    estr = "Fields must be at the top level."
                    errors.append(StructuringError(estr, bullet_token))
                    break
            stack[2:] = []
            indent_stack[2:] = []

        # Add the new list.
        lst = doc.createElement(list_type)
        stack[-1].appendChild(lst)
        stack.append(lst)
        indent_stack.append(bullet_token.indent)
        if list_type == 'olist':
            start = bullet_token.contents.split('.')[:-1]
            if start != '1':
                lst.setAttribute("start", start[-1])

    # Fields are treated somewhat specially: A "fieldlist"
    # node is created to make the parsing simpler, but fields
    # are adjoined directly into the "epytext" node, not into
    # the "fieldlist" node.
    if list_type == 'fieldlist':
        li = doc.createElement("field")
        tagwords = bullet_token.contents[1:-1].split()
        assert 0 < len(tagwords) < 3, "Bad field tag"
        tag = doc.createElement("tag")
        tag.appendChild(doc.createTextNode(tagwords[0]))
        li.appendChild(tag)
        if len(tagwords) > 1:
            arg = doc.createElement("arg")
            arg.appendChild(doc.createTextNode(tagwords[1]))
            li.appendChild(arg)
    else:
        li = doc.createElement("li")
        if list_type == 'olist':
            li.setAttribute("bullet", bullet_token.contents)

    # Add the bullet.
    stack[-1].appendChild(li)
    stack.append(li)
    indent_stack.append(None)

        
##################################################
## Tokenization
##################################################

class Token:
    """
    C{Token}s are an intermediate data structure used while
    constructing the structuring DOM tree for a formatted docstring.
    There are five types of C{Token}:
    
        - Paragraphs
        - Literal blocks
        - Doctest blocks
        - Headings
        - Bullets

    The text contained in each C{Token} is stored in the
    C{contents} variable.  The string in this variable has been
    normalized.  For paragraphs, this means that it has been converted 
    into a single line of text, with newline/indentation replaced by
    single spaces.  For literal blocks and doctest blocks, this means
    that the appropriate amount of leading whitespace has been removed 
    from each line.

    Each C{Token} has an indentation level associated with it,
    stored in the C{indent} variable.  This indentation level is used
    by the structuring procedure to assemble hierarchical blocks.

    @type tag: C{string}
    @ivar tag: This C{Token}'s type.  Possible values are C{Token.PARA} 
        (paragraph), C{Token.LBLOCK} (literal block), C{Token.DTBLOCK}
        (doctest block), C{Token.HEADINGC}, and C{Token.BULLETC}.
        
    @type startline: C{int}
    @ivar startline: The line on which this C{Token} begins.  This 
        line number is only used for issuing warnings and errors.

    @type contents: C{string}
    @ivar contents: The normalized text contained in this C{Token}.
    
    @type indent: C{int} or C{None}
    @ivar indent: The indentation level of this C{Token} (in
        number of leading spaces).  A value of C{None} indicates an
        unknown indentation; this is used for list items and fields
        that begin with one-line paragraphs.
        
    @type level: C{int} or C{None}
    @ivar level: The heading-level of this C{Token} if it is a
        heading; C{None}, otherwise.  Valid heading levels are 0, 1,
        and 2.

    @type PARA: C{string}
    @cvar PARA: The C{tag} value for paragraph C{Token}s.
    @type LBLOCK: C{string}
    @cvar LBLOCK: The C{tag} value for literal C{Token}s.
    @type DTBLOCK: C{string}
    @cvar DTBLOCK: The C{tag} value for doctest C{Token}s.
    @type HEADING: C{string}
    @cvar HEADING: The C{tag} value for heading C{Token}s.
    @type BULLET: C{string}
    @cvar BULLET: The C{tag} value for bullet C{Token}s.  This C{tag}
        value is also used for field tag C{Token}s, since fields
        function syntactically the same as list items.
    """
    # The possible token types.
    PARA = "para"
    LBLOCK = "literalblock"
    DTBLOCK = "doctestblock"
    HEADING = "heading"
    BULLET = "bullet"

    def __init__(self, tag, startline, contents, indent, level=None):
        """
        Create a new C{Token}.

        @param tag: The type of the new C{Token}.
        @type tag: C{string}
        @param startline: The line on which the new C{Token} begins.
        @type startline: C{int}
        @param contents: The normalized contents of the new C{Token}.
        @type contents: C{string}
        @param indent: The indentation of the new C{Token} (in number
            of leading spaces).  A value of C{None} indicates an
            unknown indentation.
        @type indent: C{int} or C{None}
        @param level: The heading-level of this C{Token} if it is a
            heading; C{None}, otherwise.
        @type level: C{int} or C{None}
        """
        self.tag = tag
        self.startline = startline
        self.contents = contents
        self.indent = indent
        self.level = level

    def __repr__(self):
        """
        @rtype: C{string}
        @return: the formal representation of this C{Token}.
            C{Token}s have formal representaitons of the form:: 
                <Token: para at line 12>
        """
        return '<Token: %s at line %s>' % (self.tag, self.startline)

    def to_dom(self, doc):
        """
        @return: a DOM representation of this C{Token}.
        @rtype: L{xml.dom.minidom.Element}
        """
        e = doc.createElement(self.tag)
        e.appendChild(doc.createTextNode(self.contents))
        return e

# Construct regular expressions for recognizing bullets.  These are
# global so they don't have to be reconstructed each time we tokenize
# a docstring.
_ULIST_BULLET = '[-]( +|$)'
_OLIST_BULLET = '(\d+[.])+( +|$)'
_FIELD_BULLET = '@\w+( +[\w\.]+)?:( +|$)'
_BULLET_RE = re.compile(_ULIST_BULLET + '|' +
                        _OLIST_BULLET + '|' +
                        _FIELD_BULLET)
_LIST_BULLET_RE = re.compile(_ULIST_BULLET + '|' + _OLIST_BULLET)
_FIELD_BULLET_RE = re.compile(_FIELD_BULLET)
del _ULIST_BULLET, _OLIST_BULLET, _FIELD_BULLET

def _tokenize_doctest(lines, start, block_indent, tokens, errors):
    """
    Construct a L{Token} containing the doctest block starting at
    C{lines[start]}, and append it to C{tokens}.  C{block_indent}
    should be the indentation of the doctest block.  Any warnings
    generated while tokenizing the doctest block will be appended to
    C{warnings}.

    @param lines: The list of lines to be tokenized
    @param start: The index into C{lines} of the first line of the
        doctest block to be tokenized.
    @param block_indent: The indentation of C{lines[start]}.  This is
        the indentation of the doctest block.
    @param errors: A list where any errors generated during parsing
        will be stored.  If no list is specified, then errors will 
        generate exceptions.
    @return: The line number of the first line following the doctest
        block.
        
    @type lines: C{list} of C{string}
    @type start: C{int}
    @type block_indent: C{int}
    @type tokens: C{list} of L{Token}
    @type errors: C{list} of L{ParseError}
    @rtype: C{int}
    """
    # If they dedent past block_indent, keep track of the minimum
    # indentation.  This is used when removing leading indentation
    # from the lines of the doctest block.
    min_indent = block_indent

    linenum = start + 1
    while linenum < len(lines):
        # Find the indentation of this line.
        line = lines[linenum]
        indent = len(line) - len(line.lstrip())
        
        # A blank line ends doctest block.
        if indent == len(line): break
        
        # A Dedent past block_indent gives a warning.
        if indent < block_indent:
            min_indent = min(min_indent, indent)
            estr = 'Improper doctest block indentation.'
            errors.append(TokenizationError(estr, linenum, line))

        # Go on to the next line.
        linenum += 1

    # Add the token, and return the linenum after the token ends.
    contents = [line[min_indent:] for line in lines[start:linenum]]
    contents = '\n'.join(contents)
    tokens.append(Token(Token.DTBLOCK, start, contents, block_indent))
    return linenum

def _tokenize_literal(lines, start, block_indent, tokens, warnings):
    """
    Construct a L{Token} containing the literal block starting at
    C{lines[start]}, and append it to C{tokens}.  C{block_indent}
    should be the indentation of the literal block.  Any warnings
    generated while tokenizing the literal block will be appended to
    C{warnings}.

    @param lines: The list of lines to be tokenized
    @param start: The index into C{lines} of the first line of the
        literal block to be tokenized.
    @param block_indent: The indentation of C{lines[start]}.  This is
        the indentation of the literal block.
    @param warnings: A list of the warnings generated by parsing.  Any
        new warnings generated while will tokenizing this paragraph
        will be appended to this list.
    @return: The line number of the first line following the literal
        block. 
        
    @type lines: C{list} of C{string}
    @type start: C{int}
    @type block_indent: C{int}
    @type tokens: C{list} of L{Token}
    @type warnings: C{list} of L{ParseError}
    @rtype: C{int}
    """
    linenum = start + 1
    while linenum < len(lines):
        # Find the indentation of this line.
        line = lines[linenum]
        indent = len(line) - len(line.lstrip())

        # A Dedent to block_indent ends the literal block.
        # (Ignore blank likes, though)
        if len(line) != indent and indent <= block_indent:
            break
        
        # Go on to the next line.
        linenum += 1

    # Add the token, and return the linenum after the token ends.
    contents = [line[block_indent+1:] for line in lines[start:linenum]]
    contents = '\n'.join(contents)
    contents = re.sub('(\A[ \n]*\n)|(\n[ \n]*\Z)', '', contents)
    tokens.append(Token(Token.LBLOCK, start, contents, block_indent))
    return linenum

def _tokenize_listart(lines, start, bullet_indent, tokens, warnings):
    """
    Construct L{Token}s for the bullet and the first paragraph of the
    list item (or field) starting at C{lines[start]}, and append them
    to C{tokens}.  C{bullet_indent} should be the indentation of the
    list item.  Any warnings generated while tokenizing will be
    appended to C{warnings}.

    @param lines: The list of lines to be tokenized
    @param start: The index into C{lines} of the first line of the
        list item to be tokenized.
    @param bullet_indent: The indentation of C{lines[start]}.  This is
        the indentation of the list item.
    @param warnings: A list of the warnings generated by parsing.  Any
        new warnings generated while will tokenizing this paragraph
        will be appended to this list.
    @return: The line number of the first line following the list
        item's first paragraph.
        
    @type lines: C{list} of C{string}
    @type start: C{int}
    @type bullet_indent: C{int}
    @type tokens: C{list} of L{Token}
    @type warnings: C{list} of L{ParseError}
    @rtype: C{int}
    """
    linenum = start + 1
    para_indent = None
    doublecolon = lines[start].rstrip()[-2:] == '::'

    # Get the contents of the bullet.
    para_start = _BULLET_RE.match(lines[start], bullet_indent).end()
    bcontents = lines[start][bullet_indent:para_start].strip()
    
    while linenum < len(lines):
        # Find the indentation of this line.
        line = lines[linenum]
        indent = len(line) - len(line.lstrip())

        # "::" markers end paragraphs.
        if doublecolon: break
        if line.rstrip()[-2:] == '::': doublecolon = 1

        # A blank line ends the token
        if indent == len(line): break

        # Dedenting past bullet_indent ends the list item.
        if indent < bullet_indent: break
        
        # A line beginning with a bullet ends the token.
        if _BULLET_RE.match(line, indent): break
        
        # If this is the second line, set the paragraph indentation, or 
        # end the token, as appropriate.
        if para_indent == None: para_indent = indent

        # A change in indentation ends the token
        if indent != para_indent: break

        # Go on to the next line.
        linenum += 1

    # Add the bullet token.
    tokens.append(Token(Token.BULLET, start, bcontents, bullet_indent))

    # Add the paragraph token.
    pcontents = ([lines[start][para_start:].strip()] + 
                 [line.strip() for line in lines[start+1:linenum]])
    pcontents = ' '.join(pcontents).strip()
    if pcontents:
        tokens.append(Token(Token.PARA, start, pcontents, para_indent))

    # Return the linenum after the paragraph token ends.
    return linenum

def _tokenize_para(lines, start, para_indent, tokens, warnings):
    """
    Construct a L{Token} containing the paragraph starting at
    C{lines[start]}, and append it to C{tokens}.  C{para_indent}
    should be the indentation of the paragraph .  Any warnings
    generated while tokenizing the paragraph will be appended to
    C{warnings}.

    @param lines: The list of lines to be tokenized
    @param start: The index into C{lines} of the first line of the
        paragraph to be tokenized.
    @param para_indent: The indentation of C{lines[start]}.  This is
        the indentation of the paragraph.
    @param warnings: A list of the warnings generated by parsing.  Any
        new warnings generated while will tokenizing this paragraph
        will be appended to this list.
    @return: The line number of the first line following the
        paragraph. 
        
    @type lines: C{list} of C{string}
    @type start: C{int}
    @type para_indent: C{int}
    @type tokens: C{list} of L{Token}
    @type warnings: C{list} of L{ParseError}
    @rtype: C{int}
    """
    linenum = start + 1
    doublecolon = 0
    while linenum < len(lines):
        # Find the indentation of this line.
        line = lines[linenum]
        indent = len(line) - len(line.lstrip())

        # "::" markers end paragraphs.
        if doublecolon: break
        if line.rstrip()[-2:] == '::': doublecolon = 1

        # Blank lines end paragraphs
        if indent == len(line): break

        # Indentation changes end paragraphs
        if indent != para_indent: break

        # List bullets end paragraphs
        if _BULLET_RE.match(line, indent): break

        # Check for mal-formatted field items.
        if line[indent] == '@':
            estr = "Possible mal-formatted field item."
            warnings.append(TokenizationError(estr, linenum, line))
            
        # Go on to the next line.
        linenum += 1

    contents = [line.strip() for line in lines[start:linenum]]
    
    # Does this token look like a heading?
    if ((len(contents) < 2) or
        (contents[1][0] not in _HEADING_CHARS) or
        (abs(len(contents[0])-len(contents[1])) > 5)):
        looks_like_heading = 0
    else:
        looks_like_heading = 1
        for char in contents[1]:
            if char != contents[1][0]:
                looks_like_heading = 0
                break

    if looks_like_heading:
        if len(contents[0]) != len(contents[1]):
            estr = ("Possible heading typo: the number of "+
                    "underline characters must match the "+
                    "number of heading characters.")
            warnings.append(TokenizationError(estr, start, lines[start]))
        else:
            level = _HEADING_CHARS.index(contents[1][0])
            tokens.append(Token(Token.HEADING, start,
                                contents[0], para_indent, level))
            return start+2
                 
    # Add the paragraph token, and return the linenum after it ends.
    contents = ' '.join(contents)
    tokens.append(Token(Token.PARA, start, contents, para_indent))
    return linenum
        
def _tokenize(str, warnings, errors):
    """
    Split a given formatted docstring into an ordered list of
    C{Token}s, according to the epytext markup rules.

    @param str: The epytext string
    @type str: C{string}
    @param warnings: A list of the warnings generated by parsing.  Any
        new warnings generated while will tokenizing this paragraph
        will be appended to this list.
    @type warnings: C{list} of L{ParseError}
    @param errors: A list where any errors generated during parsing
        will be stored.  If no list is specified, then errors will 
        generate exceptions.
    @type errors: C{list} of L{ParseError}
    @return: a list of the C{Token}s that make up the given string.
    @rtype: C{list} of L{Token}
    """
    tokens = []
    lines = str.split('\n')

    # Scan through the lines, determining what @type of token we're
    # dealing with, and tokenizing it, as appropriate.
    linenum = 0
    while linenum < len(lines):
        # Get the current line and its indentation.
        line = lines[linenum]
        indent = len(line)-len(line.lstrip())

        if indent == len(line):
            # Ignore blank lines.
            linenum += 1
            continue
        elif line[indent:indent+4] == '>>> ':
            # blocks starting with ">>> " are doctest block tokens.
            linenum = _tokenize_doctest(lines, linenum, indent,
                                        tokens, errors)
        elif _BULLET_RE.match(line, indent):
            # blocks starting with a bullet are LI start tokens.
            linenum = _tokenize_listart(lines, linenum, indent,
                                        tokens, warnings)
            if tokens[-1].indent != None:
                indent = tokens[-1].indent
        else:
            # Check for mal-formatted field items.
            if line[indent] == '@':
                estr = "Possible mal-formatted field item."
                warnings.append(TokenizationError(estr, linenum, line))
            
            # anything else is either a paragraph or a heading.
            linenum = _tokenize_para(lines, linenum, indent,
                                     tokens, warnings)

        # Paragraph tokens ending in '::' initiate literal blocks.
        if (tokens[-1].tag == Token.PARA and
            tokens[-1].contents[-2:] == '::'):
            tokens[-1].contents = tokens[-1].contents[:-1]
            linenum = _tokenize_literal(lines, linenum, indent,
                                        tokens, warnings)

    return tokens


##################################################
## Inline markup ("colorizing")
##################################################

# Assorted regular expressions used for colorizing.
_BRACE_RE = re.compile('{|}')
_TARGET_RE = re.compile('^(.*?)\s*<(?:URI:|URL:)?([^<>]+)>$')

def _colorize(doc, token, errors, warnings=None, tagName='para'):
    """
    Given a string containing the contents of a paragraph, produce a
    DOM C{Element} encoding that paragraph.  Colorized regions are
    represented using DOM C{Element}s, and text is represented using
    DOM C{Text}s.

    @param errors: A list of errors.  Any newly generated errors will
        be appended to this list.
    @type errors: C{list} of C{string}
    
    @param warnings: A list of warnings.  Any newly generated warnings
        will be appended to this list.  To ignore warnings, use a
        value of None.
    @type warnings: C{list} of C{string}

    @param tagName: The element tag for the DOM C{Element} that should
        be generated.
    @type tagName: C{string}
    
    @return: a DOM C{Element} encoding the given paragraph.
    @returntype: C{Element}
    """
    str = token.contents
    linenum = 0
    if warnings == None: warnings = []
    
    # Maintain a stack of DOM elements, containing the ancestors of
    # the text currently being analyzed.  New elements are pushed when 
    # "{" is encountered, and old elements are popped when "}" is
    # encountered. 
    stack = [doc.createElement(tagName)]

    # This is just used to make error-reporting friendlier.  It's a
    # stack parallel to "stack" containing the index of each element's 
    # open brace.
    openbrace_stack = [0]

    # Process the string, scanning for '{' and '}'s.  start is the
    # index of the first unprocessed character.  Each time through the
    # loop, we process the text from the first unprocessed character
    # to the next open or close brace.
    start = 0
    while 1:
        match = _BRACE_RE.search(str, start)
        if match == None: break
        end = match.start()
        
        # Open braces start new colorizing elements.  When preceeded
        # by a capital letter, they specify a colored region, as
        # defined by the _COLORIZING_TAGS dictionary.  Otherwise, 
        # use a special "literal braces" element (with tag "litbrace"),
        # and convert them to literal braces once we find the matching 
        # close-brace.
        if match.group() == '{':
            if (end>0) and 'A' <= str[end-1] <= 'Z':
                if (end-1) > start:
                    stack[-1].appendChild(doc.createTextNode(str[start:end-1]))
                if not _COLORIZING_TAGS.has_key(str[end-1]):
                    estr = "Unknown inline markup tag."
                    errors.append(ColorizingError(estr, token, end-1))
                    stack.append(doc.createElement('unknown'))
                else:
                    tag = _COLORIZING_TAGS[str[end-1]]
                    stack.append(doc.createElement(tag))
            else:
                if end > start:
                    stack[-1].appendChild(doc.createTextNode(str[start:end]))
                stack.append(doc.createElement('litbrace'))
            openbrace_stack.append(end)
            stack[-2].appendChild(stack[-1])
            
        # Close braces end colorizing elements.
        elif match.group() == '}':
            # Check for (and ignore) unbalanced braces.
            if len(stack) <= 1:
                estr = "Unbalanced '}'."
                errors.append(ColorizingError(estr, token, end))
                start = end + 1
                continue

            # Add any remaining text.
            if end > start:
                stack[-1].appendChild(doc.createTextNode(str[start:end]))

            # Special handling for escape elements:
            if stack[-1].tagName == 'escape':
                if (len(stack[-1].childNodes) != 1 or
                    not isinstance(stack[-1].childNodes[0], Text)):
                    estr = "Invalid escape."
                    errors.append(ColorizingError(estr, token, end))
                else:
                    if _ESCAPES.has_key(stack[-1].childNodes[0].data):
                        escp = _ESCAPES[stack[-1].childNodes[0].data]
                        stack[-2].removeChild(stack[-1])
                        stack[-2].appendChild(doc.createTextNode(escp))
                    # Single-character escape.
                    elif len(stack[-1].childNodes[0].data) == 1:
                        escp = stack[-1].childNodes[0].data
                        stack[-2].removeChild(stack[-1])
                        stack[-2].appendChild(doc.createTextNode(escp))
                    else:
                        estr = "Invalid escape."
                        errors.append(ColorizingError(estr, token, end))

            # Special handling for literal braces elements:
            if stack[-1].tagName == 'litbrace':
                children = stack[-1].childNodes
                stack[-2].removeChild(stack[-1])
                stack[-2].appendChild(doc.createTextNode('{'))
                for child in children:
                    stack[-2].appendChild(child)
                stack[-2].appendChild(doc.createTextNode('}'))

            # Special handling for link-type elements:
            if stack[-1].tagName in _LINK_COLORIZING_TAGS:
                link = _colorize_link(doc, stack[-1], token, end,
                                      warnings, errors)

            # Pop the completed element.
            openbrace_stack.pop()
            stack.pop()

        start = end+1

    # Add any final text.
    if start < len(str):
        stack[-1].appendChild(doc.createTextNode(str[start:]))
        
    if len(stack) != 1: 
        estr = "Unbalanced '{'."
        errors.append(ColorizingError(estr, token, openbrace_stack[-1]))

    return stack[0]

def _colorize_link(doc, link, token, end, warnings, errors):
    children = link.childNodes[:]

    # If the last child isn't text, we know it's bad.
    if not isinstance(children[-1], Text):
        estr = "Bad %s target." % link.tagName
        errors.append(ColorizingError(estr, token, end))
        return
    
    # Did they provide an explicit target?
    match2 = _TARGET_RE.match(children[-1].data)
    if match2:
        (text, target) = match2.groups()
        children[-1].data = text
    # Can we extract an implicit target?
    elif len(children) == 1:
        target = children[0].data
    else:
        estr = "Bad %s target." % link.tagName
        errors.append(ColorizingError(estr, token, end))
        return

    # Construct the name element.
    name_elt = doc.createElement('name')
    for child in children:
        name_elt.appendChild(link.removeChild(child))

    # Clean up the target.  For URIs, assume http or mailto if they
    # don't specify (no relative urls)
    target = re.sub(r'\s', '', target)
    if link.tagName=='uri':
        if not re.match(r'\w+:', target):
            if re.match(r'\w+@(\w+)(\.\w+)*', target):
                target = 'mailto:' + target
            else:
                target = 'http://'+target
    elif link.tagName=='link':
        # Remove arg lists for functions (e.g., L{_colorize_link()})
        target = re.sub(r'\(.*\)$', '', target)
        if not re.match(r'^[a-zA-Z_]\w*(\.[a-zA-Z_]\w*)*$', target):
            estr = "Bad link target."
            errors.append(ColorizingError(estr, token, end))
            return

    # Construct the target element.
    target_elt = doc.createElement('target')
    target_elt.appendChild(doc.createTextNode(target))

    # Add them to the link element.
    link.appendChild(name_elt)
    link.appendChild(target_elt)

##################################################
## Formatters
##################################################

def to_epytext(tree, indent=0, seclevel=0):
    """
    Convert a DOM document encoding epytext back to an epytext string.
    This is the inverse operation from L{parse}.  I.e., assuming there
    are no errors, the following is true:
        - C{parse(to_epytext(tree)) == tree}

    The inverse is true, except that whitespace, line wrapping, and
    character escaping may be done differently.
        - C{to_epytext(parse(str)) == str} (approximately)

    @param tree: A DOM document encoding of an epytext string.
    @type tree: L{xml.dom.minidom.Document}
    @param indent: The indentation for the string representation of
        C{tree}.  Each line of the returned string will begin with
        C{indent} space characters.
    @type indent: C{int}
    @param seclevel: The section level that C{tree} appears at.  This
        is used to generate section headings.
    @type seclevel: C{int}
    @return: The epytext string corresponding to C{tree}.
    @rtype: C{string}
    """
    if isinstance(tree, Document):
        return to_epytext(tree.childNodes[0], indent, seclevel)
    if isinstance(tree, Text):
        str = re.sub(r'\{', '\0', tree.data)
        str = re.sub(r'\}', '\1', str)
        return str

    if tree.tagName == 'epytext': indent -= 2
    if tree.tagName == 'section': seclevel += 1
    children = [to_epytext(c, indent+2, seclevel) for c in tree.childNodes]
    childstr = ''.join(children)

    # Clean up for literal blocks (add the double "::" back)
    childstr = re.sub(':(\s*)\2', '::\\1', childstr)

    if tree.tagName == 'para':
        str = wordwrap(childstr, indent)+'\n'
        str = re.sub(r'((^|\n)\s*\d+)\.', r'\1E{.}', str)
        str = re.sub(r'((^|\n)\s*)-', r'\1E{-}', str)
        str = re.sub(r'((^|\n)\s*)@', r'\1E{@}', str)
        str = re.sub(r'::(\s*($|\n))', r'E{:}E{:}\1', str)
        str = re.sub('\0', 'E{lb}', str)
        str = re.sub('\1', 'E{rb}', str)
        return str
    elif tree.tagName == 'li':
        bulletAttr = tree.getAttributeNode('bullet')
        if bulletAttr: bullet = bulletAttr.value
        else: bullet = '-'
        return indent*' '+ bullet + ' ' + childstr.lstrip()
    elif tree.tagName == 'heading':
        str = re.sub('\0', 'E{lb}',childstr)
        str = re.sub('\1', 'E{rb}', str)
        uline = len(childstr)*_HEADING_CHARS[seclevel-1]
        return (indent-2)*' ' + str + '\n' + (indent-2)*' '+uline+'\n'
    elif tree.tagName == 'doctestblock':
        str = re.sub('\0', '{', childstr)
        str = re.sub('\1', '}', str)
        lines = ['  '+indent*' '+line for line in str.split('\n')]
        return '\n'.join(lines) + '\n\n'
    elif tree.tagName == 'literalblock':
        str = re.sub('\0', '{', childstr)
        str = re.sub('\1', '}', str)
        lines = [(indent+1)*' '+line for line in str.split('\n')]
        return '\2' + '\n'.join(lines) + '\n\n'
    elif tree.tagName == 'field':
        if (len(tree.childNodes) > 1 and
            tree.childNodes[1].tagName == 'arg'):
            return (indent*' '+'@'+children[0]+'('+
                    children[1]+'):\n'+''.join(children[2:]))
        else:
            return (indent*' '+'@'+children[0]+':\n'+
                    ''.join(children[1:]))
    elif tree.tagName == 'target':
        return '<%s>' % childstr
    elif tree.tagName in ('fieldlist', 'tag', 'arg', 'epytext',
                          'section', 'olist', 'ulist', 'name'):
        return childstr
    else:
        for (tag, name) in _COLORIZING_TAGS.items():
            if name == tree.tagName:
                return '%s{%s}' % (tag, childstr)
    raise ValueError('Unknown DOM element %r' % tree.tagName)

def to_plaintext(tree, indent=0, seclevel=0):
    """    
    Convert a DOM document encoding epytext to a string representation.
    This representation is similar to the string generated by
    C{to_epytext}, but C{to_plaintext} removes inline markup, prints
    escaped characters in unescaped form, etc.

    @param tree: A DOM document encoding of an epytext string.
    @type tree: L{xml.dom.minidom.Document}
    @param indent: The indentation for the string representation of
        C{tree}.  Each line of the returned string will begin with
        C{indent} space characters.
    @type indent: C{int}
    @param seclevel: The section level that C{tree} appears at.  This
        is used to generate section headings.
    @type seclevel: C{int}
    @return: The epytext string corresponding to C{tree}.
    @rtype: C{string}
    """
    if isinstance(tree, Document):
        return to_plaintext(tree.childNodes[0], indent, seclevel)
    if isinstance(tree, Text): return tree.data

    if tree.tagName == 'section': seclevel += 1

    # Figure out the child indent level.
    if tree.tagName == 'epytext': cindent = indent
    elif tree.tagName == 'li' and tree.getAttributeNode('bullet'):
        cindent = indent + 1 + len(tree.getAttributeNode('bullet').value)
    else:
        cindent = indent + 2
    children = [to_plaintext(c, cindent, seclevel) for c in tree.childNodes]
    childstr = ''.join(children)

    if tree.tagName == 'para':
        return wordwrap(childstr, indent)+'\n'
    elif tree.tagName == 'li':
        # We should be able to use getAttribute here; but there's no
        # convenient way to test if an element has an attribute..
        bulletAttr = tree.getAttributeNode('bullet')
        if bulletAttr: bullet = bulletAttr.value
        else: bullet = '-'
        return indent*' ' + bullet + ' ' + childstr.lstrip()
    elif tree.tagName == 'heading':
        uline = len(childstr)*_HEADING_CHARS[seclevel-1]
        return ((indent-2)*' ' + childstr + '\n' +
                (indent-2)*' ' + uline + '\n')
    elif tree.tagName == 'doctestblock':
        lines = [(indent+2)*' '+line for line in childstr.split('\n')]
        return '\n'.join(lines) + '\n\n'
    elif tree.tagName == 'literalblock':
        lines = [(indent+1)*' '+line for line in childstr.split('\n')]
        return '\n'.join(lines) + '\n\n'
    elif tree.tagName == 'fieldlist':
        return indent*' '+'{omitted fieldlist}\n'
    elif tree.tagName == 'uri':
        if len(children) != 2: raise ValueError('Bad URI ')
        elif children[0] == children[1]: return '<%s>' % children[1]
        else: return '%r<%s>' % (children[0], children[1])
    elif tree.tagName == 'link':
        if len(children) != 2: raise ValueError('Bad Link')
        return '%s' % children[1]
    elif tree.tagName in ('olist', 'ulist'):
        # Use a condensed list if each list item is 1 line long.
        for child in children:
            if child.count('\n') > 2: return childstr
        return childstr.replace('\n\n', '\n')+'\n'
    else:
        # Assume that anything else can be passed through.
        return childstr

def to_debug(tree, indent=4, seclevel=0):
    """    
    Convert a DOM document encoding epytext back to an epytext string,
    annotated with extra debugging information.  This function is
    similar to L{to_epytext}, but it adds explicit information about
    where different blocks begin, along the left margin.

    @param tree: A DOM document encoding of an epytext string.
    @type tree: L{xml.dom.minidom.Document}
    @param indent: The indentation for the string representation of
        C{tree}.  Each line of the returned string will begin with
        C{indent} space characters.
    @type indent: C{int}
    @param seclevel: The section level that C{tree} appears at.  This
        is used to generate section headings.
    @type seclevel: C{int}
    @return: The epytext string corresponding to C{tree}.
    @rtype: C{string}
    """
    if isinstance(tree, Document):
        return to_debug(tree.childNodes[0], indent, seclevel)
    if isinstance(tree, Text):
        str = re.sub(r'\{', '\0', tree.data)
        str = re.sub(r'\}', '\1', str)
        return str

    if tree.tagName == 'section': seclevel += 1
    children = [to_debug(c, indent+2, seclevel) for c in tree.childNodes]
    childstr = ''.join(children)

    # Clean up for literal blocks (add the double "::" back)
    childstr = re.sub(':( *\n     \|\n)\2', '::\\1', childstr)

    if tree.tagName == 'para':
        str = wordwrap(childstr, indent-6, 69)+'\n'
        str = re.sub(r'((^|\n)\s*\d+)\.', r'\1E{.}', str)
        str = re.sub(r'((^|\n)\s*)-', r'\1E{-}', str)
        str = re.sub(r'((^|\n)\s*)@', r'\1E{@}', str)
        str = re.sub(r'::(\s*($|\n))', r'E{:}E{:}\1', str)
        str = re.sub('\0', 'E{lb}', str)
        str = re.sub('\1', 'E{rb}', str)
        lines = str.rstrip().split('\n')
        lines[0] = '   P>|' + lines[0]
        lines[1:] = ['     |'+l for l in lines[1:]]
        return '\n'.join(lines)+'\n     |\n'
    elif tree.tagName == 'li':
        bulletAttr = tree.getAttributeNode('bullet')
        if bulletAttr: bullet = bulletAttr.value
        else: bullet = '-'
        return '  LI>|'+ (indent-6)*' '+ bullet + ' ' + childstr[6:].lstrip()
    elif tree.tagName in ('olist', 'ulist'):
        return 'LIST>|'+(indent-4)*' '+childstr[indent+2:]
    elif tree.tagName == 'heading':
        str = re.sub('\0', 'E{lb}', childstr)
        str = re.sub('\1', 'E{rb}', str)
        uline = len(childstr)*_HEADING_CHARS[seclevel-1]
        return ('SEC'+`seclevel`+'>|'+(indent-8)*' ' + str + '\n' +
                '     |'+(indent-8)*' ' + uline + '\n')
    elif tree.tagName == 'doctestblock':
        str = re.sub('\0', '{', childstr)
        str = re.sub('\1', '}', str)
        lines = ['     |'+(indent-4)*' '+line for line in str.split('\n')]
        lines[0] = 'DTST>'+lines[0][5:]
        return '\n'.join(lines) + '\n     |\n'
    elif tree.tagName == 'literalblock':
        str = re.sub('\0', '{', childstr)
        str = re.sub('\1', '}', str)
        lines = ['     |'+(indent-5)*' '+line for line in str.split('\n')]
        lines[0] = ' LIT>'+lines[0][5:]
        return '\2' + '\n'.join(lines) + '\n     |\n'
    elif tree.tagName == 'field':
        if (len(tree.childNodes) > 1 and
            tree.childNodes[1].tagName == 'arg'):
            return (' FLD>|'+(indent-6)*' '+'@'+children[0]+'('+
                    children[1]+'):\n'+''.join(children[2:]))
        else:
            return (' FLD>|'+(indent-6)*' '+'@'+children[0]+':\n'+
                    ''.join(children[1:]))
    elif tree.tagName == 'target':
        return '<%s>' % childstr
    elif tree.tagName in ('fieldlist', 'tag', 'arg', 'epytext',
                          'section', 'olist', 'ulist', 'name'):
        return childstr
    else:
        for (tag, name) in _COLORIZING_TAGS.items():
            if name == tree.tagName:
                return '%s{%s}' % (tag, childstr)
    raise ValueError('Unknown DOM element %r' % tree.tagName)

##################################################
## Helper Functions
##################################################

def wordwrap(str, indent=0, right=SCRWIDTH, startindex=0):
    """
    Word-wrap the given string.  All sequences of whitespace are
    converted into spaces, and the string is broken up into lines,
    where each line begins with C{indent} spaces, followed by one or
    more (space-deliniated) words whose length is less than
    C{right-indent}.  If a word is longer than C{right-indent}
    characters, then it is put on its own line.

    @param str: The string that should be word-wrapped.
    @type str: C{int}
    @param indent: The left margin of the string.  C{indent} spaces
        will be inserted at the beginning of every line.
    @type indent: C{int}
    @param right: The right margin of the string.
    @type right: C{int}
    @type startindex: C{int}
    @param startindex: The index at which the first line starts.  This
        is useful if you want to include other contents on the first
        line. 
    @return: A word-wrapped version of C{str}.
    @rtype: C{string}
    """
    words = str.split()
    out_str = ' '*(indent-startindex)
    charindex = max(indent, startindex)
    for word in words:
        if charindex+len(word) > right and charindex > 0:
            out_str += '\n' + ' '*indent
            charindex = indent
        out_str += word+' '
        charindex += len(word)+1
    return out_str.rstrip()+'\n'

##################################################
## Top-Level Wrapper function
##################################################

def pparse(str, show_warnings=1, show_errors=1, stream=sys.stderr):
    """
    Pretty-parse the string.  This parses the string, and catches any
    warnings or errors produced.  Any warnings and errors are
    displayed, and the resulting DOM parse structure is returned.

    @param str: The string to parse.
    @type str: C{string}
    @param show_warnings: Whether or not to display warnings generated
        by parsing C{str}.
    @type show_warnings: C{boolean}
    @param show_errors: Whether or not to display errors generated
        by parsing C{str}.
    @type show_errors: C{boolean}
    @param stream: The stream that warnings and errors should be
        written to.
    @type stream: C{stream}
    @return: a DOM document encoding the contents of C{str}.
    @rtype: L{xml.dom.minidom.Document}
    @raise SyntaxError: If any fatal errors were encountered.
    """
    errors = []
    warnings = []
    confused = 0
    try:
        val = parse(str, errors, warnings)
    except:
        confused = 1
        
    if not show_warnings: warnings = []
    warnings.sort()
    errors.sort()
    if warnings:
        print >>stream, '='*SCRWIDTH
        print >>stream, "WARNINGS"
        print >>stream, '-'*SCRWIDTH
        for warning in warnings:
            print >>stream, warning.as_warning()
        print >>stream, '='*SCRWIDTH
    if errors and show_errors:
        if not warnings: print >>stream, '='*SCRWIDTH
        print >>stream, "ERRORS"
        print >>stream, '-'*SCRWIDTH
        for error in errors:
            print >>stream, error
        print >>stream, '='*SCRWIDTH

    if confused: raise
    elif errors: raise SyntaxError('Encountered Errors')
    else: return val

##################################################
## Warnings and Errors
##################################################

class ParseError(Exception):
    """
    The base class for warnings and errors generated while parsing
    epytext strings.  When an epytext
    string is parsed, a list of warnings and a list of errors is
    generated.  Each element of these lists will be an instance of
    C{ParseError}.  Usually, C{ParseError}s are simply displayed to
    the user.

    The ParseError class is only used as a base class; it should never 
    be directly instantiated.

    @ivar linenum: The line on which the error occured.
    @type linenum: C{int}
    @ivar descr: A description of the error.
    @type descr: C{string}
    """
    def __repr__(self):
        """
        Return the formal representation of this C{ParseError}.
        C{ParseError}s have formal representations of the form::
           <ParseError on line 12>

        @return: the formal representation of this C{ParseError}.
        @rtype: C{string}
        """
        return '<ParseError on line %d>' % linenum
    
    def __str__(self):
        """
        Return the informal string representation of this
        C{ParseError}.  This multi-line string contains a description
        of the error, and specifies where it occured.
        
        @return: the informal representation of this C{ParseError}.
        @rtype: C{string}
        """
        return self._repr('Error')
    
    def as_warning(self):
        """
        Return a string representation of this C{ParseError}.  This
        multi-line string contains a description of the error, and
        specifies where it occured.  The description refers to the
        error as a 'warning.'
        
        @return: a string representation of this C{ParseError}.
        @rtype: C{string}
        """
        return self._repr('Warning')

    def as_error(self):
        """
        Return a string representation of this C{ParseError}.  This
        multi-line string contains a description of the error, and
        specifies where it occured.  The description refers to the
        error as an 'error.'

        @return: a string representation of this C{ParseError}.
        @rtype: C{string}
        """
        return self._repr('Error')

    def __cmp__(self, other):
        """
        Compare two C{ParseError}s, based on their line number.
          - Return -1 if C{self.linenum<other.linenum}
          - Return +1 if C{self.linenum>other.linenum}
          - Return 0 if C{self.linenum==other.linenum}.
        The return value is undefined if C{other} is not a
        ParseError.

        @rtype: C{int}
        """
        if not isinstance(other, ParseError): return -1000
        return cmp(self.linenum, other.linenum)

    def _repr(self, typ):
        """
        Return a string representation of this C{ParseError}.  This
        multi-line string contains a description of the error, and
        specifies where it occured.

        @param typ: Either C{'Error'} or C{'Warning'}, depending on
            what the error should be referred to as.
        @type typ: C{string}
        @return: a string representation of this C{ParseError}.
        @rtype: C{string}
        """
        raise NotImplementedError('_repr is undefined')

class TokenizationError(ParseError):
    """
    A warning or error generated while tokenizing a formatted
    documentation string.

    @ivar line: The line where the C{TokenizationError} occured.
    @type line: C{string}
    """
    def __init__(self, descr, linenum, line):
        """
        Construct a new tokenization exception.
        
        @param descr: A short description of the error.
        @type descr: C{string}
        @param linenum: The line number within the docstring that the
            error occured on.
        @type linenum: C{int}
        @param line: The line that the error occured on
        @type line: C{string}
        """
        self.descr = descr
        self.linenum = linenum + 1
        self.line = line
    
    def _repr(self, typ):
        str = '%5s: %s: ' % ('L'+`self.linenum`, typ)
        return str + wordwrap(self.descr, 7, startindex=len(str))[:-1]

class StructuringError(ParseError):
    """
    A warning or error generated while structuring a formatted
    documentation string.

    @ivar token: The C{Token} where the C{StructuringError} occured.
    @type token: L{Token}
    """
    def __init__(self, descr, token):
        """
        Construct a new structuring exception.
        
        @param descr: A short description of the error.
        @type descr: C{string}
        @param token: The token where the error occured
        @type token: L{Token}
        """
        self.descr = descr
        self.token = token
        self.linenum = token.startline + 1

    def _repr(self, typ):
        str = '%5s: %s: ' % ('L'+`self.linenum`, typ)
        return str + wordwrap(self.descr, 7, startindex=len(str))[:-1]

class ColorizingError(ParseError):
    """
    A warning or error generated while colorizing a paragraph.

    @ivar token: The C{Token} where the C{ColorizingError} occured.
    @type token: L{Token}
    @ivar charnum: The index into the paragraph's contents of the
        character where the C{ColorizingError} occured.
    @type charnum: C{int}
    """
    def __init__(self, descr, token, charnum):
        """
        Construct a new colorizing exception.
        
        @param descr: A short description of the error.
        @type descr: C{string}
        @param token: The token where the error occured
        @type token: L{Token}
        @param charnum: The character index of the position in
            C{token} where the error occured.
        @type charnum: C{int}
        """
        self.descr = descr
        self.token = token
        self.charnum = charnum
        self.linenum = token.startline + 1

    def _repr(self, typ):
        RANGE = 20
        if self.charnum <= RANGE:
            left = self.token.contents[0:self.charnum]
        else:
            left = '...' + self.token.contents[self.charnum-RANGE:self.charnum]
        if (len(self.token.contents)-self.charnum) <= RANGE:
            right = self.token.contents[self.charnum:]
        else:
            right = (self.token.contents[self.charnum:self.charnum+RANGE]
                     + '...')
        
        str = '%5s: %s: ' % ('L'+`self.linenum`, typ)
        str += wordwrap(self.descr, 7, startindex=len(str))
        return (str + '\n       %s%s\n       %s^' %
                (left, right, ' '*len(left)))
                
##################################################
## Convenience parsers
##################################################

def parse_as_literal(str):
    """
    Return a DOM document matching the epytext DTD, containing a
    single literal block.  That literal block will include the
    contents of the given string.  This method is typically used as a
    fall-back when the parser fails.

    @param str: The string which should be enclosed in a literal
        block.
    @type str: C{string}
    
    @return: A DOM document containing C{str} in a single literal
        block.
    @rtype: L{xml.dom.minidom.Document}
    """
    doc = Document()
    epytext = doc.createElement('epytext')
    lit = doc.createElement('literalblock')
    doc.appendChild(epytext)
    epytext.appendChild(lit)
    lit.appendChild(doc.createTextNode(str))
    return doc

def parse_as_para(str):
    """
    Return a DOM document matching the epytext DTD, containing a
    single paragraph.  That paragraph will include the contents of the
    given string.  This can be used to wrap some forms of
    automatically generated information (such as type names) in
    paragraphs.

    @param str: The string which should be enclosed in a paragraph.
    @type str: C{string}
    
    @return: A DOM document containing C{str} in a single paragraph.
    @rtype: L{xml.dom.minidom.Document}
    """
    doc = Document()
    epytext = doc.createElement('epytext')
    para = doc.createElement('para')
    doc.appendChild(epytext)
    epytext.appendChild(para)
    para.appendChild(doc.createTextNode(str))
    return doc

def parse_type_of(obj):
    """
    Return a DOM document matching the epytext DTD, containing a
    description of C{obj}'s type.  The description consists of a
    sinlge paragraph.  If C{obj} is an instance, then its type
    description is a link to its class.  Otherwise, its type
    description is the name of its type.

    @param obj: The object whose type should be returned as DOM document.
    @type obj: any
    @return: A DOM document containing a description of C{obj}'s type.
    @rtype: L{xml.dom.minidom.Document}
    """
    doc = Document()
    epytext = doc.createElement('epytext')
    para = doc.createElement('para')
    doc.appendChild(epytext)
    epytext.appendChild(para)
    
    if type(obj) is types.InstanceType:
        link = doc.createElement('link')
        name = doc.createElement('name')
        target = doc.createElement('target')
        para.appendChild(link)
        link.appendChild(name)
        link.appendChild(target)
        name.appendChild(doc.createTextNode(str(obj.__class__.__name__)))
        target.appendChild(doc.createTextNode(str(obj.__class__)))        
    else:
        code = doc.createElement('code')
        para.appendChild(code)
        code.appendChild(doc.createTextNode(type(obj).__name__))
    return doc

# Is the cloning that happens here safe/proper?  (Cloning between 2
# different documents)
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
    epytext = doc.createElement('epytext')
    doc.appendChild(epytext)

    if isinstance(epytext_doc, Document):
        tree = epytext_doc.childNodes[0]
    else:
        tree = epytext_doc
    
    # Find the first paragraph.
    children = tree.childNodes
    while (len(children) > 0) and (children[0].tagName != 'para'):
        if children[0].tagName in ('section', 'ulist', 'olist', 'li'):
            children = children[0].childNodes
        else:
            children = children[1:]

    # Special case: if the docstring contains a single literal block,
    # then try extracting the summary from it.
    if (len(children) == 0 and len(tree.childNodes) == 1 and
        tree.childNodes[0].tagName == 'literalblock'):
        str = re.split(r'\n\s*(\n|$).*',
                       tree.childNodes[0].childNodes[0].data, 1)[0]
        children = [doc.createElement('para')]
        children[0].appendChild(doc.createTextNode(str))

    # If we didn't find a paragraph, return an empty epytext.
    if len(children) == 0: return doc

    # Extract the first sentence.
    parachildren = children[0].childNodes
    para = doc.createElement('para')
    epytext.appendChild(para)
    for parachild in parachildren:
        if isinstance(parachild, Text):
            m = re.match(r'(\s*[\w\W]*?\.)(\s|$)', parachild.data)
            if m:
                para.appendChild(doc.createTextNode(m.group(1)))
                return doc
        para.appendChild(parachild.cloneNode(1))

    return doc
