import token, symbol, re
from types import *

######################################################################
## AST Matching
######################################################################
# Move this to a different module?

class ASTMatcher:
    DEBUG = 0
    
    def __init__(self, sym=None, tok=None, children=None, varname=None,
                 qmrk=0, star=0):
        if (sym is None) == (tok is None):
            raise ValueError, 'must specify sym or tok'
        self.sym = sym
        self.tok = tok
        self.varname = varname
        self.children = children
        self.qmrk = qmrk
        self.star = star

    def _debug(self, ast, indent):
        s = ' '*indent
        if type(ast) is TupleType:
            if symbol.sym_name.has_key(ast[0]):
                s += symbol.sym_name[ast[0]]
            elif token.tok_name.has_key(ast[0]):
                s += token.tok_name[ast[0]]
        else:
            s += repr(ast)

        s = '%-35s <=> ' % s + ' '*indent
        if self.sym is not None:
            s += symbol.sym_name[self.sym]
        if self.tok is not None:
            s += token.tok_name[self.tok]
        if self.qmrk:
            s += '?'
        if self.star:
            s += '*'
        if self.varname:
            s += ': %s' % self.varname
        print s

    def match(self, ast, vars=None):
        if vars is None: vars = {}
        return self._match(ast, vars, 0), vars

    def _match(self, ast, vars, indent):
        if self.DEBUG: self._debug(ast, indent)
        
        # Did we match successfully?
        match = 1

        # Match tokens (ast leaves)
        if self.tok is not None:
            if type(ast) is not TupleType or ast[0] != self.tok:
                match = 0

        # Match symbols (ast nodes).
        elif self.sym is not None:
            # Check that the AST is a node of the right type.
            if self.sym != -1: # = anything
                if type(ast) is not TupleType or ast[0] != self.sym:
                    match = 0
            
            # Check the children.
            if match and self.children is not None:
                i = 0 # The matcher child index.
                j = 1 # The ast child index.
                while i<len(self.children) and j<len(ast):
                    matcher_child = self.children[i]
                    ast_child = ast[j]

                    if matcher_child._match(ast_child, vars, indent+1):
                        # We matched; advance to the next ast.
                        j += 1
                        # Advance to the next matcher, unless it's *.
                        if not matcher_child.star: i += 1
                    else:
                        # We didn't match; if it's * or ?, then
                        # advance to the next matcher.  Otherwise,
                        # fail.
                        if matcher_child.star or matcher_child.qmrk:
                            i += 1
                        else:
                            match = 0
                            break
                        
                # Check that we matched all ast children.
                if j != len(ast):
                    match = 0

                # Check that we used all matcher children; and bind
                # variables in any remaining star/qmrk children.
                for matcher_child in self.children[i:]:
                    if matcher_child.star or matcher_child.qmrk:
                        matcher_child._bind(None, 0, vars)
                    else:
                        match = 0
                        break

        # Bind variables
        self._bind(ast, match, vars)
        
        if self.DEBUG:
            print '%s<- %s' % (' '*indent, match)
        return match

    def _bind(self, ast, match, vars):
        # Bind variables.
        if self.varname:
            if match:
                if self.sym is not None: value = ast
                if self.tok is not None: value = ast[1]
        
                if self.star:
                    vars.setdefault(self.varname, []).append(value)
                else:
                    vars[self.varname] = value
            else:
                if self.qmrk:
                    vars[self.varname] = None
                if self.star:
                    vars.setdefault(self.varname, [])

_TOKEN_RE = re.compile(r'\s*(%s)\s*' % '|'.join([
    r'(\(\s*(?P<sym>[a-z_]+|[*]))',
    r'(?P<dots>\.\.\.)',
    r'(?P<close>\))',
    r'(?P<tok>[A-Z_]+)',
    r'(:\s*(?P<varname>\w+))',
    r'(?P<mod>[*?])',
    ]))

# This would be a static method in Python 2.2+
def compile_ast_matcher(pattern):
    pattern = pattern.strip()
    stack = []
    pos = 0
    while 1:
        match = _TOKEN_RE.match(pattern, pos)
        if not match:
            errstr = (str(pattern[max(0,pos-20):pos]) +
                      '[*ERROR*]' +
                      str(pattern[pos:pos+20]))
            raise ValueError, 'Bad pattern string\n%r' % errstr
        pos = match.end()

        if match.group('sym') is not None:
            sym_name = match.group('sym')
            if sym_name == '*':
                sym = -1
            else:
                try: sym = getattr(symbol, sym_name)
                except: raise ValueError, 'Bad symbol %r' % sym_name
            stack.append(ASTMatcher(sym=sym, children=[]))

        elif match.group('dots') is not None:
            stack[-1].children = None

        elif match.group('close') is not None:
            if len(stack) == 1:
                if pos != len(pattern):
                    raise ValueError, 'Bad pattern string'
                return stack[0]
            stack[-2].children.append(stack.pop())
            
        elif match.group('tok') is not None:
            tok_name = match.group('tok')
            try: tok = getattr(token, tok_name)
            except: raise ValueError, 'Bad token %r' % tok_name
            tokmatcher = ASTMatcher(tok=tok)
            stack[-1].children.append(tokmatcher)

        elif match.group('varname') is not None:
            lastchild = stack[-1].children[-1]
            lastchild.varname = match.group('varname')
            
        elif match.group('mod') == '*':
            lastchild = stack[-1].children[-1]
            lastchild.star = 1
            
        elif match.group('mod') == '?':
            lastchild = stack[-1].children[-1]
            lastchild.qmrk = 1
            
        else:
            assert 0, 'error in _TOKEN_RE handling'

