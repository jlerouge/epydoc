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

   <!ELEMENT uri    (name, target)>
   <!ELEMENT link   (name, target)>
   <!ELEMENT name   (#PCDATA | %colorized;)*>
   <!ELEMENT target (#PCDATA)>
   
   <!ELEMENT code   (#PCDATA | %colorized;)*>
   <!ELEMENT math   (#PCDATA | %colorized;)*>
   <!ELEMENT italic (#PCDATA | %colorized;)*>
   <!ELEMENT bold   (#PCDATA | %colorized;)*>
   <!ELEMENT index  (#PCDATA | %colorized;)>

This package also contains a number of formatters, which can be used
to convert the XML/DOM representations of Epytext strings to HTML,
LaTeX, and a number of other formats.

Supported features:
  - literal blocks (introduced with ::)
  - unordered lists (bullet is '-')
  - ordered lists (bullet is '\d+.')
  - I{colorizing}
  - sections

@var SCRWIDTH: The default width with which text will be wrapped
      when formatting the output of the parser.
"""

# Replace "index" entity with "indexed"?

# Code organization..
#   1. parse()
#   2. tokenize()
#   3. colorize()
#   4. helpers
#   5. testing

import re, epydoc.uid
from xml.dom.minidom import Element, Text

##################################################
## Constants
##################################################

# Default screen width, for printing.
SCRWIDTH = 75

# The possible heading underline characters, listed in order of
# heading depth. 
_HEADING_CHARS = "=-~"

# Escape codes.  These should be needed very rarely.
_ESCAPES = {'lb':'{', 'rb': '}'}

# Tags for colorizing text.
_COLORIZING_TAGS = {
    'C': 'code',
    'M': 'math',
    'X': 'index',
    'I': 'italic', 
    'B': 'bold',
    'U': 'uri',
    'L': 'link',       # A Python identifier that should be linked to 
    'E': 'escape',     # "escape" is a special tag.
    }

# Which tags can use "link syntax" (e.g., U{Python<www.python.org>})?
_LINK_COLORIZING_TAGS = ['link', 'uri']

# Should we use Bruce Mitchener's link syntax
# (e.g., U{Python|www.python.org}) instead of standard link syntax?
_VBAR_LINK_SYNTAX = 0

##################################################
## Helpers
##################################################

def parse_as_literal(str):
    """
    Return a DOM tree matching the epytext DTD, containing a single
    literal block.  That literal block will include the contents of
    the given string.  This method is typically used as a fall-back
    when the parser fails.

    @param str: The string which should be enclosed in a literal
        block.
    @type str: C{string}
    
    @return: A DOM tree containing C{str} in a single literal block.
    @rtype: C{xml.dom.minidom.Element}
    """
    epytext = Element('epytext')
    lit = Element('literalblock')
    epytext.appendChild(lit)
    lit.appendChild(Text(str))
    return epytext

def summary(tree):
    """
    Given a DOM tree representing formatted documentation, return a
    new DOM tree containing the documentation's first sentence.
    """
    # Find the first paragraph.
    children = [tree]
    while (len(children) > 0) and (children[0].tagName != 'para'):
        if children[0].tagName in ('epytext', 'section', 'ulist', 'olist'):
            children = children[0].childNodes
        else:
            children = children[1:]

    # If we didn't find a paragraph, return an empty epytext.
    if len(children) == 0: return Element('epytext')

    # Extract the first sentence.
    parachildren = children[0].childNodes
    summary = Element('epytext')
    for parachild in parachildren:
        if (isinstance(parachild, Text) and
            '.' in parachild.data):
            dotloc = parachild.data.find('.')
            summary.appendChild(Text(parachild.data[:dotloc+1]))
            return summary
        summary.appendChild(parachild.cloneNode(1))

    return summary

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
    @rtype: C{xml.dom.minidom.Element}
    
    @raise ParseError: If C{errors} is C{None} and an error is
        encountered while parsing.

    @see: C{xml.dom.minidom.Element}
    """
    # Initialize warning and error lists.
    if warnings == None: warnings = []
    if errors == None:
        errors = []
        raise_on_error = 1
    else:
        raise_on_error = 0

    # Tokenize the input string.
    tokens = _tokenize(str, warnings)

    encountered_field = 0       # Have we encountered a field yet?

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
    stack = [None, Element('epytext')]
    indent_stack = [-1, None]

    for token in tokens:
        #print [t and t.tagName for t in stack], token.tag
        #print indent_stack, token.indent
        
        # Pop any completed blocks off the stack.
        _pop_completed_blocks(token, stack, indent_stack)

        # If Token has type PARA, colorize and add the new paragraph
        if token.tag == Token.PARA:
            _add_para(token, stack, indent_stack, errors, warnings)
                     
        # If Token has type HEADING, add the new section
        elif token.tag == Token.HEADING:
            _add_section(token, stack, indent_stack, errors, warnings)

        # If Token has type LBLOCK, add the new literal block
        elif token.tag == Token.LBLOCK:
            stack[-1].appendChild(token.to_dom())

        # If Token has type DTBLOCK, add the new doctest block
        elif token.tag == Token.DTBLOCK:
            stack[-1].appendChild(token.to_dom())

        # If Token has type BULLET, add the new list/list item/field
        elif token.tag == Token.BULLET:
            _add_list(token, stack, indent_stack, errors, warnings)
        else:
            assert 0, 'Unknown token type: '+token.tag

        # Check if the DOM element we just added was a field..
        if stack[-1].tagName == 'field':
            encountered_field = 1
        elif encountered_field == 1:
            if len(stack) <= 3:
                # For now, make this a warning; later it will be an error
                estr = ("Fields must be the final elements in a "+
                        "epytext string.")
                warnings.append(StructuringError(estr, token))

    # If there was an error, then signal it!
    if errors != []:
        if raise_on_error:
            raise errors[0]
        else:
            pass # For debugging!
            #return None
        
    # Return the top-level epytext DOM element.
    return stack[1]

def _pop_completed_blocks(token, stack, indent_stack):
    """
    Pop any completed blocks off the stack.  This includes any
    blocks that we have dedented past, as well as any list item
    blocks that we've dedented to.  The top element on the stack 
    should only be \"list\" if we're about to start a new list
    item (i.e., if the next token is a bullet).
    """
    indent = token.indent
    if indent != None:
        while ((len(stack) > 2) and
               ((indent_stack[-1]!=None and indent<indent_stack[-1]) or
                (indent_stack[-1]==None and indent<indent_stack[-2]) or
                (stack[-1].tagName in ('li', 'field') and
                 indent_stack[-1]==None and
                 indent==indent_stack[-2]))):
            stack.pop()
            indent_stack.pop()
            
    if (stack[-1].tagName in ('ulist', 'olist', 'fieldlist') and
        token.tag != 'bullet'):
        stack.pop()
        indent_stack.pop()

def _add_para(para_token, stack, indent_stack, errors, warnings):
    """Colorize the given paragraph, and add it to the DOM tree."""
    # Check indentation, and update the parent's indentation
    # when appropriate.
    if indent_stack[-1] == None:
        indent_stack[-1] = para_token.indent
    if para_token.indent == indent_stack[-1]:
        # Colorize the paragraph and add it.
        para = _colorize(para_token, errors, warnings)
        stack[-1].appendChild(para)
    else:
        if (len(stack[-1].childNodes)>0 and
            stack[-1].childNodes[-1].tagName == 'para'):
            estr = ("Improper paragraph indentation: "+
                    "blockquotes are not supported")
            errors.append(StructuringError(estr, para_token))
        else:
            estr = "Improper paragraph indentation"
            errors.append(StructuringError(estr, para_token))

def _add_section(heading_token, stack, indent_stack, errors, warnings):
    """Add a new section to the DOM tree, with the given heading."""
    if indent_stack[-1] == None:
        indent_stack[-1] = heading_token.indent
    elif indent_stack[-1] != heading_token.indent:
        estr = "Improper heading indentation"
        errors.append(StructuringError(estr, heading_token))

    # Check for errors.
    for tok in stack[2:]:
        if tok.tagName != "section":
            estr = "Headings may only occur at the top level"
            errors.append(StructuringError(estr, heading_token))
            break
    if (heading_token.level+2) > len(stack):
        estr = "Wrong underline character for heading"
        errors.append(StructuringError(estr, heading_token))

    # Pop the appropriate number of headings so we're at the
    # correct level.
    stack[heading_token.level+2:] = []
    indent_stack[heading_token.level+2:] = []

    # Add the section's and heading's DOM elements.
    sec = Element("section")
    stack[-1].appendChild(sec)
    head = heading_token.to_dom()
    stack.append(sec)
    sec.appendChild(head)
    indent_stack.append(None)
        
def _add_list(bullet_token, stack, indent_stack, errors, warnings):
    """Add a new list item or field to the DOM tree, with the given
    bullet or field tag.  When necessary, create the associated
    list."""
    # Determine what type of bullet it is.
    if bullet_token.contents[-1] == '-':
        list_type = 'ulist'
    elif bullet_token.contents[-1] == '.':
        list_type = 'olist'
    elif bullet_token.contents[-1] == ':':
        list_type = 'fieldlist'
    else:
        print 'WARNING: Bad bullet', bullet_token.contents
        list_type = 'ulist'
    
    if stack[-1].tagName != list_type:
        if stack[-1].tagName in ('ulist', 'olist', 'fieldlist'):
            stack.pop()
            indent_stack.pop()

        if list_type == 'fieldlist':
            # Fieldlist should be at the top-level.
            for tok in stack[2:]:
                if tok.tagName != "section":
                    #print [s.tagName for s in stack[1:]]
                    estr = "Fields may only occur at the top level"
                    errors.append(StructuringError(estr, bullet_token))
                    break
            stack[2:] = []
            indent_stack[2:] = []

        # Add the new list.
        lst = Element(list_type)
        stack[-1].appendChild(lst)
        stack.append(lst)
        indent_stack.append(bullet_token.indent)

    # Fields are treated somewhat specially: A "fieldlist"
    # node is created to make the parsing simpler, but fields
    # are adjoined directly into the "epytext" node, not into
    # the "fieldlist" node.
    if list_type == 'fieldlist':
        li = Element("field")
        tagwords = bullet_token.contents[1:-1].split()
        assert 0 < len(tagwords) < 3, "Bad field tag"
        tag = Element("tag")
        tag.appendChild(Text(tagwords[0]))
        li.appendChild(tag)
        if len(tagwords) > 1:
            arg = Element("arg")
            arg.appendChild(Text(tagwords[1]))
            li.appendChild(arg)
    else:
        li = Element("li")
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

    @cvar PARA: The C{tag} value for paragraph C{Token}s.
    @cvar LBLOCK: The C{tag} value for literal C{Token}s.
    @cvar DTBLOCK: The C{tag} value for doctest C{Token}s.
    @cvar HEADING: The C{tag} value for heading C{Token}s.
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
        return '<Token: '+str(self.tag)+' at line '+`self.startline`+'>'

    def to_dom(self):
        """
        @return: a DOM representation of this C{Token}.
        @rtype: C{xml.dom.minidom.Element}
        """
        e = Element(self.tag)
        e.appendChild(Text(self.contents))
        return e

# Construct regular expressions for recognizing bullets.  These are
# global so they don't have to be reconstructed each time we tokenize
# a docstring.
_ULIST_BULLET = '[-*]( +|$)'
_OLIST_BULLET = '(\d+[.])+( +|$)'
_FIELD_BULLET = '@\w+( +[\w\.]+)?:( +|$)'
_BULLET_RE = re.compile(_ULIST_BULLET + '|' +
                        _OLIST_BULLET + '|' +
                        _FIELD_BULLET)
_LIST_BULLET_RE = re.compile(_ULIST_BULLET + '|' + _OLIST_BULLET)
del _ULIST_BULLET, _OLIST_BULLET, _FIELD_BULLET

def _tokenize_doctest(lines, start, block_indent, tokens, warnings):
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
    @param warnings: A list of the warnings generated by parsing.  Any
        new warnings generated while will tokenizing this paragraph
        will be appended to this list.
    @return: The line number of the first line following the doctest
        block.
        
    @type lines: C{list} of C{string}
    @type start: C{int}
    @type block_indent: C{int}
    @type tokens: C{list} of L{Token}
    @type warnings: C{list} of C{ParseError}
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
        
        # A Dedent past block_indent givs a warning.
        if indent < block_indent:
            min_indent = min(min_indent, indent)
            estr = 'Bad Doctest block indentation'
            warnings.append(TokenizationError(estr, linenum, line))

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
    @type warnings: C{list} of C{ParseError}
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
    @type warnings: C{list} of C{ParseError}
    @rtype: C{int}
    """
    linenum = start + 1
    para_indent = None
    brace_level = lines[start].count('{') - lines[start].count('}')
    if brace_level < 0: brace_level = 0
    while linenum < len(lines):
        # Find the indentation of this line.
        line = lines[linenum]
        indent = len(line) - len(line.lstrip())

        # A blank line ends the token
        if indent == len(line): break

        # Dedenting past bullet_indent ends the list item.
        if indent < bullet_indent: break
        
        # A line beginning with a bullet ends the token.
        if brace_level == 0 and _LIST_BULLET_RE.match(line, indent):
            if para_indent and indent == para_indent:
                estr = ("Sublists should be indented or separated "+
                        "by blank lines.")
                warnings.append(TokenizationError(estr, linenum, line))
            break
        brace_level += line.count('{')        
        brace_level -= line.count('}')
        if brace_level < 0: brace_level = 0

        if indent == bullet_indent:
            if brace_level == 0 and _BULLET_RE.match(line, indent):
                # Don't complain if it's a field.??
                break
            else:
                estr = ("List item contents should be indented; "+
                        "Paragraphs should be separated from "+
                        "lists by blank lines.")
                warnings.append(TokenizationError(estr, linenum, line))
                break

        # If this is the second line, set the paragraph indentation, or 
        # end the token, as appropriate.
        if para_indent == None: para_indent = indent

        # A change in indentation ends the token
        if indent != para_indent: break

        # Go on to the next line.
        linenum += 1

    # Add the bullet token.
    para_start = _BULLET_RE.match(lines[start], bullet_indent).end()
    bcontents = lines[start][bullet_indent:para_start].strip()
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
    @type warnings: C{list} of C{ParseError}
    @rtype: C{int}
    """
    linenum = start + 1
    brace_level = lines[start].count('{') - lines[start].count('}')
    if brace_level < 0: brace_level = 0
    while linenum < len(lines):
        # Find the indentation of this line.
        line = lines[linenum]
        indent = len(line) - len(line.lstrip())

        # Blank lines end paragraphs
        if indent == len(line): break

        # Indentation changes end paragraphs
        if indent != para_indent: break

        # List bullets end paragraphs
        if brace_level == 0 and _BULLET_RE.match(line, indent):
            estr = "Lists should be indented or separated by blank lines."
            warnings.append(TokenizationError(estr, linenum, line))
            break
        brace_level += line.count('{')        
        brace_level -= line.count('}')
        if brace_level < 0: brace_level = 0

        # Check for mal-formatted field items.
        if line[indent] == '@':
            estr = "Possible mal-formatted field item"
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
            #if len(contents) > 2:
            #    # On second thought, why not allow headings to be
            #    # immediately followed by a paragraph? :)
            #    estr = "Headings should be followed by blank lines"
            #    err = TokenizationError(estr, linenum, line)
            #    warnings.append(err)
            return start+2
                 
    # Add the paragraph token, and return the linenum after it ends.
    contents = ' '.join(contents)
    tokens.append(Token(Token.PARA, start, contents, para_indent))
    return linenum
        
def _tokenize(str, warnings):
    """
    Split a given formatted docstring into an ordered list of
    C{Token}s, according to the epytext markup rules.

    @param str: The epytext string
    @type str: C{string}
    @param warnings: A list of the warnings generated by parsing.  Any
        new warnings generated while will tokenizing this paragraph
        will be appended to this list.
    @type warnings: C{list} of L{ParseError}
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
                                        tokens, warnings)
        elif _BULLET_RE.match(line, indent):
            # blocks starting with a bullet are LIStart tokens.
            linenum = _tokenize_listart(lines, linenum, indent,
                                        tokens, warnings)
            if tokens[-1].indent != None:
                indent = tokens[-1].indent
        else:
            # Check for mal-formatted field items.
            if line[indent] == '@':
                estr = "Possible mal-formatted field item"
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
if _VBAR_LINK_SYNTAX:
    _URI_RE = re.compile(r'^(.*?)\s*\|([^|]+)$')
else:
    _URI_RE = re.compile('^(.*?)\s*<(?:URI:|URL:)?([^<>]+)>$')

def _colorize(token, errors, warnings=None):
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
    stack = [Element('para')]

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
                    stack[-1].appendChild(Text(str[start:end-1]))
                if not _COLORIZING_TAGS.has_key(str[end-1]):
                    estr = ("'{' must be preceeded by a valid colorizing tag")
                    errors.append(ColorizingError(estr, token, end))
                    stack.append(Element('unknown'))
                else:
                    stack.append(Element(_COLORIZING_TAGS[str[end-1]]))
            else:
                if end > start:
                    stack[-1].appendChild(Text(str[start:end]))
                stack.append(Element('litbrace'))
            openbrace_stack.append(end)
            stack[-2].appendChild(stack[-1])
            
        # Close braces end colorizing elements.
        elif match.group() == '}':
            # Check for (and ignore) unbalanced braces.
            if len(stack) <= 1:
                estr = "Unbalanced '}'"
                errors.append(ColorizingError(estr, token, end))
                start = end + 1
                continue

            # Add any remaining text.
            if end > start:
                stack[-1].appendChild(Text(str[start:end]))

            # Special handling for escape elements:
            if stack[-1].tagName == 'escape':
                if (len(stack[-1].childNodes) != 1 or
                    not isinstance(stack[-1].childNodes[0], Text)):
                    estr = "Invalid escape"
                    errors.append(ColorizingError(estr, token, end))
                else:
                    # Single-character escape.
                    if len(stack[-1].childNodes[0].data) == 1:
                        escp = stack[-1].childNodes[0].data
                        stack[-2].removeChild(stack[-1])
                        stack[-2].appendChild(Text(escp))
                    elif _ESCAPES.has_key(stack[-1].childNodes[0].data):
                        escp = _ESCAPES[stack[-1].childNodes[0].data]
                        stack[-2].removeChild(stack[-1])
                        stack[-2].appendChild(Text(escp))
                    else:
                        estr = "Invalid escape"
                        errors.append(ColorizingError(estr, token, end))

            # Special handling for literal braces elements:
            if stack[-1].tagName == 'litbrace':
                children = stack[-1].childNodes
                stack[-2].removeChild(stack[-1])
                stack[-2].appendChild(Text('{'))
                for child in children:
                    stack[-2].appendChild(child)
                stack[-2].appendChild(Text('}'))

            # Special handling for link-type elements:
            if stack[-1].tagName in _LINK_COLORIZING_TAGS:
                link = _colorize_link(stack[-1], token, end, warnings, errors)

            # Pop the completed element.
            openbrace_stack.pop()
            stack.pop()

        start = end+1

    # Add any final text.
    if start < len(str):
        stack[-1].appendChild(Text(str[start:]))
        
    if len(stack) != 1: 
        estr = "Unbalanced "+`'{'`
        errors.append(ColorizingError(estr, token, openbrace_stack[-1]))

    return stack[0]

def _colorize_link(link, token, end, warnings, errors):
    children = link.childNodes[:]

    # If the last child isn't text, we know it's bad.
    if not isinstance(children[-1], Text):
        estr = "Bad %s URI" % link.tagName
        errors.append(ColorizingError(estr, token, end))
        return
    
    # Did they provide an explicit URL?
    match2 = _URI_RE.match(children[-1].data)
    if match2:
        (text, uri) = match2.groups()
        children[-1].data = text
    # Can we extract an implicit URL?
    elif len(children) == 1:
        uri = children[0].data
    else:
        estr = "Bad %s URI" % link.tagName
        errors.append(ColorizingError(estr, token, end))
        return

    # Construct the name element.
    name = Element('name')
    for child in children:
        name.appendChild(link.removeChild(child))

    # Clean up the target.  For URIs, assume http if they don't
    # specify (no relative urls)
    uri = re.sub(r'\s', '', uri)
    if link.tagName=='uri' and not re.match(r'\w+:', uri):
        uri = 'http://'+uri

    # Construct the target element.
    target = Element('target')
    target.appendChild(Text(re.sub(r'\s', '', uri)))

    # Add them to the link element.
    link.appendChild(name)
    link.appendChild(target)
            
##################################################
## Formatters
##################################################

def index_to_anchor(str):
    "Given a string, construct a name for an index anchor."
    return "_index_"+re.sub("[^a-zA-Z0-9]", "_", str)

def to_epytext(tree, indent=0, seclevel=0, **kwargs):
    """
    Convert a DOM tree encoding epytext back to an epytext string.
    This is the inverse operation from L{parse}.  I.e., assuming there
    are no errors, the following is true:
        - C{parse(to_epytext(tree)) == tree}

    The inverse is true, except that whitespace and line wrapping may
    be done differently:
        - C{to_epytext(parse(str)) == str} (+/- whitespace)

    This still doesn't handle escape characters quite right..
    """
    if isinstance(tree, Text):
        str = tree.data
#         str = re.sub(r'\{', '\0', str)
#         str = re.sub(r'\}', '\1', str)
#         #str = re.sub(r'\.', 'E{.}', str)
#         #str = re.sub(r'-', 'E{.}', str)
#         str = re.sub('\0', 'E{lb}', str)
#         str = re.sub('\1', 'E{rb}', str)
        return str

    if tree.tagName in ('epytext', 'ulist', 'olist', 'fieldlist'): indent -= 2
    if tree.tagName == 'section': seclevel += 1
    children = [to_epytext(c, indent+2, seclevel) for c in tree.childNodes]
    childstr = ''.join(children)

    # Clean up for literal blocks (add the double "::" back)
    childstr = re.sub(':(\s*)\0', '::\\1', childstr)

    if tree.tagName == 'para':
        return wordwrap(childstr, indent)+'\n'
    elif tree.tagName == 'li':
        bulletAttr = tree.getAttributeNode('bullet')
        if bulletAttr: bullet = bulletAttr.value
        else: bullet = '-'
        return indent*' '+ bullet + ' ' + childstr.lstrip()
    elif tree.tagName == 'heading':
        uline = len(childstr)*_HEADING_CHARS[seclevel-1]
        return indent*' ' + childstr + '\n' + indent*' '+uline+'\n'
    elif tree.tagName == 'doctestblock':
        lines = [indent*' '+line for line in childstr.split('\n')]
        return '\n'.join(lines) + '\n\n'
    elif tree.tagName == 'literalblock':
        lines = [(indent+1)*' '+line for line in childstr.split('\n')]
        return '\0' + '\n'.join(lines) + '\n\n'
    elif tree.tagName == 'field':
        if (len(tree.childNodes) > 1 and
            tree.childNodes[1].tagName == 'arg'):
            return (indent*' '+children[0]+'('+
                    children[1]+'):\n'+''.join(children[2:]))
        else:
            return (indent*' '+children[0]+':\n'+
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
    Given the DOM tree for an epytext string (as
    returned by L{parse}), return a string encoding it in plaintext.
    This function is similar to L{to_epytext}; however, it prints
    escaped characters in unescaped form, removes colorizing, etc...
    """
    if isinstance(tree, Text): return tree.data

    if tree.tagName == 'epytext': indent -= 2
    if tree.tagName == 'section': seclevel += 1
    children = [to_plaintext(c, indent+2, seclevel) for c in tree.childNodes]
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
        lines = [(indent+3)*' '+line for line in childstr.split('\n')]
        return '\n'.join(lines) + '\n\n'
    elif tree.tagName in ('olist', 'ulist'):
        return childstr
    elif tree.tagName == 'fieldlist':
        return indent*' '+'{omitted fieldlist}\n'
    elif tree.tagName in ('uri', 'link'):
        if len(children) != 2: return 'XX'+childstr+'XX'
        elif children[0] == children[1]: return '<%s>' % children[1]
        else: return '%r<%s>' % (children[0], children[1])
    else:
        # Assume that anything else can be passed through.
        return childstr

def to_debug(tree, indent=4, seclevel=0):
    """
    Given the DOM tree for an epytext string (as
    returned by L{parse}), return a string encoding it in plaintext.
    This function is similar to L{to_epytext}; however, it prints
    escaped characters in unescaped form, removes colorizing, etc...
    """
    if isinstance(tree, Text): return tree.data

    if tree.tagName in ('olist', 'ulist'): indent -= 2
    if tree.tagName == 'section': seclevel += 1
    children = [to_debug(c, indent+2, seclevel) for c in tree.childNodes]
    childstr = ''.join(children)

    if tree.tagName == 'para':
        lines = ['     |'+l for l in
                 wordwrap(childstr, indent-6).rstrip().split('\n')]
        return '\n'.join(lines)+'\n'
    elif tree.tagName == 'li':
        bulletAttr = tree.getAttributeNode('bullet')
        if bulletAttr: bullet = bulletAttr.value
        else: bullet = '-'
        return '  LI>|'+(indent-6)*' '+ bullet + ' ' + childstr[6:].lstrip()
    elif tree.tagName == 'heading':
        uline = len(childstr)*_HEADING_CHARS[seclevel-1]
        return ('SEC'+`seclevel`+'>|'+(indent-6)*' ' + childstr + '\n' +
                '     |'+(indent-6)*' ' + uline + '\n')
    elif tree.tagName == 'doctestblock':
        lines = ['DTST>|'+(indent-6)*' '+line for line in childstr.split('\n')]
        return '\n'.join(lines) + '\n'
    elif tree.tagName == 'literalblock':
        lines = [' LIT>|'+(indent-5)*' '+line for line in childstr.split('\n')]
        return '\n'.join(lines) + '\n'
    elif tree.tagName in ('olist', 'ulist'):
        return 'LIST>|'+(indent-6)*' '+childstr[indent+2:]
    elif tree.tagName == 'field':
        if (len(tree.childNodes) > 1 and
            tree.childNodes[1].tagName == 'arg'):
            return (' FLD>|'+(indent-6)*' '+children[0]+'('+
                    children[1]+'):\n'+''.join(children[2:]))
        else:
            return (' FLD>|'+(indent-6)*' '+children[0]+':\n'+
                    ''.join(children[1:]))
    elif tree.tagName in ('fieldlist', 'tag', 'arg', 'epytext', 'section'):
        return childstr
    else:
        # Assume that anything else is colorizing.
        return '<'+tree.tagName+'>'+childstr+'</'+tree.tagName+'>'


##################################################
## Helper Functions
##################################################

def wordwrap(in_str, indent=0, right=SCRWIDTH):
    """Word-wrap the given string.  Indent the text C{indent} spaces
    on the left, and assume a right margin of C{right}.  C{in_str}
    should not contain any newlines."""
    line_length = right-indent
    out_str = ''
    start = 0
    while (start+line_length+1 < len(in_str)):
        end = in_str.rfind(' ', start, start+line_length+1)
        if end <= 0:
            end = in_str.find(' ', start+1)
        if end <= 0:
            out_str += ' '*indent + in_str[start:len(in_str)] + '\n'
            return out_str
        out_str += ' '*indent + in_str[start:end] + '\n'
        start = end+1
    out_str += ' '*indent + in_str[start:len(in_str)] + '\n'
    return out_str

def to_debug2(elt, indent=0):
    """Pretty-print a DOM representation... Used for debugging"""
    if isinstance(elt, Element):
        if elt.tagName == 'epytext':
            str = ''
            for child in elt.childNodes:
                str += to_debug2(child, indent+2)
            return str.rstrip()
        elif elt.tagName in ('ulist', 'olist', 'fieldlist'):
            li1 = to_debug2(elt.childNodes[0], indent+2)
            ind = (indent-2)/4
            str = ind*' '+'L>' + li1[ind+2:]
            for child in elt.childNodes[1:]:
                str += to_debug2(child, indent+2)
            return str
        elif elt.tagName == 'section':
            str = ''
            for child in elt.childNodes:
                str += to_debug2(child, indent+2)
            return str
        elif elt.tagName == 'li':
            str = indent*' '+'- '
            if elt.childNodes:
                str += to_debug2(elt.childNodes[0], 0)
            else:
                str += '\n'
            if len(str) > (SCRWIDTH-10): str = str[:SCRWIDTH-13]+'...\n'
            for child in elt.childNodes[1:]:
                str += to_debug2(child, indent+2)
            return str
        elif elt.tagName == 'para':
            str = indent*' ' + 'P>'
            for child in elt.childNodes:
                str += to_debug2(child)
            if len(str) > (SCRWIDTH-10): str = str[:SCRWIDTH-13]+'...'
            return str + '\n'
        elif elt.tagName == 'heading':
            return ((indent-2)*' ' + 'SECTION: ' + 
                    to_debug2(elt.childNodes[0]) + '\n')
        elif elt.tagName == 'literalblock':
            lines = elt.childNodes[0].data.split('\n')
            str = ''
            for line in lines:
                str += indent*' ' + 'LIT>' + line + '\n'
            return str
        elif elt.tagName == 'doctestblock':
            lines = elt.childNodes[0].data.split('\n')
            str = ''
            for line in lines:
                str += indent*' ' + 'DTB>' + line + '\n'
            return str
        elif elt.tagName == 'field':
            str = indent*' '+ elt.childNodes[0].childNodes[0].data
            if (len(elt.childNodes) > 1 and
                elt.childNodes[1].tagName == 'arg'):
                str += '(' + elt.childNodes[1].childNodes[0].data
                str += '):\n'
                for child in elt.childNodes[2:]:
                    str += to_debug2(child, indent+2)
            else:
                str += ':\n'
                for child in elt.childNodes[1:]:
                    str += to_debug2(child, indent+2)
            return str
        else: #if elt.tagName in ('code', 'bold', 'italic'):
            str = ''
            for child in elt.childNodes:
                str += ('<'+elt.tagName[0].upper()+'>'+
                        to_debug2(child)+'</'+elt.tagName[0].upper()+'>')
            return str
#        else:
#            return '??'+elt.tagName+'??\n'
    elif isinstance(elt, Text):
        return elt.data

def to_dent(str):
    """
    Replace leading whitespace with INDENTS (») and DEDENTS («).  This 
    really has nothing to do with anything right now, but may be used
    for an EBNF implementation of epytext at some point.. I had no
    better place to put it.
    """
    if str.find(chr(171)) >= 0 or str.find(chr(187)) >= 0:
        raise SyntaxError('string already contains dents')
    old_indent = 0
    out = ''
    for line in str.split('\n'):
        lstrip_line = line.lstrip()
        indent = len(line)-len(lstrip_line)
        if lstrip_line == '':
            out += '\n'
            continue
        while indent > old_indent:
            out += chr(187)
            old_indent += 1
        while indent < old_indent:
            out += chr(171)
            old_indent -= 1
        out += lstrip_line + '\n'
        old_indent = indent
    return out

##################################################
## Top-Level Wrapper function
##################################################

def pparse(str, show_warnings=1, show_errors=1):
    """
    \"Pretty-parse\" the string.
    i.e., parse it and print out warnings and errors.
    """
    errors = []
    warnings = []
    confused = 0
    try:
        val = parse(str, errors, warnings)
    except:
        if errors == []: raise
        else: confused = 1
        
    if not show_warnings: warnings = []
    warnings.sort()
    errors.sort()
    if warnings:
        print '='*SCRWIDTH
        print "WARNINGS"
        print '-'*SCRWIDTH
        for warning in warnings:
            print warning.as_warning()
        print '='*SCRWIDTH
    if errors and show_errors:
        if not warnings: print '='*SCRWIDTH
        print "ERRORS"
        print '-'*SCRWIDTH
        for error in errors:
            print error
        print '='*SCRWIDTH
        if confused:
            raise
            print '(Confused by errors.  Bailing out...)'
    if errors:
        raise SyntaxError('Encountered Errors')
    return val

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
        Return -1 if C{self.linenum<other.linenum}; +1 if
        C{self.linenum>other.linenum}; and 0 if
        C{self.linenum==other.linenum}.  The return value is undefined
        if C{other} is not a ParseError.

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
        self.descr = descr
        self.linenum = linenum + 1
        self.line = line
    
    def _repr(self, typ):
        return (typ+' on line ' + `self.linenum` +
                ' during tokenization:\n'+wordwrap(self.descr, 2) +
                '  ' + `self.line`)

class StructuringError(ParseError):
    """
    A warning or error generated while structuring a formatted
    documentation string.

    @ivar token: The C{Token} where the C{StructuringError} occured.
    @type token: C{Token}
    """
    def __init__(self, descr, token):
        self.descr = descr
        self.token = token
        self.linenum = token.startline + 1

    def _repr(self, typ):
        # Do we want to include the token here?  That might be an
        # entire paragraph!!
        return(typ+' on the ' + self.token.tag + ' at line '
               + `self.linenum` + ' during structuring:\n' +
               wordwrap(self.descr, 2)[:-1])

class ColorizingError(ParseError):
    """
    A warning or error generated while colorizing a paragraph.

    @ivar token: The C{Token} where the C{ColorizingError} occured.
    @type token: C{Token}
    @ivar charnum: The index into the paragraph's contents of the
        character where the C{ColorizingError} occured.
    """
    def __init__(self, descr, token, charnum):
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
        
        return(typ+' colorizing the ' + self.token.tag +
               ' at line ' + `self.linenum` + ':\n' +
               wordwrap(self.descr, 2) + '  ' +
               left+right + '\n  '+ (' '*len(left)) +'^')


##################################################
## Testing
##################################################

test1= \
"""
   asd fasdfasdf
   afasdfasdf::
     sdf sdf sdf AA
     sdf as

     sdf as

   - 1 asdf
   - LIST
      - foo
       - ONE
         TWO

         FOUR
           - THREE
         sdf
       - asdf

   >>> asf
    asf
      sf

   >>> asf
    asdf

   adfas::
       
   asdfasdf asdfd"""

test2 = \
"""
   pre-sectioning paragraph.

   Heading
   =======

     para

   test

   heading
   =======
   
   subheading
   ----------

     >>> print 12
     12

     para2
     
   Heading
   =======
   
   asdf::
     Literal /
            / Block

   I{B{C{multiline}}}
   para

   - lists don't have to be
     indented
     foo
   - multiline list items must have their
     second and subsequent lines indented more
     than the first line.

     Subsequent paragraphs must line up with
     the first paragraph.

   single line para
      - lists may be indented

   - xxxxxxxxxxxx
   xxxxxxxxxxxxxx

   xxxxxxxxxxxxxx
   - xxxxxxxxxxxx

   - xxxxxxxxxxxx
     - xxxxxxxxxx

   - xxxxxxxxxxxx
   - xxxxxxxxxxxx

   How about this: M{x
   - y}.

   Or you could wrap a dash like
   E{-} this.

   You can end a paragraph with two colons like thisE{:}E{:}

   1E{.} It's a number that can start a paragraph with escapes.

   Left brace is tha character C{E{lb}}.
   {color} a{color}
"""

test3 = \
"""
  asdf - asdf
  asdf

  asdf
  - asdf

  This is ugly: EE{lb}lbE{rb}

  So use a literal block::
      E{lb}

"""

ambig_test = \
"""
  Ambiguous
  =========

    - xxxxxxxxxxxxxx
    this is ambiguous: new para or continuation of list item?

    xxxxxxxxxxxx
    - this is ambiguous: new li or continuation of para?

  Unambiguous
  ===========
    - xxxxxxxxxx
      xxxxxxxxxx

    Bullets do not count in C{colored
    - regions}

  Slightly Ambiguous
  ==================
    - xxxxxxxxxx
      - xxxxxxxx

    12. xxxxxxxxxx
    13. xxxxxxxxxx

"""

"""
parameters:
    foo: asdf asd fasd f
    bar: asdf sadf sad f
    baz: asdf klj sdlkjsd
types:
    x --- asdf asdf
    y --- asdf sd
    z --- asfsf
"""

test4 = """
Standard syntax:

- Basic uri U{hello}.
- Basic uri U{http://hello}.
- With a name/target: U{name<target>}
- With a name/target: U{name<URI:target>}
- With a name/target: U{name<URL:target>}
- With a name/target: U{name  <URI:target>}
- With a colorized name/target: L{I{italic} name<target>}
"""

test5="""
Bruce's syntax:

- Basic uri U{hello}.
- Basic uri U{http://hello}.
- With a name/target: U{name|target}
- With a name/target: U{name|  target}
- With a colorized name/target: L{I{italic} name|target}
"""

#def profile_parse():
#    s=open("epytext.test")
#    import profile
#    p=profile.Profile()
#    p.calibrate(10000)
#    p.run("for x in range(100): parse(s)")
#    p.print_stats()

#print eltstruct(pparse(test1))
#print pparse(test2).toxml()
#pparse(test2)
#print to_debug(pparse(open("epytext.test").read(),1,1))
#print to_plaintext(pparse(open("epytext.test").read(),1,1))
#print pparse(open("epytext.test").read(),1,1).getElementsByTagName('field')
if __name__ == '__main__':
    if _VBAR_LINK_SYNTAX:
        print to_plaintext(pparse(test5))
    else:
        print to_plaintext(pparse(test5))
    #print to_epytext(parse(test4))
    #print '='*50
    #print to_debug(parse(test1))
#    print to_debug2(parse(test1))
    #print pparse(Token.__repr__.__doc__).toxml()
    #print to_html(pparse(test2, 0))
#print to_dent(test2)
