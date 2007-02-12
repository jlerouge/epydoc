# epydoc -- Marked-up Representations for Python Values
#
# Copyright (C) 2005 Edward Loper
# Author: Edward Loper <edloper@loper.org>
# URL: <http://epydoc.sf.net>
#
# $Id: apidoc.py 1448 2007-02-11 00:05:34Z dvarrazzo $

"""
Syntax highlighter for Python values.  Currently provides special
colorization support for:

  - lists, tuples, sets, frozensets, dicts
  - numbers
  - strings
  - compiled regexps

The highlighter also takes care of line-wrapping, and automatically
stops generating repr output as soon as it has exceeded the specified
number of lines (which should make it faster than pprint for large
values).  It does I{not} bother to do automatic cycle detection,
because maxlines is typically around 5, so it's really not worth it.
"""

# Implementation note: we use exact tests for classes (list, etc)
# rather than using isinstance, because subclasses might override
# __repr__.

import types, re
import epydoc.apidoc
from epydoc.util import decode_with_backslashreplace
from epydoc.compat import *
import sre_parse, sre_constants

def is_re_pattern(pyval):
    return type(pyval).__name__ == 'SRE_Pattern'

class _ColorizerState:
    """
    An object uesd to keep track of the current state of the pyval
    colorizer.  The L{mark()}/L{restore()} methods can be used to set
    a backup point, and restore back to that backup point.  This is
    used by several colorization methods that first try colorizing
    their object on a single line (setting linebreakok=False); and
    then fall back on a multi-line output if that fails.
    """
    def __init__(self):
        self.result = []
        self.charpos = 0
        self.lineno = 1
        self.linebreakok = True

    def mark(self):
        return (len(self.result), self.charpos, self.lineno, self.linebreakok)

    def restore(self, mark):
        n, self.charpos, self.lineno, self.linebreakok = mark
        del self.result[n:]

class _Maxlines(Exception):
    """A control-flow exception that is raised when PyvalColorizer
    exeeds the maximum number of allowed lines."""
    
class _Linebreak(Exception):
    """A control-flow exception that is raised when PyvalColorizer
    generates a string containing a newline, but the state object's
    linebreakok variable is False."""


