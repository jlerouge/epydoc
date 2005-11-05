import tokenize, symbol, re
from types import *

######################################################################
## AST Matching
######################################################################
# Move this to a different module?  (maybe into docparser?)

class ASTMatcher:
    DEBUG = 0
    
    def __init__(self, sym=None, tok=None, toktext=None, variables=None, 
                 varname=None, qmrk=0, star=0):
        if (sym is None) == (tok is None):
            raise ValueError, 'must specify sym or tok'
        self.sym = sym
        self.tok = tok
        self.toktext = toktext
        self.varname = varname
        self.variables = variables
        self.qmrk = qmrk
        self.star = star

    def _debug(self, ast, indent):
        s = ' '*indent
        if type(ast) is StringType:
            s += repr(ast)
        else:
            if symbol.sym_name.has_key(ast[0]):
                s += symbol.sym_name[ast[0]]
            elif tokenize.tok_name.has_key(ast[0]):
                s += tokenize.tok_name[ast[0]]

        s = '%-35s <=> ' % s + ' '*indent
        if self.sym is not None:
            if self.sym != -1: s += symbol.sym_name[self.sym]
        if self.tok is not None:
            s += tokenize.tok_name[self.tok]
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
            if type(ast) is StringType or self.tok != ast[0]:
                match = 0
            if self.toktext is not None and self.toktext != ast[1]:
                match = 0

        # Match symbols (ast nodes).
        elif self.sym is not None:
            # Check that the AST is a node of the right type.
            if self.sym != -1: # = anything
                if type(ast) is StringType or ast[0] != self.sym:
                    match = 0
            
            # Check the variables.
            if match:
                i = 0 # The matcher child index.
                j = 1 # The ast child index.
                while i<len(self.variables) and j<len(ast):
                    matcher_child = self.variables[i]
                    ast_child = ast[j]

                    # If matcher_child is None ('...'), then ignore
                    # the remaining variables.
                    if matcher_child is None:
                        i = len(self.variables)
                        j = len(ast)
                        break

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
                        
                # Check that we matched all ast variables.
                if j != len(ast):
                    match = 0

                # Check that we used all matcher variables; and bind
                # variables in any remaining star/qmrk variables.
                for matcher_child in self.variables[i:]:
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

    def __repr__(self):
        if self.sym is not None:
            s = '(%s' % symbol.sym_name.get(self.sym, '')
            if self.variables is None:
                s += '...)'
            elif self.variables == []:
                s += ')'
            else:
                s += ' ' + ' '.join([`c` for c in self.variables]) + ')'
        
        else:
            s = tokenize.tok_name[self.tok]

        # Add on any modifiers/bindings.
        if self.qmrk: s += '?'
        if self.star: s += '*'
        if self.varname: s += ':%s' % self.varname

        return s

_TOKEN_RE = re.compile(r'\s*(%s)\s*' % '|'.join([
    r'(\(\s*(?P<sym>[a-z_]*))',
    r'(?P<dots>\.\.\.)',
    r'(?P<close>\))',
    r'(?P<tok>[A-Z_]+)',
    r'(?P<toktext>\'[^\']*\'|\"[^\"]*")',
    r'(:\s*(?P<varname>\w+))',
    r'(?P<mod>[*?])',
    ]))

# This would be a static method in Python 2.2+
def compile_ast_matcher(pattern):
    pattern = ' '.join(pattern.strip().split())
    stack = []
    pos = 0
    while 1:
        match = _TOKEN_RE.match(pattern, pos)
        if not match:
            _pattern_error(pattern, pos)
        pos = match.end()

        if match.group('sym') is not None:
            sym_name = match.group('sym')
            if sym_name == '':
                sym = -1
            else:
                try: sym = getattr(symbol, sym_name)
                except:
                    # hack for backwards compatibility:
                    if sym_name == 'decorators': sym = 'py24sym'
                    else: _pattern_error(pattern, match.start('sym'),
                                         'unknown symbol')
                    
            stack.append(ASTMatcher(sym=sym, variables=[]))

        elif match.group('dots') is not None:
            stack[-1].variables.append(None)

        elif match.group('close') is not None:
            if None in stack[-1].variables[:-1]:
                raise ValueError('Bad pattern: "..." must be the final elt')

            if len(stack) == 1:
                if pos != len(pattern):
                    _pattern_error(pattern, pos)
                stack[0].pattern = pattern # Record the pattern
                return stack[0]
            stack[-2].variables.append(stack.pop())
            
        elif match.group('tok') is not None:
            tok_name = match.group('tok')
            try: tok = getattr(tokenize, tok_name)
            except: _pattern_error(pattern, match.start('tok'),
                                   'unknown token')
            tokmatcher = ASTMatcher(tok=tok)
            stack[-1].variables.append(tokmatcher)

        elif match.group('toktext') is not None:
            toktext = match.group('toktext')[1:-1] # strip quotes.
            tokmatcher = ASTMatcher(tok=tokenize.NAME, toktext=toktext)
            stack[-1].variables.append(tokmatcher)

        elif match.group('varname') is not None:
            lastchild = stack[-1].variables[-1]
            lastchild.varname = match.group('varname')
            
        elif match.group('mod') == '*':
            lastchild = stack[-1].variables[-1]
            lastchild.star = 1
            
        elif match.group('mod') == '?':
            lastchild = stack[-1].variables[-1]
            lastchild.qmrk = 1

        else:
            assert 0, 'internal error: bad _TOKEN_RE'

def _pattern_error(pattern, pos, msg='Bad pattern string'):
    left = min(30, pos)
    raise ValueError('Bad pattern: %s\n  ..."%s"...\n      %s^' %
                     (msg, pattern[pos-left:pos+30], ' '*left))
