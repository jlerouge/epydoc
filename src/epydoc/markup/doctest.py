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
# set of keywords as listed in the Python Language Reference 2.4.1
# added 'as' as well since IDLE already colorizes it as a keyword.
# The documentation states that 'None' will become a keyword
# eventually, but IDLE currently handles that as a builtin.
_KEYWORDS = """
and       del       for       is        raise    
assert    elif      from      lambda    return   
break     else      global    not       try      
class     except    if        or        while    
continue  exec      import    pass      yield    
def       finally   in        print
as
""".split()
_KEYWORD = '|'.join([r'\b%s\b' % _KW for _KW in _KEYWORDS])

_BUILTINS = [_BI for _BI in dir(__builtins__) if not _BI.startswith('__')]
_BUILTIN = '|'.join([r'\b%s\b' % _BI for _BI in _BUILTINS])

_STRING = '|'.join([r'("""("""|.*?((?!").)"""))', r'("("|.*?((?!").)"))',
                    r"('''('''|.*?[^\\']'''))", r"('('|.*?[^\\']'))"])
_COMMENT = '(#.*?$)'
_PROMPT1 = r'^\s*>>>(?:\s|$)'
_PROMPT2 = r'^\s*\.\.\.(?:\s|$)'

PROMPT_RE = re.compile('(%s|%s)' % (_PROMPT1, _PROMPT2),
		       re.MULTILINE | re.DOTALL)
PROMPT2_RE = re.compile('(%s)' % _PROMPT2, re.MULTILINE | re.DOTALL)
'''The regular expression used to find Python prompts (">>>" and
"...") in doctest blocks.'''

EXCEPT_RE = re.compile(r'(.*)(^Traceback \(most recent call last\):.*)',
                       re.DOTALL | re.MULTILINE)

DOCTEST_DIRECTIVE_RE = re.compile(r'#\s*doctest:.*')

DOCTEST_RE = re.compile(r"""(?P<STRING>%s)|(?P<COMMENT>%s)|"""
                        r"""(?P<KEYWORD>(%s))|(?P<BUILTIN>(%s))|"""
                        r"""(?P<PROMPT1>%s)|(?P<PROMPT2>%s)|.+?""" %
  (_STRING, _COMMENT, _KEYWORD, _BUILTIN, _PROMPT1, _PROMPT2),
  re.MULTILINE | re.DOTALL)
'''The regular expression used by L{_doctest_sub} to colorize doctest
blocks.'''

def colorize_doctest(s, markup_func, inline=False, strip_directives=False):
    """
    Colorize the given doctest string C{s} using C{markup_func()}.
    C{markup_func()} should be a function that takes a substring and a
    tag, and returns a colorized version of the substring.  E.g.:

        >>> def html_markup_func(s, tag):
        ...     return '<span class="%s">%s</span>' % (tag, s)

    The tags that will be passed to the markup function are: 
        - C{prompt} -- the Python PS1 prompt (>>>)
	- C{more} -- the Python PS2 prompt (...)
        - C{keyword} -- a Python keyword (for, if, etc.)
        - C{builtin} -- a Python builtin name (abs, dir, etc.)
        - C{string} -- a string literal
        - C{comment} -- a comment
	- C{except} -- an exception traceback (up to the next >>>)
        - C{output} -- the output from a doctest block.
        - C{other} -- anything else (does *not* include output.)
    """
    pysrc = [] # the source code part of a docstest block (lines)
    pyout = [] # the output part of a doctest block (lines)
    result = []
    out = result.append

    if strip_directives:
        s = DOCTEST_DIRECTIVE_RE.sub('', s)

    def subfunc(match):
        if match.group('PROMPT1'):
            return markup_func(match.group(), 'prompt')
	if match.group('PROMPT2'):
	    return markup_func(match.group(), 'more')
        if match.group('KEYWORD'):
            return markup_func(match.group(), 'keyword')
        if match.group('BUILTIN'):
            return markup_func(match.group(), 'builtin')
        if match.group('COMMENT'):
            return markup_func(match.group(), 'comment')
        if match.group('STRING') and '\n' not in match.group():
            return markup_func(match.group(), 'string')
        elif match.group('STRING'):
            # It's a multiline string; colorize the string & prompt
            # portion of each line.
            pieces = [markup_func(s, ['string','more'][i%2])
                      for i, s in enumerate(PROMPT2_RE.split(match.group()))]
            return ''.join(pieces)
        else:
            return markup_func(match.group(), 'other')

    if inline:
	pysrc = DOCTEST_RE.sub(subfunc, s)
	return pysrc.strip()

    # need to add a third state here for correctly formatting exceptions

    for line in s.split('\n')+['\n']:
        if PROMPT_RE.match(line):
            pysrc.append(line)
            if pyout:
                pyout = '\n'.join(pyout).strip()
                m = EXCEPT_RE.match(pyout)
                if m:
                    pyout, pyexc = m.group(1).strip(), m.group(2).strip()
                    if pyout:
                        print ('Warning: doctest does not allow for mixed '
                               'output and exceptions!')
                        result.append(markup_func(pyout, 'output'))
                    result.append(markup_func(pyexc, 'except'))
                else:
                    result.append(markup_func(pyout, 'output'))
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
    result = '\n'.join(result)

    # Merge adjacent spans w/ the same class.  I.e, convert:
    #   <span class="x">foo</span><span class="x">foo</span>
    # to:
    #   <span class="x">foofoo</span>
    prev_span_class = [None]
    def subfunc(match):
        if match.group(2) == prev_span_class[0]:
            prev_span_class[0] = match.group(2)
            return match.group(1) or ''
        else:
            prev_span_class[0] = match.group(2)
            return match.group()
    result = re.sub(r'</span>(\n?)<span class="([^"]+)">', subfunc, result)
        
    return result