class PyvalColorizer:
    """
    Syntax highlighter for Python values.
    """

    def __init__(self, linelen=75, maxlines=5, sort=True):
        self.linelen = linelen
        self.maxlines = maxlines
        self.sort = sort

    #////////////////////////////////////////////////////////////
    # Subclassing Hooks
    #////////////////////////////////////////////////////////////

    PREFIX = None
    """A string sequence that should be added to the beginning of all
        colorized pyval outputs."""
    
    SUFFIX = None
    """A string sequence that should be added to the beginning of all
        colorized pyval outputs."""
    
    NEWLINE = '\n'
    """The string sequence that should be generated to encode newlines."""
    
    LINEWRAP = None
    """The string sequence that should be generated when linewrapping a
       string that is too long to fit on a single line.  (The
       NEWLINE sequence will be added immediately after this sequence)"""
    
    ELLIPSIS = None
    """The string sequence that should be generated when omitting the
       rest of the repr because maxlines has been exceeded."""
    
    def markup(self, s, tag=None):
        """
        Apply syntax highlighting to a single substring from a Python
        value representation.  C{s} is the substring, and C{tag} is
        the tag that should be applied to the substring.  C{tag} will
        be one of the following strings:

          - (list under construction)
        """

    #////////////////////////////////////////////////////////////
    # Colorization Tags
    #////////////////////////////////////////////////////////////

    GROUP_TAG = 'val-group'     # e.g., "[" and "]"
    COMMA_TAG = 'val-op'        # The "," that separates elements
    COLON_TAG = 'val-op'        # The ":" in dictionaries
    CONST_TAG = None            # None, True, False
    NUMBER_TAG = None           # ints, floats, etc
    QUOTE_TAG = 'val-quote'     # Quotes around strings.
    STRING_TAG = 'val-string'   # Body of string literals

    RE_CHAR_TAG = None
    RE_GROUP_TAG = 're-group'
    RE_REF_TAG = 're-ref'
    RE_OP_TAG = 're-op'
    RE_FLAGS_TAG = 're-flags'
    
    #////////////////////////////////////////////////////////////
    # Entry Point
    #////////////////////////////////////////////////////////////

    def colorize(self, pyval):
        # Create an object to keep track of the colorization.
        state = _ColorizerState()
        # Add the prefix string.
        state.result.append(self.PREFIX)
        # Colorize the value.  If we reach maxlines, then add on an
        # ellipsis marker and call it a day.
        try:
            self._colorize(pyval, state)
        except _Maxlines:
            state.result.append(self.ELLIPSIS)
        # Add on the suffix string.
        state.result.append(self.SUFFIX)
        # Put it all together.
        return ''.join(state.result)

    def _colorize(self, pyval, state):
        pyval_type = type(pyval)

        if pyval is None or pyval is True or pyval is False:
            self._output(str(pyval), self.CONST_TAG, state)
        elif pyval_type in (int, float, long, types.ComplexType):
            self._output(str(pyval), self.NUMBER_TAG, state)
        elif pyval_type is str:
            self._colorize_str(pyval, state, '', 'string-escape')
        elif pyval_type is unicode:
            self._colorize_str(pyval, state, 'u', 'unicode-escape')
        elif pyval_type is list:
            self._multiline(self._colorize_iter, pyval, state, '[', ']')
        elif pyval_type is tuple:
            self._multiline(self._colorize_iter, pyval, state, '(', ')')
        elif pyval_type is set:
            if self.sort: pyval = sorted(pyval)
            self._multiline(self._colorize_iter, pyval, state,
                            'set([', '])')
        elif pyval_type is frozenset:
            if self.sort: pyval = sorted(pyval)
            self._multiline(self._colorize_iter, pyval, state,
                            'frozenset([', '])')
        elif pyval_type is dict:
            items = pyval.items()
            if self.sort: items = sorted(items)
            self._multiline(self._colorize_dict, items, state, '{', '}')
        elif is_re_pattern(pyval):
            self._colorize_re(pyval, state)
        else:
            self._output(repr(pyval), None, state)
        
    #////////////////////////////////////////////////////////////
    # Object Colorization Functions
    #////////////////////////////////////////////////////////////

    def _multiline(self, func, pyval, state, *args):
        """
        Helper for container-type colorizers.  First, try calling
        C{func(pyval, state, *args)} with linebreakok set to false;
        and if that fails, then try again with it set to true.
        """
        linebreakok = state.linebreakok
        mark = state.mark()
        
        try:
            state.linebreakok = False
            func(pyval, state, *args)
            state.linebreakok = linebreakok

        except _Linebreak:
            if not linebreakok:
                raise
            state.restore(mark)
            func(pyval, state, *args)
            
    def _colorize_iter(self, pyval, state, prefix, suffix):
        self._output(prefix, self.GROUP_TAG, state)
        indent = state.charpos
        for i, elt in enumerate(pyval):
            if i>=1:
                if state.linebreakok:
                    self._output(',', self.COMMA_TAG, state)
                    self._output('\n'+' '*indent, None, state)
                else:
                    self._output(', ', self.COMMA_TAG, state)
            self._colorize(elt, state)
        self._output(suffix, self.GROUP_TAG, state)

    def _colorize_dict(self, items, state, prefix, suffix):
        self._output(prefix, self.GROUP_TAG, state)
        indent = state.charpos
        for i, (key, val) in enumerate(items):
            if i>=1:
                if state.linebreakok:
                    self._output(',', self.COMMA_TAG, state)
                    self._output('\n'+' '*indent, None, state)
                else:
                    self._output(', ', self.COMMA_TAG, state)
            self._colorize(key, state)
            self._output(': ', self.COLON_TAG, state)
            self._colorize(val, state)
        self._output(suffix, self.GROUP_TAG, state)

    def _colorize_str(self, pyval, state, prefix, encoding):
        # Decide which quote to use.
        if '\n' in pyval: quote = "'''"
        else: quote = "'"
        # Open quote.
        self._output(prefix+quote, self.QUOTE_TAG, state)
        # Body
        for i, line in enumerate(pyval.split('\n')):
            if i>0: self._output('\n', None, state)
            self._output(line.encode(encoding), self.STRING_TAG, state)
        # Close quote.
        self._output(quote, self.QUOTE_TAG, state)

    def _colorize_re(self, pyval, state):
        # Extract the flag & pattern from the regexp.
        pat, flags = pyval.pattern, pyval.flags
        # If the pattern is a string, decode it to unicode.
        if isinstance(pat, str):
            pat = decode_with_backslashreplace(pat)
        # Parse the regexp pattern.
        tree = sre_parse.parse(pat, flags)
        groups = dict([(num,name) for (name,num) in
                       tree.pattern.groupdict.items()])
        # Colorize it!
        self._colorize_re_flags(tree.pattern.flags, state)
        self._colorize_re_tree(tree, state, True, groups)

    def _colorize_re_flags(self, flags, state):
        if flags:
            flags = [c for (c,n) in sorted(sre_parse.FLAGS.items())
                     if (n&flags)]
            flags = '(?%s)' % ''.join(flags)
            self._output(flags, self.RE_FLAGS_TAG, state)

    def _colorize_re_tree(self, tree, state, noparen, groups):
        assert noparen in (True, False)
        if len(tree) > 1 and not noparen:
            self._output('(', self.RE_GROUP_TAG, state)
        for elt in tree:
            op = elt[0]
            args = elt[1]
    
            if op == sre_constants.LITERAL:
                c = unichr(args)
                # Add any appropriate escaping.
                if c in '.^$\\*+?{}[]|()': c = '\\'+c
                elif c == '\t': c = '\\t'
                elif c == '\r': c = '\\r'
                elif c == '\n': c = '\\n'
                elif c == '\f': c = '\\f'
                elif c == '\v': c = '\\v'
                elif ord(c) > 0xffff: c = r'\U%08x' % ord(c)
                elif ord(c) > 0xff: c = r'\u%04x' % ord(c)
                elif ord(c)<32 or ord(c)>=127: c = r'\x%02x' % ord(c)
                self._output(c, self.RE_CHAR_TAG, state)
            
            elif op == sre_constants.ANY:
                self._output('.', self.RE_CHAR_TAG, state)
                
            elif op == sre_constants.BRANCH:
                if args[0] is not None:
                    raise ValueError('Branch expected None arg but got %s'
                                     % args[0])
                for i, item in enumerate(args[1]):
                    if i > 0:
                        self._output('|', self.RE_OP_TAG, state)
                    self._colorize_re_tree(item, state, True, groups)
                
            elif op == sre_constants.IN:
                if (len(args) == 1 and args[0][0] == sre_constants.CATEGORY):
                    self._colorize_re_tree(args, state, False, groups)
                else:
                    self._output('[', self.RE_GROUP_TAG, state)
                    self._colorize_re_tree(args, state, True, groups)
                    self._output(']', self.RE_GROUP_TAG, state)
                    
            elif op == sre_constants.CATEGORY:
                if args == sre_constants.CATEGORY_DIGIT: val = r'\d'
                elif args == sre_constants.CATEGORY_NOT_DIGIT: val = r'\D'
                elif args == sre_constants.CATEGORY_SPACE: val = r'\s'
                elif args == sre_constants.CATEGORY_NOT_SPACE: val = r'\S'
                elif args == sre_constants.CATEGORY_WORD: val = r'\w'
                elif args == sre_constants.CATEGORY_NOT_WORD: val = r'\W'
                else: raise ValueError('Unknown category %s' % args)
                self._output(val, self.RE_CHAR_TAG, state)
                
            elif op == sre_constants.AT:
                if args == sre_constants.AT_BEGINNING_STRING: val = r'\A'
                elif args == sre_constants.AT_BEGINNING: val = r'^'
                elif args == sre_constants.AT_END: val = r'$'
                elif args == sre_constants.AT_BOUNDARY: val = r'\b'
                elif args == sre_constants.AT_NON_BOUNDARY: val = r'\B'
                elif args == sre_constants.AT_END_STRING: val = r'\Z'
                else: raise ValueError('Unknown position %s' % args)
                self._output(val, self.RE_CHAR_TAG, state)
                
            elif op in (sre_constants.MAX_REPEAT, sre_constants.MIN_REPEAT):
                minrpt = args[0]
                maxrpt = args[1]
                if maxrpt == sre_constants.MAXREPEAT:
                    if minrpt == 0:   val = '*'
                    elif minrpt == 1: val = '+'
                    else: val = '{%d,}' % (minrpt)
                elif minrpt == 0:
                    if maxrpt == 1: val = '?'
                    else: val = '{,%d}' % (maxrpt)
                elif minrpt == maxrpt:
                    val = '{%d}' % (maxrpt)
                else:
                    val = '{%d,%d}' % (minrpt, maxrpt)
                if op == sre_constants.MIN_REPEAT:
                    val += '?'
                    
                self._colorize_re_tree(args[2], state, False, groups)
                self._output(val, self.RE_OP_TAG, state)
                
            elif op == sre_constants.SUBPATTERN:
                if args[0] is None:
                    self._output('(?:', self.RE_GROUP_TAG, state)
                elif args[0] in groups:
                    self._output('(?P<', self.RE_GROUP_TAG, state)
                    self._output(groups[args[0]], self.RE_REF_TAG, state)
                    self._output('>', self.RE_GROUP_TAG, state)
                elif isinstance(args[0], (int, long)):
                    # This is cheating:
                    self._output('(', self.RE_GROUP_TAG, state)
                else:
                    self._output('(?P<', self.RE_GROUP_TAG, state)
                    self._output(args[0], self.RE_REF_TAG, state)
                    self._output('>', self.RE_GROUP_TAG, state)
                self._colorize_re_tree(args[1], state, True, groups)
                self._output(')', self.RE_GROUP_TAG, state)
    
            elif op == sre_constants.GROUPREF:
                self._output('\\%d' % args, self.RE_REF_TAG, state)
    
            elif op == sre_constants.RANGE:
                self._colorize_re_tree( ((sre_constants.LITERAL, args[0]),),
                                        state, False, groups )
                self._output('-', self.RE_OP_TAG, state)
                self._colorize_re_tree( ((sre_constants.LITERAL, args[1]),),
                                        state, False, groups )
                
            elif op == sre_constants.NEGATE:
                self._output('^', self.RE_OP_TAG, state)
    
            elif op == sre_constants.ASSERT:
                if args[0] > 0:
                    self._output('(?=', self.RE_GROUP_TAG, state)
                else:
                    self._output('(?<=', self.RE_GROUP_TAG, state)
                self._colorize_re_tree(args[1], state, True, groups)
                self._output(')', self.RE_GROUP_TAG, state)
                               
            elif op == sre_constants.ASSERT_NOT:
                if args[0] > 0:
                    self._output('(?!', self.RE_GROUP_TAG, state)
                else:
                    self._output('(?<!', self.RE_GROUP_TAG, state)
                self._colorize_re_tree(args[1], state, True, groups)
                self._output(')', self.RE_GROUP_TAG, state)
    
            elif op == sre_constants.NOT_LITERAL:
                self._output('[^', self.RE_GROUP_TAG, state)
                self._colorize_re_tree( ((sre_constants.LITERAL, args),),
                                        state, False, groups )
                self._output(']', self.RE_GROUP_TAG, state)
            else:
                log.error("Error colorizing regexp: unknown elt %r" % elt)
        if len(tree) > 1 and not noparen: 
            self._output(')', self.RE_GROUP_TAG, state)
                           
    #////////////////////////////////////////////////////////////
    # Output function
    #////////////////////////////////////////////////////////////

    def _output(self, s, tag, state):
        """
        Add the string `s` to the result list, tagging its contents
        with tag `tag`.  Any lines that go beyond `self.linelen` will
        be line-wrapped.  If the total number of lines exceeds
        `self.maxlines`, then raise a `_Maxlines` exception.
        """
        if '\n' in s and not state.linebreakok:
            raise _Linebreak()
        
        # Split the string into segments.  The first segment is the
        # content to add to the current line, and the remaining
        # segments are new lines.
        segments = s.split('\n')

        for i, segment in enumerate(segments):
            # If this isn't the first segment, then add a newline to
            # split it from the previous segment.
            if i > 0:
                if not state.linebreakok:
                    raise _Linebreak()
                state.result.append(self.NEWLINE)
                state.lineno += 1
                state.charpos = 0
                if state.lineno > self.maxlines:
                    raise _Maxlines()

            # If the segment fits on the current line, then just call
            # markup to tag it, and store the result.
            if state.charpos + len(segment) <= self.linelen:
                state.result.append(self.markup(segment, tag))
                state.charpos += len(segment)

            # If the segment doesn't fit on the current line, then
            # line-wrap it, and insert the remainder of the line into
            # the segments list that we're iterating over.
            else:
                split = self.linelen-state.charpos
                state.result += [self.markup(segment[:split], tag),
                                 self.LINEWRAP]
                segments.insert(i+1, segment[split:])

class HTMLPyvalColorizer(PyvalColorizer):
    NEWLINE = '\n'
    PREFIX = SUFFIX = ''
    LINEWRAP = (r'<span class="variable-linewrap">'
                '<img src="crarr.png" alt="\" /></span>')
    ELLIPSIS = r'<span class="variable-ellipsis">...</span>'
    def markup(self, s, tag=None):
        s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        if tag:
            return '<span class="variable-%s">%s</span>' % (tag, s)
        else:
            return s

class XMLPyvalColorizer(PyvalColorizer):
    NEWLINE = '\n'
    PREFIX = '<pyval>'
    SUFFIX = '</pyval>'
    LINEWRAP = '<linewrap />'
    ELLIPSIS = '<ellipsis />'
    def markup(self, s, tag=None):
        s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        if tag:
            return '<%s>%s</%s>' % (tag, s, tag)
        else:
            return s
