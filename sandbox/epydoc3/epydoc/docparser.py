import symbol
import os.path
import apidoc; reload(apidoc); from apidoc import *
import astmatcher; reload(astmatcher); from astmatcher import *
from types import *

######################################################################
## Doc Parser
######################################################################

class DocParser:
    def __init__(self, apidoc_graph):
        self._apidoc_graph = apidoc_graph
        
        self.context = None
        """Where are we in the tree right now?
        @type: L{DottedName}"""

        self.context2 = None
        """What vardoc are we editing right now?
        """

    def parse(self, filename):
        # Find the basedir of the package & the full module name.
        (basedir, module_name) = _find_module_from_filename(filename)

        # Look up the module's existing documentation, or create it if
        # it doesn't have any yet.
        moduledoc = self._apidoc_graph.get(module_name)
        if moduledoc is None:
            moduledoc = ModuleDoc()
            self._apidoc_graph[module_name] = moduledoc

        # Set the context.
        self.context = module_name

        # Read the source code & parse it into a syntax tree.
        try:
            source_code = open(filename).read()
            ast = parser.suite(source_code.replace('\r\n','\n')+'\n')
            ast = ast.totuple()
        except:
            return # Couldn't parse it!

        # Start parsing!
        #print pp_ast(ast)
        self.parse_suite(ast)

    #////////////////////////////////////////////////////////////
    # Suite/Statement Parsing
    #////////////////////////////////////////////////////////////
     
    STMT_PATTERNS = {
        'import': compile_ast_matcher("""
            (stmt
             (simple_stmt
              (small_stmt (import_stmt...):import) NEWLINE))"""),
        'assign': compile_ast_matcher("""
            (stmt
             (simple_stmt
              (small_stmt (expr_stmt (testlist...):lhs
                                     EQUAL
                                     (*...):rhs)) NEWLINE))"""),
        'funcdef': compile_ast_matcher("""
            (stmt (compound_stmt (funcdef
                NAME:def
                NAME:funcname
                (parameters ...):parameters
                COLON
                (suite ...): body)))"""),
        'classdef': compile_ast_matcher("""
            (stmt (compound_stmt (classdef
                NAME:class
                NAME:classname
                LPAR? (testlist...)?:bases RPAR?
                COLON
                (suite ...):body)))"""),
        }

    def parse_suite(self, ast):
        assert ast[0] in (symbol.file_input, symbol.suite)
        for stmt in ast[1:]:
            for (name, matcher) in self.STMT_PATTERNS.items():
                match, vars = matcher.match(stmt)
                if match:
                    parse_method = getattr(self, 'parse_%s' % name)
                    parse_method(stmt, vars)

    #////////////////////////////////////////////////////////////
    # Assignment Statements
    #////////////////////////////////////////////////////////////
     
    def parse_assign(self, ast, vars):
        print 'assign', [k for (k,v) in vars.items() if v]
        print vars
        print
     
    #////////////////////////////////////////////////////////////
    # Import Statements
    #////////////////////////////////////////////////////////////
     
    def parse_import(self, ast, vars):
        print 'import', [k for (k,v) in vars.items() if v]
        print

    #////////////////////////////////////////////////////////////
    # Function definitions
    #////////////////////////////////////////////////////////////

    def parse_funcdef(self, ast, vars):
        print 'funcdef', [k for (k,v) in vars.items() if v]
        print
     
    #////////////////////////////////////////////////////////////
    # Class definitions
    #////////////////////////////////////////////////////////////

    def parse_classdef(self, ast, vars):
        print 'classdef', [k for (k,v) in vars.items() if v]
        # Set our new context.
        self.context = DottedName(self.context, vars['classname'])
        print 'new context', self.context

        # Parse the suite.
        self.parse_suite(vars['body'])

        # Restore our context.
        self.context = DottedName(*self.context[:-1])
     
    #////////////////////////////////////////////////////////////
    # Identifier extraction
    #////////////////////////////////////////////////////////////

    LHS_PATTERN = compile_ast_matcher("""
    (test
     (and_test
      (not_test
       (comparison
        (expr
         (xor_expr
          (and_expr
           (shift_expr
            (arith_expr
             (term
              (factor
               (power
                (atom ...): atom
                (trailer DOT NAME)*: trailers
                ))))))))))))""")

    def lhs_to_idents(self, testlist):
        assert testlist[0] in (symbol.testlist, symbol.listmaker)
        names = []

        # Traverse the AST, looking for variables.
        for test in testlist[1:]:
            match, vars = self.LHS_PATTERN.match(test)
            if match:
                atom = vars['atom']
                trailers = vars['trailers']
                
                # atom: NAME
                if atom[1][0] == token.NAME:
                    idents = [atom[1][1]] + [t[2][1] for t in trailers]
                    names.append(DottedName(*idents))

                # atom: '[' [listmaker] ']'
                elif atom[1][0] == token.LSQB:
                    listmaker = atom[2]
                    names.append(self.lhs_to_idents(listmaker))

                # atom: '(' [testlist] ')'
                elif atom[1][0] == token.LPAR:
                    testlist = atom[2]
                    names.append(self.lhs_to_idents(testlist))

        return names
     
    #////////////////////////////////////////////////////////////
    # Helper Functions
    #////////////////////////////////////////////////////////////

    # Based on http://www.python.org/doc/current/lib/node566.html
    def ast_match(self, pattern, data, vars=None):
        """
        Match C{data} to C{pattern}, with variable extraction.
    
        The C{pattern} value may contain variables of the form
        C{['M{varname}']} which are allowed to match anything.  The
        value that is matched is returned as part of a dictionary
        which maps 'M{varname}' to the matched value.  'M{varname}' is
        not required to be a string object, but using strings makes
        patterns and the code which uses them more readable.

        Variables:
          - ['varname']: match any node or leaf
          - [type, 'varname']: match any node with the given type
          - ['varname', '*']
    
        @return: two values -- a boolean indicating whether a match
        was found and a dictionary mapping variable names to their
        associated values.
        
        @param pattern:
            Pattern to match against, possibly containing variables.
    
        @param data:
            Data to be checked and against which variables are extracted.
    
        @param vars:
            Dictionary of variables which have already been found.  If
            not provided, an empty dictionary is created.
            
        """
        if vars is None:
            vars = {}
        if type(pattern) is types.ListType:  # 'variables' are ['varname']
            if len(pattern) == 1:
                vars[pattern[0]] = data
                return 1, vars
            elif len(pattern) == 2:
                if type(data) is not types.TupleType: return 0, vars
                if pattern[0] != data[0]: return 0, vars
                vars[pattern[1]] = data
                return 1, vars
            else:
                raise ValueError, 'bad pattern variable %r' % pattern
        if type(pattern) is not types.TupleType:
            return (pattern == data), vars
        if len(data) != len(pattern):
            return 0, vars
        for pattern, data in map(None, pattern, data):
            same, vars = self.ast_match(pattern, data, vars)
            if not same:
                break
        return same, vars
        
