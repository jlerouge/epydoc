#
# doctest.py: Syntax Highlighting for doctest blocks
# Edward Loper
#
# Created [06/28/03 02:52 AM]
# $Id: restructuredtext.py 1210 2006-04-10 13:25:50Z edloper $
#

"""
Syntax highlighting for doctest blocks.  This module defines two
functions, L{doctest_to_html()} and L{doctest_to_latex()}, which can
be used to perform syntax highlighting on doctest blocks.  It also
defines the more general L{colorize_doctest()}, which could be used to
do syntac highlighting on doctest blocks with other output formats.
(Both C{doctest_to_html()} and C{doctest_to_latex()} are defined using
C{colorize_doctest()}.)
"""

import re
from epydoc.util import plaintext_to_html, plaintext_to_latex

def doctest_to_html(s):
    """
    Perform syntax highlighting on the given doctest string, and
    return the resulting HTML code.  This code consists of a C{<pre>}
    block with class=py-doctest.  Syntax highlighting is performed
    using the following css classes: 'py-prompt', 'py-keyword',
    'py-string', 'py-comment', and 'py-output'.
    """
    return ('<pre class="py-doctest">\n%s\n</pre>\n' %
            colorize_doctest(s, _tag_span_html).strip())

def doctest_to_latex(s):
    """
    Perform syntax highlighting on the given doctest string, and
    return the resulting LaTeX code.  This code consists of an
    C{alltt} environment.  Syntax highlighting is performed using five
    new latex commands, which must be defined externally:
    '\pysrcprompt', '\pysrckeyword', '\pysrcstring', '\pysrccomment',
    and '\pysrcoutput'.
    """
    return ('\\begin{alltt}\n%s\n\\end{alltt}\n' % 
            colorize_doctest(s, _tag_span_latex).strip())

def _tag_span_html(s, tag):
    return '<span class="py-%s">%s</span>' % (tag, plaintext_to_html(s))

def _tag_span_latex(s, tag):
    return '\\pysrc%s{%s}' % (tag, plaintext_to_latex(s))

# Regular expressions for colorize_doctestblock
_KEYWORDS = ["del", "from", "lambda", "return", "and", "or", "is", 
             "global", "not", "try", "break", "else", "if", "elif", 
             "while", "class", "except", "import", "pass", "raise",
             "continue", "finally", "in", "print", "def", "for"]
_KEYWORD = '|'.join([r'(\b%s\b)' % _KW for _KW in _KEYWORDS])
_STRING = (r"""
[uU]?[rR]?
  (?:              # Single-quote (') strings
  '''(?:                 # Tripple-quoted can contain...
      [^']               | # a non-quote
      \\'                | # a backslashed quote
      '{1,2}(?!')          # one or two quotes
    )*''' |
  '(?:                   # Non-tripple quoted can contain...
     [^']                | # a non-quote
     \\'                   # a backslashded quote
   )*'(?!') | """+
r'''               # Double-quote (") strings
  """(?:                 # Tripple-quoted can contain...
      [^"]               | # a non-quote
      \\"                | # a backslashed single
      "{1,2}(?!")          # one or two quotes
    )*""" |
  "(?:                   # Non-tripple quoted can contain...
     [^"]                | # a non-quote
     \\"                   # a backslashded quote
   )*"(?!")
)''')
_COMMENT = '(#.*?$)'
_PROMPT = r'^\s*(?:>>>|\.\.\.)(?:\s|$)'

PROMPT_RE = re.compile('(%s)' % _PROMPT, re.MULTILINE | re.DOTALL)
'''The regular expression used to find Python prompts (">>>" and
"...") in doctest blocks.'''

DOCTEST_RE = re.compile(
    '(?P<STRING>%s)|(?P<COMMENT>%s)|(?P<KEYWORD>%s)|(?P<PROMPT>%s)|.+?' %
    (_STRING, _COMMENT, _KEYWORD, _PROMPT), re.MULTILINE | re.DOTALL)
'''The regular expression used by L{_doctest_sub} to colorize doctest
blocks.'''

def colorize_doctest(s, markup_func):
    """
    Colorize the given doctest string C{s} using C{markup_func()}.
    C{markup_func()} should be a function that takes a substring and a
    tag, and returns a colorized version of the substring.  E.g.:

        >>> def html_markup_func(s, tag):
        ...     return '<span class="%s">%s</span>' % (tag, s)

    The tags that will be passed to the markup function are: 
        - C{prompt} -- a Python prompt (>>> or ...)
        - C{keyword} -- a Python keyword (for, if, etc.)
        - C{string} -- a string literal
        - C{comment} -- a comment
        - C{output} -- the output from a doctest block.
        - C{other} -- anything else (does *not* include output.)
    """
    pysrc = [] # the source code part of a docstest block (lines)
    pyout = [] # the output part of a doctest block (lines)
    result = []
    out = result.append

    def subfunc(match):
        if match.group('PROMPT'):
            return markup_func(match.group(), 'prompt')
        if match.group('KEYWORD'):
            return markup_func(match.group(), 'keyword')
        if match.group('COMMENT'):
            return markup_func(match.group(), 'comment')
        if match.group('STRING') and '\n' not in match.group():
            return markup_func(match.group(), 'string')
        elif match.group('STRING'):
            # It's a multiline string; colorize the string & prompt
            # portion of each line.
            pieces = [markup_func(s, ['string','prompt'][i%2])
                      for i, s in enumerate(PROMPT_RE.split(match.group()))]
            return ''.join(pieces)
        else:
            return markup_func(match.group(), 'other')
    
    for line in s.split('\n')+['\n']:
        if PROMPT_RE.match(line):
            pysrc.append(line)
            if pyout:
                result.append(markup_func('\n'.join(pyout).strip(), 'output'))
                pyout = []
        else:
            pyout.append(line)
            if pysrc:
                pysrc = DOCTEST_RE.sub(subfunc, '\n'.join(pysrc))
                result.append(pysrc.strip())
                #result.append(markup_func(pysrc.strip(), 'python'))
                pysrc = []

    remainder = '\n'.join(pyout).strip()
    if remainder:
        result.append(markup_func(remainder, 'output'))
        
    return '\n'.join(result)