def _find_module_from_filename(filename):
    """
    Break a module/package filename into a base directory and a module
    name.  C{_find_module_from_filename} checks directories in the
    filename to see if they contain C{"__init__.py"} files; if they
    do, then it assumes that the module is part of a package, and
    returns the full module name.  For example, if C{filename} is
    C{"/tmp/epydoc/imports.py"}, and the file
    C{"/tmp/epydoc/__init__.py"} exists, then the base directory will
    be C{"/tmp/"} and the module name will be C{"epydoc.imports"}.
    
    @return: A pair C{(basedir, module)}, where C{basedir} is the base
        directory from which the module can be imported; and C{module}
        is the name of the module itself.    
    @rtype: C{(string, string)}

    @param filename: The filename that contains the module.
        C{filename} can be a directory (for a package); a C{.py} file;
        a C{.pyc} file; a C{.pyo} file; or an C{.so} file.
    @type filename: C{string}
    """
    # Normalize the filename
    filename = os.path.normpath(os.path.abspath(filename))

    # Split the file into (basedir, module, ext), and check the extension.
    (basedir, file) = os.path.split(filename)
    (module, ext) = os.path.splitext(file)
    if not (ext[-3:] == '.py' or ext[-4:-1] == '.py' or
            ext[-3:] == '.so'):
        raise ImportError('Error importing %r: ' % filename +
                          'not a Python module')

    # Is it a package?
    if module == '__init__':
        (basedir, module) = os.path.split(basedir)
    
    # If there's a package, then find its base directory.
    if (os.path.exists(os.path.join(basedir, '__init__.py')) or
        os.path.exists(os.path.join(basedir, '__init__.pyc')) or
        os.path.exists(os.path.join(basedir, '__init__.pyw'))):
        package = []
        while os.path.exists(os.path.join(basedir, '__init__.py')):
            (basedir,dir) = os.path.split(basedir)
            if dir == '': break
            package.append(dir)
        package.reverse()
        module = '.'.join(package+[module])

    return (basedir, DottedName(module))


def pp_ast(ast, indent=''):
    if isinstance(ast, tuple):
        if symbol.sym_name.has_key(ast[0]):
            s = '(symbol.%s' % symbol.sym_name[ast[0]]
        else:
            s = '(token.%s' % token.tok_name[ast[0]]
        for arg in ast[1:]:
            s += ',\n%s  %s' % (indent, pp_ast(arg, indent+' '))
        return s + ')'
    else:
        return repr(ast)

######################################################################
# Testing
######################################################################

print DocParser(DocCollection()).parse('epydoc_test.py')

