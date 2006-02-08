# epydoc -- Source code parsing
#
# Copyright (C) 2005 Edward Loper
# Author: Edward Loper <edloper@loper.org>
# URL: <http://epydoc.sf.net>
#
# $Id$

"""
Extract API documentation about python objects by parsing their source
code.

L{DocParser} is a processing class that reads the Python source code
for one or more modules, and uses it to create L{APIDoc} objects
containing the API documentation for the variables and values defined
in those modules.

C{DocParser} can be subclassed to extend the set of source code
constructions that it supports.
"""
__docformat__ = 'epytext en'

######################################################################
## Imports
######################################################################

# Python source code parsing:
import parser, symbol, token, tokenize, compiler
# Finding modules:
import imp
# File services:
import os, os.path
# API documentation encoding:
from epydoc.apidoc import *
# Syntax tree matching:
from epydoc.astmatcher import compile_ast_matcher
# Type comparisons:
from types import StringType, ListType, TupleType, IntType

######################################################################
## Doc Parser
######################################################################

class DocParser:
    """    
    An API documentation extractor based on source code parsing.
    C{DocParser} reads and parses the Python source code for one or
    more modules, and uses it to create L{APIDoc} objects containing
    the API documentation for the variables and values defined in
    those modules.

    C{DocParser} defines two methods that return L{APIDoc} objects for
    a specified object:
    
      - L{find} - get the documentation for an object with a given
        dotted name.
      - L{parse} - get the documentation for a module with a given
        filename.

    Currently, C{DocParser} extracts documentation from the following
    source code constructions:

      - module docstring
      - import statements
      - class definition blocks
      - function definition blocks
      - assignment statements
        - simple assignment statements
        - assignment statements with multiple C{'='}s
        - assignment statements with unpacked left-hand sides
        - assignment statements that wrap a function in classmethod
          or staticmethod.
        - assignment to special variables __path__, __all__, and
          __docformat__.
      - delete statements

    C{DocParser} does not yet support the following source code
    constructions:
    
      - assignment statements that create properties

    By default, C{DocParser} will expore the contents of top-level
    C{try} and C{if} blocks.  If desired, C{DocParser} can also
    be told to explore the contents of C{while} and C{for} blocks.

    Subclassing
    ===========
    C{DocParser} can be subclassed, to extend the set of source code
    constructions that it supports.  C{DocParser} can be extended in
    several different ways:

      - A subclass can extend the L{STMT_PATTERNS} table with a new
        pattern, and add a handler method to handle the new pattern.

      - A subclass can override one of the existing handler methods
        with a new handler that handles a special case itself, and
        delegates all other cases to the original handler.

      - A subclass can override one of the existing handler methods
        with a new handler that calls the original handler, and
        modifies its output.

      - A subclass can override various helper methods, such as
        L{rhs_to_valuedoc}, to customize the behavior of the handler
        methods.

    @group Entry Points: find, parse
    
    @group Configuration Constants: PARSE_*, IMPORT_HANDLING,
        IMPORT_STAR_HANDLING
    @group Dispatch Tables: STMT_PATTERNS
    @group AST Matchers: *_PATTERN
    """
    def __init__(self, builtins_moduledoc):
        """
        Construct a new C{DocParser}.

        @param builtins_moduledoc: A C{ModuleDoc} for C{__builtins__},
        which is used when builtin objects are referenced by a
        module's code (e.g., if C{object} is used as a base class).
        @type builtins_moduledoc: L{ModuleDoc}
        """
        
        self.context = None
        """The dotted name of the documentation block containing the
        current parse tree node.  E.g., if we're inside the class
        definition for C{A} in module C{m}, then C{context} is
        C{DottedName(m.A)}.
        @type: L{DottedName}"""
        
        self.parentdocs = []
        """A stack of the C{APIDoc}s for the documentation blocks
        containing the current parse tree node.  E.g., if we're inside
        the class definition for C{A} in module C{m}, then
        C{parentdocs[0]} is the C{ModuleDoc} for C{m}; and
        C{parentdocs[1]} is the C{ClassDoc} for C{m.A}.  The direct
        parent for the current parse tree node is always
        C{parentdocs[-1]}.
        @type: C{list} of L{APIDoc}"""

        self.builtins_moduledoc = builtins_moduledoc
        """A C{ModuleDoc} for C{__builtins__}, which is used whenever
        builtin objects are referenced by a module's code (e.g., if
        C{object} is used as a base class).
        @type: L{ModuleDoc}"""

        self.moduledoc_cache = {}
        """A cache of C{ModuleDoc}s that we've already created.  Dict
        from filename to ModuleDoc."""

        self.docstring_info = {}
        """A dictionary used to record the contents and line numbers
        of docstrings, attribute docstrings, and comment docstrings
        for the source tree that is currently being parsed.  This
        dictionary's keys are python ids identifying nodes in the
        parse tree; and its values are tuples C{(docstring, lineno)},
        where C{docstring} is the docstring for that node; and
        C{lineno} is the line number where that docstring begins.
        """

    #////////////////////////////////////////////////////////////
    # Configuration Constants
    #////////////////////////////////////////////////////////////

    PARSE_TRY_BLOCKS = True
    """Should the contents of C{try} blocks be examined?"""
    PARSE_EXCEPT_BLOCKS = True
    """Should the contents of C{except} blocks be examined?"""
    PARSE_FINALLY_BLOCKS = True
    """Should the contents of C{finally} blocks be examined?"""
    PARSE_IF_BLOCKS = True
    """Should the contents of C{if} blocks be examined?"""
    PARSE_ELSE_BLOCKS = True
    """Should the contents of C{else} and C{elif} blocks be examined?"""
    PARSE_WHILE_BLOCKS = False
    """Should the contents of C{while} blocks be examined?"""
    PARSE_FOR_BLOCKS = False
    """Should the contents of C{for} blocks be examined?"""

    IMPORT_HANDLING = 'link'
    """What should the C{DocParser} do when it encounters an import
    statement?
      - C{'link'}: Create valuedoc objects with imported_from pointers
        to the source object.
      - C{'parse'}: Parse the imported file, to find the actual
        documentation for the imported object.  (This will fall back
        to the 'link' behavior if the imported file can't be parsed,
        e.g., if it's a builtin.)
    """

    IMPORT_STAR_HANDLING = 'parse'
    """When C{DocParser} encounters a C{'from M{m} import *'}
    statement, and is unable to parse C{M{m}} (either because
    L{IMPORT_HANDLING}=C{'link'}, or because parsing failed), how
    should it determine the list of identifiers expored by C{M{m}}?
      - C{'ignore'}: ignore the import statement, and don't create
        any new variables.
      - C{'parse'}: parse it to find a list of the identifiers that it
        exports.  (This will fall back to the 'ignore' behavior if the
        imported file can't be parsed, e.g., if it's a builtin.)
      - C{'inspect'}: import the module and inspect it (using C{dir})
        to find a list of the identifiers that it exports.  (This will
        fall back to the 'ignore' behavior if the imported file can't
        be parsed, e.g., if it's a builtin.)
    """

    DEFAULT_DECORATOR_BEHAVIOR = 'passthrough'
    """When C{DocParse} encounters an unknown decorator, what should
    it do to the documentation of the decorated function?
      - C{'passthrough'}: leave the function's documentation as-is.
      - C{'erasedocs'}: replace the function's documentation with an
        empty C{ValueDoc} object, reflecting the fact that we have no
        knowledge about what value the decorator returns.
    """

    COMMENT_MARKER = '#: '
    """The prefix used to mark comments that contain attribute
    docstrings for variables."""

    #////////////////////////////////////////////////////////////
    # Entry point
    #////////////////////////////////////////////////////////////

    def find(self, name):
        """
        Return a L{ValueDoc} object containing the API documentation
        for the object with the given name.
        """
        name = DottedName(name)
        
        # Check if it's a builtin.
        if (len(name) == 1 and
            name[0] in self.builtins_moduledoc.variables):
            var_doc = self.builtins_moduledoc.variables[name[0]]
            return var_doc.value

        # Otherwise, try importing it.
        else:
            return self._find(name)

    def _find(self, name, package_doc=None):
        """
        Return the API documentaiton for the object whose name is
        C{name}.  C{package_doc}, if specified, is the API
        documentation for the package containing the named object.
        """
        # If we're inside a package, then find the package's path.
        if package_doc is None:
            path = None
        else:
            try:
                path_ast = module_doc.variables['__path__'].value.ast
                path = self.extract_string_list(path_ast)
            except:
                path = [os.path.split(package_doc.filename)[0]]

        # The leftmost identifier in `name` should be a module or
        # package on the given path; find it and parse it.
        try: filename = self._get_filename(name[0], path)
        except ImportError: raise ValueError('Could not find value')
        module_doc = self.parse(filename, package_doc)

        # If the name just has one identifier, then the module we just
        # parsed is the object we're looking for; return it.
        if len(name) == 1: return module_doc

        # Otherwise, we're looking for something inside the module.
        # First, check to see if it's in a variable.
        if name[1] in module_doc.variables:
            return self._find_in_namespace(DottedName(*name[1:]), module_doc)

        # If not, then check to see if it's in a subpackage.
        elif re.match(r'__init__.py\w?', os.path.split(filename)[1]):
            return self._find(DottedName(*name[1:]), module_doc)

        # If it's not in a variable or a subpackage, then we can't
        # find it.
        else:
            raise ValueError('Could not find value')
        
    def _find_in_namespace(self, name, namespace_doc):
        # Look up the variable in the namespace.
        var_doc = namespace_doc.variables[name[0]]
        if var_doc.value is UNKNOWN:
            raise ValueError('Could not find value')
        val_doc = var_doc.value

        # If the variable's value was imported, then follow its
        # alias link.
        if val_doc.imported_from not in (None, UNKNOWN):
            return self._find(DottedName(val_doc.imported_from, *name[1:]))

        # Otherwise, if the name has one identifier, then this is the
        # value we're looking for; return it.
        elif len(name) == 1:
            return val_doc

        # Otherwise, if this value is a namespace, look inside it.
        elif isinstance(val_doc, NamespaceDoc):
            return self._find_in_namespace(DottedName(*name[1:]), val_doc)

        # Otherwise, we ran into a dead end.
        else:
            raise ValueError('Could not find value')
        
    def _get_filename(self, identifier, path=None):
        file, filename, (s,m,typ) = imp.find_module(identifier, path)
        try: file.close()
        except: pass

        if typ == imp.PY_SOURCE:
            return filename
        elif typ == imp.PY_COMPILED:
            # See if we can find a corresponding non-compiled version.
            filename = re.sub('.py\w$', '.py', filename)
            if not os.path.exists(filename):
                raise ImportError, 'No Python source file found.'
            return filename
        elif typ == imp.PKG_DIRECTORY:
            filename = os.path.join(filename, '__init__.py')
            if not os.path.exists(filename):
                filename = os.path.join(filename, '__init__.pyw')
                if not os.path.exists(filename):
                    raise ImportError, 'No package file found.'
            return filename
        elif typ == imp.C_BUILTIN:
            raise ImportError, 'No Python source file for builtins.'
        elif typ == imp.C_EXTENSION:
            raise ImportError, 'No Python source file for c extensions.'
        else:
            raise ImportError, 'No Python source file found.'

    #////////////////////////////////////////////////////////////
    # Top level: Module parsing
    #////////////////////////////////////////////////////////////

    DEFAULT_ENCODING = 'iso-8859-1' # aka 'latin-1'

    def parse(self, filename, package_doc=None):
        """
        Parse the given python module, and return a C{ModuleDoc}
        containing its API documentation.  If you want the module to
        be treated as a member of a package, then you must specify
        C{package_doc}.
        
        @param filename: The filename of the module to parse.
        @type filename: C{string}
        @rtype: L{ModuleDoc}
        """
        # Check the cache, first.
        if self.moduledoc_cache.has_key(filename):
            return self.moduledoc_cache[filename]

        # debug:
        import sys
        print >>sys.stderr, 'parsing %r...' % filename

        # Figure out the canonical name of the module we're parsing.
        module_name, is_pkg = _get_module_name(filename, package_doc)

        # Create a new ModuleDoc for the module, & add it to the cache.
        module_doc = ModuleDoc(canonical_name=module_name, variables={},
                               sort_spec=[],
                               filename=filename, package=package_doc,
                               is_package=is_pkg, submodules=[])
        self.moduledoc_cache[filename] = module_doc

        # Add this module to the parent package's list of submodules.
        if package_doc is not None:
            package_doc.submodules.append(module_doc)

        # Initialize the context & the parentdocs stack.
        old_context = self.context
        self.context = module_name
        self.parentdocs.append(module_doc)
        
        # Read the source file, and fix up newlines.
        source_code = open(filename).read()
        ast = parser.suite(source_code.replace('\r\n','\n')+'\n')
        
        # Parse the source file into a syntax tree.
        ast = ast.tolist()
        
        # If there's an encoding-decl, then strip it.
        if ast[0] == symbol.encoding_decl:
            ast = ast[1]
            encoding = ast[2] # reentrance!!
        else:
            encoding = self.DEFAULT_ENCODING
            
        # Find docstrings in the syntax tree.  Record the old value of
        # self.docstrings, in case we recursively call parse().
        old_docstring_info = self.docstring_info
        self.docstring_info = self.find_docstrings(ast, filename)

        # Get the module's docstring.
        docstring, lineno = self.docstring_info.get(id(ast), (None,None))
        module_doc.docstring = docstring
        module_doc.docstring_lineno = lineno

        # Parse each statement in the syntax tree.
        self.process_suite(ast)

        # Handle any special variables (__path__, __docformat__, etc.)
        self.handle_special_module_vars(module_doc, ast)

        # Restore the context & parentdocs stack (in case we were
        # called recursively).
        assert self.parentdocs[-1] is module_doc
        self.parentdocs.pop()
        self.context = old_context

        # Restore the old docstring info dictionary (in case we were
        # called recursively).
        self.docstring_info = old_docstring_info

        # Return the completed ModuleDoc
        return module_doc

    def handle_special_module_vars(self, module_doc, ast):
        """
        Extract values from any special variables that are defined by
        the module.  Currently, this looks for values for
        C{__docformat__}, C{__all__}, and C{__path__}.
        """
        # If __docformat__ is defined, then extract its value.
        ast = self._module_var_ast(module_doc, '__docformat__')
        if ast is not None:
            try: module_doc.docformat = self.extract_string(ast)
            except ValueError: module_doc.docformat = None
        if '__docformat__' in module_doc.variables:
            self._del_variable(module_doc, '__docformat__')

        # If __all__ is defined, then extract its value.
        ast = self._module_var_ast(module_doc, '__all__')
        if ast is not None:
            try:
                public_names = Set(self.extract_string_list(ast))
                for name, var_doc in module_doc.variables.items():
                    var_doc.is_public = (name in public_names)
            except ValueError: pass
        if '__all__' in module_doc.variables:
            self._del_variable(module_doc, '__all__')

        # If __path__ is defined, then extract its value.  Otherwise,
        # use the default value.
        if module_doc.is_package:
            module_doc.path = [os.path.split(module_doc.filename)[0]]
            ast = self._module_var_ast(module_doc, '__path__')
            if ast is not None:
                try: module_doc.path = self.extract_string_list(ast)
                except ValueError: raise #pass
            if '__path__' in module_doc.variables:
                self._del_variable(module_doc, '__path__')
                
    def _module_var_ast(self, module_doc, name):
        """
        If a variable named C{name} exists in C{module_doc}, and its
        value has an ast, then return its ast.
        """
        var_doc = module_doc.variables.get(name)
        if (var_doc is None or var_doc.value in (None, UNKNOWN) or
            var_doc.value.ast is UNKNOWN):
            return None
        else:
            return var_doc.value.ast

    #////////////////////////////////////////////////////////////
    # Token Eater
    #////////////////////////////////////////////////////////////

    def process(self, tokeniter):
        pass

    #////////////////////////////////////////////////////////////
    # Line handler
    #////////////////////////////////////////////////////////////


    

    #////////////////////////////////////////////////////////////
    # Suite Processor
    #////////////////////////////////////////////////////////////

    def process_suite(self, suite):
        """
        Process each statement of interest in the given suite.  In
        particular, compare each statement against the pattern
        matchers in L{STMT_PATTERNS}; and for the first pattern
        matcher that matches the statement, call the corresponding
        handler method.

        The handler method is called with keyword parameters based on
        the matcher's variables.  The handler is also given one
        additional parameter, C{docstring_info}, which contains a
        tuple C{(docstring, lineno)}, where C{docstring} is the
        statement's docstring, and C{docstring_lineno} is the line
        number where the docstring begins.  If the statement does not
        have a docstring, then C{docstring_info=(None,None)}.
    
        @param suite: A Python syntax tree containing the suite to be
            processed (as generated by L{parser.ast2list}).
        @type suite: C{list}
        @rtype: C{None}
        """
        assert suite[0] in (symbol.file_input, symbol.suite)
        for stmt in suite[1:]:
            # Check if stmts[i] matches any of our statement patterns.
            for (name, matcher) in self.STMT_PATTERNS:
                match, vars = matcher.match(stmt)
                if match:
                    ds = self.docstring_info.get(id(stmt), (None, None))
                    # Delegate to the appropriate handler.
                    handler_method = getattr(self, name)
                    handler_method(docstring_info=ds, **vars)
                    break

            #else:
            #    print pp_ast(stmts[i])
        
    #////////////////////////////////////////////////////////////
    # Statement Parsing Dispatch Table
    #////////////////////////////////////////////////////////////

    #: A table used by L{process_suite} to find statements of interest,
    #: and delegate them to appropriate handlers.  Each table entry
    #: has the form C{(name, matcher)}.  C{matcher} is an
    #: L{ASTMatcher} that matches statements of interest, and C{name}
    #: is the name of a handler method that can parse statements
    #: matched by C{matcher}.
    #:
    #: For each statement, the matchers are tried in order.  For the
    #: first matcher that matches a statement, the corresponding
    #: handler is called, with parameters based on the matcher's
    #: variables.  The handler is given one additional parameter,
    #: C{docstring_info}, which contains a tuple C{(docstring,
    #: lineno)}, where C{docstring} is the statement's docstring, and
    #: C{docstring_lineno} is the line number where the docstring
    #: begins.  If the statement does not have a docstring, then
    #: C{docstring_info=(None,None)}.
    #:
    #: If no matchers match a statement, then that statement is
    #: ignored.
    STMT_PATTERNS = [
        ('process_import', compile_ast_matcher("""
            (stmt 
             (simple_stmt
              (small_stmt
               (import_stmt ...):ast)
              NEWLINE))""")),
        # Class definition: "class A(B): ..."
        ('process_classdef', compile_ast_matcher("""
            (stmt 
             (compound_stmt (classdef
                'class' NAME:classname
                LPAR? (testlist...)?:bases RPAR?
                COLON
                (suite ...):body)))""")),
        # Function definition: "def f(x): ..."
        ('process_funcdef', compile_ast_matcher("""
            (stmt 
             (compound_stmt (funcdef
                (decorators ...)?:decorators
                'def' NAME:funcname
                (parameters ...):parameters
                COLON
                (suite ...): body)))""")),
        # Simple assignment: "x=y" or "x.y=z"
        ('process_simple_assignment', compile_ast_matcher("""
            (stmt 
             (simple_stmt (small_stmt (expr_stmt
              (testlist (test (and_test (not_test (comparison (expr
               (xor_expr (and_expr (shift_expr (arith_expr (term
                (factor (power (atom NAME)
                               (trailer DOT NAME)*))))))))))))):lhs
              EQUAL (...):rhs)) NEWLINE))""")),
        # Complex-LHS assignment: "(a,b)=c" or "[a,b]=c"
        ('process_complex_assignment', compile_ast_matcher("""
            (stmt 
             (simple_stmt (small_stmt (expr_stmt
              (testlist...):lhs EQUAL (...):rhs)) NEWLINE))""")),
        # Multi assignment: "a=b=c"
        ('process_multi_assignment', compile_ast_matcher("""
            (stmt 
             (simple_stmt (small_stmt (expr_stmt
              (testlist...):lhs EQUAL
              (...)*:rhs)) NEWLINE))""")),
        # Try statement: "try: ..."
        ('process_try', compile_ast_matcher("""
            (stmt 
             (compound_stmt
              (try_stmt 'try' COLON (suite ...):trysuite
              (...)*:rest)))""")),
        # If statement: "if x: ..."
        ('process_if', compile_ast_matcher("""
            (stmt 
             (compound_stmt
              (if_stmt 'if' ...):ifstmt))""")),
        # While statement: "while x: pass"
        ('process_while', compile_ast_matcher("""
            (stmt 
             (compound_stmt
              (while_stmt 'while' (test ...) COLON (suite ...):whilesuite
               'else'? COLON? (suite ...)?:elsesuite)))""")),
        # For statement: "for x in [1,2,3]: pass"
        ('process_for', compile_ast_matcher("""
            (stmt 
             (compound_stmt
              (for_stmt 'for' (exprlist...):loopvar 'in' 
               (testlist...) COLON (suite ...):forsuite
               'else'? COLON? (suite ...)?:elsesuite)))""")),
        # Semicolon-separated statements: "x=1; y=2"
        ('process_multi_stmt', compile_ast_matcher("""
            (stmt 
             (simple_stmt
              (small_stmt ...):stmt1
              SEMI
              (...)*:rest))""")),
        # Delete statement: "del x"
        ('process_del', compile_ast_matcher("""
            (stmt 
             (simple_stmt (small_stmt (del_stmt 'del'
              (exprlist ...):exprlist)) NEWLINE))""")),
        ]

    #////////////////////////////////////////////////////////////
    # Parse Handler: Imports
    #////////////////////////////////////////////////////////////

    def process_import(self, ast, docstring_info):
        """
        The statement handler for import statements.  This handler
        adds a C{VariableDoc} to the parent C{APIDoc} for each name
        that is created by importing.

        @param cmd: The import command (C{'from'} or C{'import'})
        @param names: The contents of the import statement, from
            which the import names are taken.            
        @param docstring_info: Information about the statement's
            docstring (ignored).
        @rtype: C{None}
        """
        # If we're not in a namespace, then ignore import statements.
        parentdoc = self.parentdocs[-1]
        if not isinstance(parentdoc, NamespaceDoc): return

        # For Python 2.3:
        if ast[1][0] == token.NAME: 
            if ast[1][1] == 'from' and ast[2][1][1] == '__future__':
                pass # ignore __future__ statements
            elif ast[1][1] == 'from' and ast[-1][0] == token.STAR:
                self._process_fromstar_import(ast[2])
            elif ast[1][1] == 'from':
                self._process_from_import(ast[2], ast[4:])
            elif ast[1][1] == 'import':
                self._process_simple_import(ast[2:])

        # For Python 2.4:
        elif ast[1][0] == symbol.import_from:
            ast = ast[1]
            if ast[2][1][1] == '__future__':
                pass # ignore future statements
            elif ast[-1][0] == token.STAR:
                self._process_fromstar_import(ast[2])
            elif len(ast) == 7:
                self._process_from_import(ast[2], ast[5][1:])
            elif len(ast) == 5:
                self._process_from_import(ast[2], ast[4][1:])
            else:
                raise ValueError, 'unexpected ast value'
        elif ast[1][0] == symbol.import_name:
            self._process_simple_import(ast[1][2][1:])

    def _process_simple_import(self, names):
        for name in names:
                if name[0] == symbol.dotted_as_name:
                    # dotted_as_name: dotted_name
                    if len(name) == 2:
                        src = DottedName(name[1][1][1])
                        self._import_var(src)
                    # dotted_as_name: dotted_name 'as' NAME
                    elif len(name) == 4:
                        src = self.extract_dotted_name(name[1])
                        self._import_var_as(src, name[3][1])
        
        # from module import name1 [as alias1], ...
    def _process_from_import(self, srcmod, names):
        srcmod = self.extract_dotted_name(srcmod)
        for name in names:
                if name[0] == symbol.import_as_name:
                    # import_as_name: NAME
                    if len(name) == 2:
                        src = DottedName(srcmod, name[1][1])
                        self._import_var_as(src, name[1][1])
                    # import_as_name: import_name 'as' NAME
                    elif len(name) == 4:
                        src = DottedName(srcmod, name[1][1])
                        self._import_var_as(src, name[3][1])
                        
    def _process_fromstar_import(self, src):
        """
        Handle a statement of the form:
            >>> from <src> import *

        If L{IMPORT_HANDLING} is C{'parse'}, then first try to parse
        the module C{M{<src>}}, and copy all of its exported variables
        to C{parentdoc}.

        Otherwise, try to determine the names of the variables
        exported by C{M{<src>}}, and create a new variable for each
        export, using proxy values (i.e., values with C{imported_from}
        attributes pointing to the imported objects).  If
        L{IMPORT_STAR_HANDLING} is C{'parse'}, then the list of
        exports if found by parsing C{M{<src>}}; if it is
        C{'inspect'}, then the list of exports is found by importing
        and inspecting C{M{<src>}}.
        """
        parentdoc = self.parentdocs[-1]
        src = self.extract_dotted_name(src)
        
        # If src is package-local, then convert it to a global name.
        src = self._global_name(src)
        
        if (self.IMPORT_HANDLING == 'parse' or
            self.IMPORT_STAR_HANDLING == 'parse'):
            try: module_doc = self._find(src)
            except ValueError: module_doc = None
            if isinstance(module_doc, ModuleDoc):
                if self.IMPORT_HANDLING == 'parse':
                    for name, imp_var in module_doc.variables.items():
                        if imp_var.is_public:
                            var_doc = VariableDoc(name=name, is_alias=False,
                                                  value=imp_var.value,
                                                  is_imported=True)
                            self._set_variable(parentdoc, var_doc)
                else:
                    for name, imp_var in module_doc.variables.items():
                        if imp_var.is_public:
                            self._add_import_var(DottedName(src,name),
                                                 name, parentdoc)
                return

        # If we got here, then either IMPORT_HANDLING='link' or we
        # failed to parse the `src` module.
        if self.IMPORT_STAR_HANDLING == 'inspect':
            try: module = __import__(str(src), {}, {}, [0])
            except: return # We couldn't import it.
            if module is None: return # We couldn't import it.
            if hasattr(module, '__all__'):
                names = list(module.__all__)
            else:
                names = [n for n in dir(module) if not n.startswith('_')]
            for name in names:
                self._add_import_var(DottedName(src, name), name, parentdoc)

    def _import_var(self, name):
        """
        Handle a statement of the form:
            >>> import <name>

        If L{IMPORT_HANDLING} is C{'parse'}, then first try to find
        the value by parsing; and create an appropriate variable in
        parentdoc.

        Otherwise, create one or more variables using proxy values
        (i.e., values with C{imported_from} attributes pointing to the
        imported objects).  (More than one variable may be created for
        cases like C{'import a.b'}, where we need to create a variable
        C{'a'} in parentdoc containing a proxy module; and a variable
        C{'b'} in the proxy module containing a proxy value.
        """
        # If name is package-local, then convert it to a global name.
        name = self._global_name(name)
        
        if self.IMPORT_HANDLING == 'parse':
            # Check to make sure that we can actually find the value.
            try: val_doc = self._find(name)
            except ValueError: val_doc = None
            if val_doc is not None:
                # We found it; but it's not the value itself we want to
                # import, but the module containing it; so import that
                # module and create a variable for it.
                mod_doc = self._find(DottedName(name[0]))
                var_doc = VariableDoc(name=name[0], value=mod_doc,
                                      is_imported=True, is_alias=False)
                self._set_variable(self.parentdocs[-1], var_doc)
                return

        # If we got here, then either IMPORT_HANDLING='link', or we
        # did not successfully find the value's docs by parsing; use
        # a variable with a proxy value.
        
        # Create any necessary intermediate proxy module values.
        container = self.parentdocs[-1]
        for i, identifier in enumerate(name[:-1]):
            if (identifier not in container.variables or
                not isinstance(container.variables[identifier], ModuleDoc)):
                val_doc = NamespaceDoc(variables={}, sort_spec=[],
                                       imported_from=name[:i+1])
                var_doc = VariableDoc(name=identifier, value=val_doc,
                                      is_imported=True, is_alias=False)
                self._set_variable(container, var_doc)
            container = container.variables[identifier].value

        # Add the variable to the container.
        self._add_import_var(name, name[-1], self.parentdocs[-1])

    def _import_var_as(self, src, name):
        """
        Handle a statement of the form:
            >>> from src import name
            
        If L{IMPORT_HANDLING} is C{'parse'}, then first try to find
        the value by parsing; and create an appropriate variable in
        parentdoc.

        Otherwise, create a variables with a proxy value (i.e., a
        value with C{imported_from} attributes pointing to the
        imported object).
        """
        # If src is package-local, then convert it to a global name.
        src = self._global_name(src)
        
        if self.IMPORT_HANDLING == 'parse':
            # Parse the value and create a variable for it.
            try: val_doc = self._find(src)
            except ValueError: val_doc = None
            if val_doc is not None:
                var_doc = VariableDoc(name=name, value=val_doc,
                                      is_imported=True, is_alias=False)
                self._set_variable(self.parentdocs[-1], var_doc)
                return

        # If we got here, then either IMPORT_HANDLING='link', or we
        # did not successfully find the value's docs by parsing; use a
        # variable with a proxy value.
        self._add_import_var(src, name, self.parentdocs[-1])

    def _add_import_var(self, src, name, container):
        """
        Add a new variable named C{name} to C{container}, whose value
        is a C{ValueDoc} with an C{imported_from=src}.
        """
        val_doc = ValueDoc(imported_from=src)
        var_doc = VariableDoc(name=name, value=val_doc,
                              is_imported=True, is_alias=False)
        self._set_variable(container, var_doc)

    def _global_name(self, name):
        """
        If the given name is package-local (relative to the current
        context, as determined by L{self.parentdocs}), then convert it
        to a global name.
        """
        # Find our module.
        for i in range(len(self.parentdocs)-1, -1, -1):
            if isinstance(self.parentdocs[i], ModuleDoc): break
        module_doc = self.parentdocs[i]
        if module_doc.is_package in (False, UNKNOWN):
            return name
        else:
            try:
                self._get_filename(name[0], module_doc.path)
                return DottedName(module_doc.canonical_name, name)
            except ImportError:
                return name

    #////////////////////////////////////////////////////////////
    # Parse Handler: Simple Assignments
    #////////////////////////////////////////////////////////////

    def process_simple_assignment(self, lhs, rhs, docstring_info):
        """
        The statement handler for assignment statements whose
        left-hand side is a single identifier.  The behavior of this
        handler depends on the contents of the assignment statement
        and the context:

          - If the assignment statement occurs inside an __init__          
            method, and has a docstring, then the handler creates a
            new C{VariableDoc} in the containing class and sets
            C{L{is_instvar<VariableDoc.is_instvar>}=True}.

          - If the assignment's right-hand side is a single identifier
            with a known value, then the handler creates a new
            C{VariableDoc} in the containing namespace whose
            C{val_doc} is that value's documentation, and sets
            C{L{is_alias<VariableDoc.is_alias>}=True}.

          - Otherwise, the handler creates a new C{VariableDoc} in the
            containing namespace, whose C{ValueDoc} is computed from
            the right-hand side by L{rhs_to_valuedoc}.

        @param lhs: The left-hand side of the assignment statement.
        @param rhs: The right-hand side of the assignment statement.
        @param docstring_info: Information about the statement's
            docstring, encoded as a tuple C{(docstring, lineno)}.
        @rtype: C{None}
        """
        # The APIDoc for our container.
        parentdoc = self.parentdocs[-1]

        is_alias = False    # Is the variable an alias?
        is_instvar = False  # Is the variable an instance variable?
        val_doc = UNKNOWN   # What's the variable's value?
        
        # Extract the var name from the left-hand side.  If the
        # left-hand side isn't a var name, then just return.
        var_dotted_name = self.extract_dotted_name(lhs)
        if var_dotted_name is None: return

        # Inside __init__ functions, look for instance variables.
        if self._inside_init():
            # To be recorded, instance variables must have the form
            # "self.x", and must have a non-empty docstring.
            if (docstring_info[0] is None or len(var_dotted_name) != 2 or
                len(parentdoc.posargs) == 0 or
                var_dotted_name[0] != parentdoc.posargs[0]):
                return
            
            is_instvar = True
            val_doc = ValueDoc()
            # Set parentdoc to the containing class.
            parentdoc = self.parentdocs[-2]

        # Outside __init__, ignore any assignment to a dotted name
        # with more than one identifier (e.g. "a.b.c").
        if not is_instvar and len(var_dotted_name) > 1: return
        varname = var_dotted_name[-1]

        # If the RHS is a single identifier that we have a value for,
        # then create an alias variable.
        if val_doc is UNKNOWN and rhs[0] == symbol.testlist:
            rhs_dotted_name = self.extract_dotted_name(rhs)
            if rhs_dotted_name is not None:
                val_doc = self.lookup_value(rhs_dotted_name)
                if val_doc is None:
                    val_doc = UNKNOWN
                else:
                    is_alias = True
                
        # Otherwise, use rhs_to_valuedoc to find a val_doc for rhs.
        if val_doc is UNKNOWN:
            val_doc = self.rhs_to_valuedoc(rhs, varname)

        # Create the VariableDoc, and add it to its parent.
        if isinstance(parentdoc, NamespaceDoc):
            var_doc = VariableDoc(name=varname, value=val_doc,
                                  docstring=docstring_info[0],
                                  docstring_lineno=docstring_info[1],
                                  is_imported=False, is_alias=is_alias, 
                                  is_instvar=is_instvar)
            self._set_variable(parentdoc, var_doc)

    def _inside_init(self):
        """
        @return: True if the current context of the C{DocParser} is
        the C{__init__} method of a class.
        @rtype: C{bool}
        """
        return (len(self.parentdocs)>=2 and 
                isinstance(self.parentdocs[-2], ClassDoc) and
                isinstance(self.parentdocs[-1], RoutineDoc) and
                self.context[-1] == '__init__')
    
    #////////////////////////////////////////////////////////////
    # Parse Handler: Complex Assignments
    #////////////////////////////////////////////////////////////

    def process_complex_assignment(self, lhs, rhs, docstring_info):
        """
        The statement handler for assignment statements whose
        left-hand side is a single complex expression, such as a tuple
        or list.  This handler creates a new C{VariableDoc} in the
        containing namespace for each non-dotted variable name on the
        left-hand side.  The docstring and right-hand side are
        ignored.

        @param lhs: The left-hand side of the assignment statement.
        @param rhs: The right-hand side of the assignment statement.
        @param docstring_info: Information about the statement's
            docstring (ignored).
        @rtype: C{None}
        @todo: Try matching the left-hand side against the right-hand
            side; and if successful, create a suite containing
            multiple simple assignments, and delegate to
            L{process_suite}.
        """
        # If we're not in a namespace, ignore tuple assignments
        parentdoc = self.parentdocs[-1]
        if not isinstance(parentdoc, NamespaceDoc): return

        # Convert the LHS into dotted names.
        try: lhs = self.extract_dotted_name_list(lhs)
        except: return

        # Create VariableDocs in the namespace.
        for dotted_name in flatten(lhs):
            if len(dotted_name) == 1:
                varname = dotted_name[0]
                var_doc = VariableDoc(name=varname, value=ValueDoc(),
                                     is_imported=False)
                self._set_variable(parentdoc, var_doc)

    #////////////////////////////////////////////////////////////
    # Parse Handler: Multi-Assignments
    #////////////////////////////////////////////////////////////

    def process_multi_assignment(self, lhs, rhs, docstring_info):
        """
        The statement handler for assignment statements with multiple
        left-hand sides, such as C{x=y=2}.  This handler creates a
        suite containing the individual assignments, and delegates to
        L{process_suite}.  For example, the assignment C{x=y=z=3}
        translates to the suite C{z=3;y=z;x=y}.

        @param lhs: The first left-hand side of the assignment
            statement.
        @param rhs: The remaining left-hand sides, and the final
            right-hand side.
        @param docstring_info: Information about the statement's
            docstring (ignored).
        @rtype: C{None}
        """
        # Get a list of all the testlists.
        testlists = [lhs] + [e for e in rhs if e[0]==symbol.testlist]

        # Unroll the multi-assignment into a suite.
        suite = [symbol.suite]
        for i in range(len(testlists)-2, -1, -1):
            suite.append((symbol.stmt, (symbol.simple_stmt,
                            (symbol.small_stmt, (symbol.expr_stmt,
                               testlists[i], (token.EQUAL, '='),
                               testlists[i+1])),
                          (token.NEWLINE, ''))))

        # Delegate to process_suite
        self.process_suite(suite)
        
    #////////////////////////////////////////////////////////////
    # Parse Handler: Control Blocks
    #////////////////////////////////////////////////////////////

    def process_try(self, trysuite, rest, docstring_info):
        """
        The statement handler for C{try} blocks.  This handler calls
        C{process_suite} on the suites contained by the C{try} block.

        @param trysuite: The contents of the C{try} block.
        @param rest: The contents of the C{finally/except/else} blocks.
        @param docstring_info: Information about the statement's
            docstring (ignored).
        @rtype: C{None}
        """
        if self.PARSE_TRY_BLOCKS:
            self.process_suite(trysuite)
        if len(rest)>3 and rest[-3] == (token.NAME, 'finally'):
            if self.PARSE_FINALLY_BLOCKS:
                self.process_suite(rest[-1])
        elif self.PARSE_EXCEPT_BLOCKS:
            for elt in rest:
                if elt[0] == symbol.suite:
                    self.process_suite(elt)
    
    def process_if(self, ifstmt, docstring_info):
        """
        The statement handler for C{if} blocks.  This handler calls
        C{process_suite} on the suites contained by the C{if} block.

        @param ifstmt: The contents of the C{if} block.
        @param docstring_info: Information about the statement's
            docstring (ignored).
        @rtype: C{None}
        """
        # The contents of ifstmt are::
        #   'if' test COLON suite ('elif' test COLON suite)*
        #                         ('else' test COLON suite)?
        # We're interested in extracting the suites.
        if self.PARSE_IF_BLOCKS:
            self.process_suite(ifstmt[4])
        if self.PARSE_ELSE_BLOCKS:
            for i in range(8, len(ifstmt), 4):
                self.process_suite(ifstmt[i])

    def process_while(self, whilesuite, elsesuite, docstring_info):
        """
        The statement handler for C{while} blocks.  This handler calls
        C{process_suite} on the suites contained by the C{while}
        block.

        @param whilesuite: The contents of the C{while} block.
        @param elsesuite: The contents of the C{else} block.
        @param docstring_info: Information about the statement's
            docstring (ignored).
        @rtype: C{None}
        """
        if self.PARSE_WHILE_BLOCKS:
            self.process_suite(whilesuite)
            if elsesuite is not None:
                self.process_suite(elsesuite)
        
    def process_for(self, loopvar, forsuite, elsesuite, docstring_info):
        """
        The statement handler for C{for} blocks.  This handler calls
        C{process_suite} on the suites contained by the C{for} block;
        and creates a C{VariableDoc} in the containing namespace for
        the loop variable.

        @param loopvar: The loop variable.
        @param forsuite: The contents of the C{for} block.
        @param elsesuite: The contents of the C{else} block.
        @param docstring_info: Information about the statement's
            docstring (ignored).
        @rtype: C{None}
        """
        # The APIDoc for our container.
        parentdoc = self.parentdocs[-1]
        
        if self.PARSE_FOR_BLOCKS:
            self.process_suite(forsuite)
            if elsesuite is not None:
                self.process_suite(elsesuite)
                
            # Create a VariableDoc for the loop variable.
            if isinstance(parentdoc, NamespaceDoc):
                loopvar_dotted_name = self.extract_dotted_name(loopvar)
                if len(loopvar_dotted_name) == 1:
                    loopvar_name = loopvar_dotted_name[0]
                    var_doc = VariableDoc(name=loopvar_name, is_imported=False)
                    self._set_variable(parentdoc, var_doc)

    #////////////////////////////////////////////////////////////
    # Parse Handler: Function Definitions
    #////////////////////////////////////////////////////////////

    def process_funcdef(self, decorators, funcname, parameters,
                        body, docstring_info):
        """
        The statement handler for function definition blocks.  This
        handler constructs the documentation for the function, and
        adds it to the containing namespaces.  If the function is a
        method's C{__init__} method, then it calls L{process_suite} to
        process the function's body.

        @param funcname: The name of the function.
        @param parameters: The function's parameter list.
        @param body: The function's body.
        @param docstring_info: Information about the statement's
            docstring, encoded as a tuple C{(docstring, lineno)}.
        @rtype: C{None}
        """
        # If we're not in a namespace, then ignore the funcdef.
        parentdoc = self.parentdocs[-1]
        if not isinstance(parentdoc, NamespaceDoc): return

        # Create the function's RoutineDoc & VariableDoc.
        if isinstance(parentdoc, ClassDoc):
            func_doc = InstanceMethodDoc()
        else:
            func_doc = FunctionDoc()
        var_doc = VariableDoc(name=funcname, value=func_doc,
                              is_imported=False, is_alias=False)

        # Add the VariableDoc to our container.
        self._set_variable(parentdoc, var_doc)
        
        # Add the function's parameters.
        self._add_parameters(parameters, func_doc)

        # Add the function's docstring.
        func_doc.docstring, func_doc.docstring_lineno = docstring_info

        # Add the function's canonical name
        func_doc.canonical_name = DottedName(self.context, funcname)
        
        # Parse the suite (if we're in an __init__ method).
        if isinstance(parentdoc, ClassDoc) and funcname == '__init__':
            self.context = DottedName(self.context, funcname)
            self.parentdocs.append(func_doc)
            self.process_suite(body)
            self.context = DottedName(*self.context[:-1])
            self.parentdocs.pop()

        # Check for recognized decorators
        if decorators is not None:
            # Decorators are evaluated from bottom-to-top; so reverse
            # the list.
            decorators = decorators[1:]
            decorators.reverse()
            # Check each decorator to see if we know what to do with it.
            for decorator in decorators:
                decorator_name = self.extract_dotted_name(decorator[2])
                if len(decorator) == 6:
                    decorator_args = ()
                elif len(decorator) > 6:
                    decorator_args = decorator[4]
                else:
                    assert len(decorator) == 4
                    decorator_args = None
                func_doc = self.apply_decorator(func_doc, decorator_name,
                                                decorator_args)
                var_doc.value = func_doc
                
    def apply_decorator(self, func_doc, decorator_name, decorator_args):
        """
        Return a C{RoutineDoc} specifying the API documentation for
        the value produced by applying the given decorator to the
        specified function.

        @param func_doc: The API documentation for the function that
            is being decorated.
        @param decorator_name: The name of the decorator that is being
            applied.
        @type decorator_name: L{DottedName}
        @param decorator_args: The ast for the arguments to the
            decorator, if any.  If the decorator has no argument list,
            then C{decorator_args} is C{None}.  If the decorator has
            an empty argument list, then C{decorator_args} is C{()}.
        """
        if decorator_name == DottedName('staticmethod'):
            return  StaticMethodDoc(**func_doc.__dict__)
        elif decorator_name == DottedName('classmethod'):
            return ClassMethodDoc(**func_doc.__dict__)
        elif self.DEFAULT_DECORATOR_BEHAVIOR == 'passthrough':
            return func_doc
        elif self.DEFAULT_DECORATOR_BEHAVIOR == 'erasedocs':
            return ValueDoc()

    def _add_parameters(self, parameters, func_doc):
        """
        Set C{func_doc}'s parameter fields (C{args}, C{vararg}, and
        C{kwarg}) based on C{parameters}.
        
        @param parameters: The syntax tree for the function's
           parameter list (as generated by L{parser.ast2list}).
        """
        # Set initial values.
        func_doc.posargs = []
        func_doc.posarg_defaults = []
        func_doc.vararg = None
        func_doc.kwarg = None
        
        # parameters: '(' [varargslist] ')'
        if len(parameters) == 3: return
        varargslist = parameters[2]

        # Check for kwarg.
        if len(varargslist) > 3 and varargslist[-2][0] == token.DOUBLESTAR:
            func_doc.kwarg = varargslist[-1][1]
            del varargslist[-3:]

        # Check for vararg.
        if len(varargslist) > 3 and varargslist[-2][0] == token.STAR:
            func_doc.vararg = varargslist[-1][1]
            del varargslist[-3:]

        # The rest should all be fpdef's.
        for elt in varargslist[1:]:
            if elt[0] == symbol.fpdef:
                name = self._fpdef_to_name(elt)
                func_doc.posargs.append(name)
                func_doc.posarg_defaults.append(None)
            elif elt[0] == symbol.test:
                default = ValueDoc(ast=elt, repr=ast_to_string(elt, 'tight'))
                func_doc.posarg_defaults[-1] = default

    def _fpdef_to_name(self, fpdef):
        """
        @return: The name (or nested tuple of names) specified by
            the given function parameter definition.
        @param fpdef: The syntax tree for a function parameter
            definition (as generated by L{parser.ast2list}).
        @rtype: C{string} or C{tuple}
        """
        # fpdef: NAME | '(' fplist ')'
        if fpdef[1][0] == token.NAME:
            return fpdef[1][1]
        else:
            fplist = fpdef[2] # fplist: fpdef (',' fpdef)* [',']
            return tuple([self._fpdef_to_name(e) for e in fplist[1:]
                          if e[0] == symbol.fpdef])

    #////////////////////////////////////////////////////////////
    # Parse Handler: Class Definitions
    #////////////////////////////////////////////////////////////

    def process_classdef(self, classname, bases, body, docstring_info):
        """
        The statement handler for class definition blocks.  This
        handler constructs the documentation for the class, and adds
        it to the containing namespaces.  The handler then calls
        L{process_suite} to process the class's body.

        @param classname: The name of the class
        @param bases: The class's base list
        @param body: The class's body
        @param docstring_info: Information about the statement's
            docstring, encoded as a tuple C{(docstring, lineno)}.
        @rtype: C{None}
        """
        # If we're not in a namespace, then ignore the classdef.
        parentdoc = self.parentdocs[-1]
        if not isinstance(parentdoc, NamespaceDoc): return
        
        # Create the class's ClassDoc & VariableDoc.
        classdoc = ClassDoc(local_variables={}, sort_spec=[],
                            bases=[], subclasses=[])
        var_doc = VariableDoc(name=classname, value=classdoc,
                              is_imported=False, is_alias=False)

        # Add the VariableDoc to our container.
        self._set_variable(parentdoc, var_doc)

        # Find our base classes.
        if bases is not None:
            base_dotted_names = self.extract_dotted_name_list(bases)
            for base in base_dotted_names:
                base_doc = self.lookup_value(base)
                if base_doc is not None:
                    classdoc.bases.append(base_doc)
                else:
                    # [XX] This is a potentially significant problem?
                    base_doc = ClassDoc(variables={}, sort_spec=[],
                                        bases=[], subclasses=[],
                                        imported_from = base)
                    classdoc.bases.append(base_doc)

        # Register ourselves as a subclass to our bases.
        for basedoc in classdoc.bases:
            if isinstance(basedoc, ClassDoc):
                basedoc.subclasses.append(classdoc)
        
        # Add the class's docstring.
        classdoc.docstring, classdoc.docstring_lineno = docstring_info
        
        # Add the class's canonical name
        classdoc.canonical_name = DottedName(self.context, classname)
        
        # Parse the suite.
        self.context = DottedName(self.context, classname)
        self.parentdocs.append(classdoc)
        self.process_suite(body)
        self.context = DottedName(*self.context[:-1])
        self.parentdocs.pop()

    #////////////////////////////////////////////////////////////
    # Parse Handler: Semicolon-Separated Statements
    #////////////////////////////////////////////////////////////

    def process_multi_stmt(self, stmt1, rest, docstring_info):
        """
        The statement handler for a set of semicolon-separated
        statements, such as:
        
            >>> x=1; y=2; z=3
            
        This handler wraps the individual statements in a suite, and
        delegates to C{process_suite}.
        @param docstring_info: Information about the statement's
            docstring (ignored).
        """
        # Get a list of the small-statements.
        small_stmts = [stmt1] + [s for s in rest
                                 if s[0] == symbol.small_stmt]
                        
        # Wrap them up to look like a suite.
        stmts = [[symbol.stmt, [symbol.simple_stmt, s, [token.NEWLINE, '']]]
                 for s in small_stmts]
        suite = [symbol.suite] + stmts

        # Delegate to process_suite.
        self.process_suite(suite)

    #////////////////////////////////////////////////////////////
    # Parse Handler: Delete Statements
    #////////////////////////////////////////////////////////////
     
    def process_del(self, exprlist, docstring_info):
        """
        The statement handlere for delete statements.
        @param docstring_info: Information about the statement's
            docstring (ignored).
        """
        # If we're not in a namespace, then ignore del statements.
        parentdoc = self.parentdocs[-1]
        if not isinstance(parentdoc, NamespaceDoc): return

        # Extract the list of identifiers to delete, and delete them.
        try: names = flatten(self.extract_dotted_name_list(exprlist))
        except ValueError: return
        for name in names:
            self._del_variable(parentdoc, name)

    #////////////////////////////////////////////////////////////
    # Variable Manipulation
    #////////////////////////////////////////////////////////////

    def _set_variable(self, namespace, var_doc):
        # Choose which dictionary we'll be storing the variable in.
        if not isinstance(namespace, NamespaceDoc):
            return
        elif isinstance(namespace, ClassDoc):
            var_dict = namespace.local_variables
        else:
            var_dict = namespace.variables
        # If we already have a variable with this name, then remove the
        # old VariableDoc from the sort_spec list; and if we gave its
        # value a canonical name, then delete it.
        if var_doc.name in var_dict:
            namespace.sort_spec.remove(var_doc.name)
            if not var_doc.is_alias and var_doc.value is not UNKNOWN:
                var_doc.value.canonical_name = UNKNOWN
        # Add the variable to the namespace.
        var_dict[var_doc.name] = var_doc
        namespace.sort_spec.append(var_doc.name)
        assert var_doc.container is UNKNOWN
        var_doc.container = namespace

    # need to handle things like 'del A.B.c'
    def _del_variable(self, namespace, name):
        if not isinstance(namespace, NamespaceDoc):
            return
        elif isinstance(namespace, ClassDoc):
            var_dict = namespace.local_variables
        else:
            var_dict = namespace.variables

        name = DottedName(name)
        if name[0] in var_dict:
            if len(name) == 1:
                var_doc = var_dict[name[0]]
                namespace.sort_spec.remove(name[0])
                del var_dict[name[0]]
                if not var_doc.is_alias and var_doc.value is not UNKNOWN:
                    var_doc.value.canonical_name = UNKNOWN
            else:
                self._del_variable(var_dict[name[0]], name[1:])
                
    #////////////////////////////////////////////////////////////
    # Value Extraction
    #////////////////////////////////////////////////////////////

    #: A pattern matcher used to find C{classmethod} and
    #: C{staticmethod} wrapper functions on the right-hand side
    #: of assignment statements.
    __WRAPPER_PATTERN = compile_ast_matcher("""
        (testlist (test (and_test (not_test (comparison (expr
         (xor_expr (and_expr (shift_expr (arith_expr (term (factor
          (power (atom NAME:funcname)
           (trailer LPAR (arglist (argument (test (and_test (not_test
            (comparison (expr (xor_expr (and_expr (shift_expr
             (arith_expr (term (factor
              (power (atom NAME) (trailer DOT NAME)*):arg)))))))))))))
            RPAR))))))))))))))""")

    def rhs_to_valuedoc(self, rhs, varname):
        """
        @return: A C{ValueDoc} giving the API documentation for the
            object specified by the right-hand side of an assignment
            statement.
        @rtype: L{ValueDoc}
        @param rhs: The Python syntax tree for the right-hand side
            of the assignment statement (as generated by
            L{parser.ast2list}).
        @type rhs: C{list}
        """
        # If the RHS is a classmethod or staticmethod wrapper, then
        # create a ClassMethodDoc/StaticMethodDoc
        match, vars2 = self.__WRAPPER_PATTERN.match(rhs)
        if match:
            arg_dotted_name = self.extract_dotted_name(vars2['arg'])
            arg_valuedoc = self.lookup_value(arg_dotted_name)
            if isinstance(arg_valuedoc, RoutineDoc):
                # Figure out the canonical name for the value.
                parent_name = self.parentdocs[-1].canonical_name
                if parent_name is not UNKNOWN:
                    rhs_canonical_name = DottedName(parent_name, varname)
                else:
                    rhs_canonical_name = None
                # Wrap the routine in a classmethod/staticmethod.
                if vars2['funcname'] == 'classmethod':
                    cm_doc = ClassMethodDoc(**arg_valuedoc.__dict__)
                    cm_doc.canonical_name = rhs_canonical_name
                    return cm_doc
                elif vars2['funcname'] == 'staticmethod':
                    sm_doc = StaticMethodDoc(**arg_valuedoc.__dict__)
                    sm_doc.canonical_name = rhs_canonical_name
                    return sm_doc
        
        # Otherwise, it's a simple assignment
        return ValueDoc(ast=rhs, repr=ast_to_string(rhs))

    #////////////////////////////////////////////////////////////
    # Docstring Extraction
    #////////////////////////////////////////////////////////////
     
    __STRING_STMT_PATTERN = compile_ast_matcher("""
        (stmt COMMENT* (simple_stmt (small_stmt (expr_stmt (testlist 
          (test (and_test (not_test (comparison (expr (xor_expr 
            (and_expr (shift_expr (arith_expr (term (factor (power (atom
              STRING:stringval)))))))))))))))) NEWLINE))""")
    """A pattern matcher that matches a statement containing a single
    string literal.  This pattern matcher is used to find docstrings."""

    def find_docstrings(self, ast, filename):
        """
        Find all docstrings in a Python source file, including
        attribute docstrings and comment docstrings.  In particular,
        given a syntax tree and the name of the file that syntax tree
        came from, return a dictionary that maps from python id's of
        syntax tree nodes to tuples C{(docstring, lineno)}, where
        C{docstring} is the docstring for that node, and C{lineno} is
        the line number for that docstring.
        """
        tokeniter = tokenize.generate_tokens(open(filename).readline)
        docstrings = {}
        self._find_docstrings_helper(ast, filename, tokeniter,
                                     docstrings, [ast])
        for key, (strings, lineno) in docstrings.items():
            docstrings[key] = ('\n'.join(strings), lineno)
        return docstrings
            
    def _find_docstrings_helper(self, ast, filename, tokeniter,
                                docstrings, stmts):
        if ast == '': return
    
        # If `ast` is a leaf in the syntax tree, then iterate through the
        # tokens until we find one that matches the leaf.  Record any
        # tokens that contain docstrings.
        if isinstance(ast, str):
            for typ,tok,start,end,line in tokeniter:
                
                # Is this token a docstring?
                if (typ == token.STRING and stmts[-1] is not None and
                    self.__STRING_STMT_PATTERN.match(stmts[-1])[0]):
                    # This is safer than eval():
                    s = compiler.parse(tok).getChildren()[0]
                    docstrings.setdefault(id(stmts[-2]), ([],start[0]))
                    docstrings[id(stmts[-2])][0].append(s)
    
                # Is this token a comment docstring?
                if (typ == tokenize.COMMENT and stmts[-1] is not None and
                    tok.startswith(self.COMMENT_MARKER)):
                    s = tok[len(self.COMMENT_MARKER):].rstrip()
                    docstrings.setdefault(id(stmts[-1]), ([],start[0]))
                    docstrings[id(stmts[-1])][0].append(s)
                        
                if tok == ast: return
    
        # If `ast` is a non-leaf node, then explore its contents.
        else:
            if ast[0] == symbol.stmt: stmts.append(ast)
            for child in ast[1:]:
                self._find_docstrings_helper(child, filename, tokeniter, 
                                             docstrings, stmts)

    #////////////////////////////////////////////////////////////
    # Name Lookup
    #////////////////////////////////////////////////////////////

    def lookup_name(self, identifier):
        """
        Find and return the documentation for the variable named by
        the given identifier in the current namespace.
        
        @rtype: L{VariableDoc} or C{None}
        """
        assert type(identifier) == StringType
        
        # Decide which namespaces to check.  Note that, even if we're
        # in a version of python that uses nested scopes, it does not
        # look at intermediate class blocks.  E.g:
        #     >>> x = 1
        #     >>> class A:
        #     ...     x = 2
        #     ...     class B:
        #     ...         print x
        #     1
        namespaces = [self.builtins_moduledoc,
                      self.parentdocs[0],
                      self.parentdocs[-1]]

        # Check the namespaces, from closest to farthest.
        for i in range(len(namespaces)-1, -1, -1):
            # In classes, check local_variables.
            if isinstance(namespaces[i], ClassDoc):
                if namespaces[i].local_variables.has_key(identifier):
                    return namespaces[i].local_variables[identifier]
            # In modules, check variables.
            elif isinstance(namespaces[i], NamespaceDoc):
                if namespaces[i].variables.has_key(identifier):
                    return namespaces[i].variables[identifier]

        # We didn't find it; return None.
        return None

    def lookup_value(self, dotted_name):
        """
        Find and return the documentation for the value contained in
        the variable with the given name in the current namespace.
        """
        var_doc = self.lookup_name(dotted_name[0])

        for i in range(1, len(dotted_name)):
            if var_doc is None: return None
            
            if var_doc.value.imported_from not in (UNKNOWN, None):
                from_name = DottedName(var_doc.value.imported_from,
                                       *dotted_name[i:])
                return ValueDoc(imported_from=from_name)

            if isinstance(var_doc.value, ClassDoc):
                var_dict = var_doc.value.local_variables
            elif isinstance(var_doc.value, NamespaceDoc):
                var_dict = var_doc.value.variables
            else:
                return None

            var_doc = var_dict.get(dotted_name[i])

        if var_doc is None: return None
        return var_doc.value

    # [xx] not currently used by anything:
    def lookup_variable(self, dotted_name):
        """
        Find and return the documentation for the variable with the
        given name in the current namespace.
        """
        var_doc = self.lookup_name(dotted_name[0])
        
        for i in range(1, len(dotted_name)):
            if var_doc is None: return None
            if isinstance(var_doc.value, ClassDoc):
                var_dict = var_doc.value.local_variables
            elif isinstance(var_doc.value, NamespaceDoc):
                var_dict = var_doc.value.variables
            else:
                return None

            var_doc = var_dict.get(dotted_name[i])

        return var_doc

    #////////////////////////////////////////////////////////////
    # Extracting values & identifiers from AST
    #////////////////////////////////////////////////////////////

    def eval_strval(self, strval):
        # use compiler.parse, since it's safer than eval().
        return compiler.parse(strval).getChildren()[0]

    __TEST_ATOM_PATTERN = compile_ast_matcher("""
        (test (and_test (not_test (comparison (expr (xor_expr
         (and_expr (shift_expr (arith_expr (term (factor 
          (power (atom ...):atom))))))))))))""")

    __PAREN_PATTERN = compile_ast_matcher("""
        (testlist (test (and_test (not_test (comparison (expr (xor_expr 
         (and_expr (shift_expr (arith_expr (term (factor (power
            (atom LPAR (testlist ...):contents RPAR))))))))))))))""")

    def extract_list(self, ast, elt_handler):
        testlist_gexp = getattr(symbol, 'testlist_gexp', -1)
        if ast[0] not in (symbol.testlist, symbol.listmaker,
                          testlist_gexp):
            raise ValueError('Could not extract list')

        # Does ast contain a tuple?
        if (ast[0] in (symbol.testlist, testlist_gexp) and
            len(ast) > 2):
            return tuple(self._extract_list_items(ast, elt_handler))

        # Does ast contain a list?
        if ast[0] == symbol.listmaker:
            if len(ast) > 2 and ast[2][0] == symbol.list_for:
                raise ValueError('Could not extract list')
            return self._extract_list_items(ast, elt_handler)

        # Does ast contain parens for a tuple or brackets for a list?
        match, vars = self.__TEST_ATOM_PATTERN.match(ast[1])
        if match:
            atom = vars['atom']
            if len(atom) == 4 and atom[1][0] in (token.LSQB, token.LPAR):
                return self.extract_list(atom[2], elt_handler)
            elif len(atom) == 3 and atom[1][0] == token.LSQB:
                return []
            elif len(atom) == 3 and atom[1][0] == token.LPAR:
                return ()
            else:
                return elt_handler(ast[1])

        # Otherwise, fail.
        raise ValueError('Could not extract list')

    def _extract_list_items(self, ast, elt_handler):
        testlist_gexp = getattr(symbol, 'testlist_gexp', -1)
        assert ast[0] in (symbol.testlist, symbol.listmaker,
                          testlist_gexp)
        elts = []
        for child in ast[1:]:
            if child[0] == token.COMMA: continue
            match, vars = self.__TEST_ATOM_PATTERN.match(child)
            if match:
                atom = vars['atom']
                if (len(atom) == 4 and 
                    atom[1][0] in (token.LSQB, token.LPAR)):
                    elts.append(self.extract_list(atom[2], elt_handler))
                else:
                    elts.append(elt_handler(child))
            else:
                elts.append(elt_handler(child))
        return elts

    def extract_string(self, ast):
        # Walk down the syntax tree to symbol.atom.  If the tree
        # branches or we get to a token first, then abort.
        while ast[0] != symbol.atom:
            if len(ast)!=2 or type(ast[1]) == StringType:
                raise ValueError('ast does not contain a string')
            ast = ast[1]

        # If the atom doesn't contain a string, return None.
        if ast[1][0] != token.STRING:
            raise ValueError('ast does not contain a string')

        # Otherwise, return the string.
        return ''.join([self.eval_strval(tok[1]) for tok in ast[1:]])
        
    def extract_string_list(self, ast):
        return self.extract_list(ast, self.extract_string)

    def extract_dotted_name_list(self, ast):
        # It might be a single name:
        n = self.extract_dotted_name(ast)
        if n is not None: return [n]
        # Otherwise try a list:
        return self.extract_list(ast, self.extract_dotted_name)

    __DOTTED_NAME_PATTERN = compile_ast_matcher("""
        (power (atom NAME:varname) (trailer DOT NAME)*:trailers)""")
    def extract_dotted_name(self, ast):
        """
        Given an abstract syntax tree containing a single dotted name,
        return a corresponding L{DottedName} object.  (If the given
        ast does not contain a dotted name, return C{None}.)
        """
        # Walk down the syntax tree to symbol.power or
        # symbol.dotted_name.  If the tree branches or we get to a
        # token first, then return None.
        while ast[0] not in (symbol.power, symbol.dotted_name):
            if len(ast)!=2 or type(ast[1]) == StringType: return None
            ast = ast[1]

        if ast[0] == symbol.dotted_name:
            idents = [e[1] for e in ast[1:] if e[0] == token.NAME]
            return DottedName(*idents)
        else:
            match, vars = self.__DOTTED_NAME_PATTERN.match(ast)
            if not match: return None
            atom = vars['varname']
            trailers = [t[2][1] for t in vars['trailers']]
            return DottedName(atom, *trailers)
    







######################################################################
## Helper Functions
######################################################################

def _get_module_name(filename, package_doc):
    """
    Return (dotted_name, is_package)
    """
    name = re.sub(r'.py\w?$', '', os.path.split(filename)[1])
    if name == '__init__':
        is_package = True
        name = os.path.split(os.path.split(filename)[0])[1]
    else:
        is_package = False
        
    # [XX] if the module contains a script, then `name` may not
    # necessarily be a valid identifier -- which will cause
    # DottedName to raise an exception.  Is that what I want?
    if package_doc is None:
        return DottedName(name), is_package
    else:
        return DottedName(package_doc.canonical_name, name), is_package

def pp_ast(ast, indent=''):
    r"""
    Display a Python syntax tree in a human-readable format.  E.g.:

    >>> print pp_ast(parser.suite('\ndel x\n').tolist())
    
    @param ast: The syntax tree to display, enocded as nested lists
        or nested tuples.
    """
    if type(ast) is StringType:
        return repr(ast)
    else:
        if symbol.sym_name.has_key(ast[0]):
            s = '(symbol.%s' % symbol.sym_name[ast[0]]
        else:
            s = '(token.%s' % token.tok_name[ast[0]]
        for arg in ast[1:]:
            s += ',\n%s  %s' % (indent, pp_ast(arg, indent+' '))
        return s + ')'

def flatten(lst, out=None):
    """
    @return: a flat list containing the leaves of the given nested
        list.
    @param lst: The nested list that should be flattened.
    """
    if out is None: out = []
    for elt in lst:
        if isinstance(elt, (list, tuple)):
            flatten(elt, out)
        else:
            out.append(elt)
    return out

def ast_to_string(ast, spacing='normal', indent=0):
    """
    Given a Python parse tree, return a string that could be parsed to
    produce that tree.
    @param ast: The Python syntax tree, enocded as nested lists or
        nested tuples.
    @param spacing: 'tight' or 'normal' -- determines how much space is
        left between tokens (e.g., '1+2' vs '1 + 2').
    """
    if type(ast[0]) is IntType:
        ast = ast[1:]

    s = ''
    for elt in ast:
        # Put a blank line before class & def statements.
        if elt == (token.NAME, 'class') or elt == (token.NAME, 'def'):
            s += '\n%s' % ('    '*indent)

        if type(elt) is not TupleType and type(elt) is not ListType:
            s += str(elt)
        elif elt[0] == token.NEWLINE:
            s += '    '+elt[1]
            s += '\n%s' % ('    '*indent)
        elif elt[0] == token.INDENT:
            s += '    '
            indent += 1
        elif elt[0] == token.DEDENT:
            assert s[-4:] == '    '
            s = s[:-4]
            indent -= 1
        elif elt[0] == tokenize.COMMENT:
            s += elt[1].rstrip() + '\n' + '    '*indent
        else:
            s = _ast_string_join(s, ast_to_string(elt, spacing, indent),
                                 spacing)

    return s

def _ast_string_join(left, right, spacing):
    if (right=='' or left=='' or
        left in '-`' or right in '}])`:' or
        right[0] in '.,' or left[-1] in '([{.\n ' or
        (right[0] == '(' and left[-1] not in ',=')):
        return '%s%s' % (left, right)
    elif (spacing=='tight' and
          left[-1] in '+-*/=,' or right[0] in '+-*/=,'):
        return '%s%s' % (left, right)
    else:
        return '%s %s' % (left, right)

# rename to augment_ast; add comments, and record line numbers.
# where to record line numbers???















def add_comments_to_ast(ast, filename):
    """
    Given a Python syntax tree and the filename of the file that it
    was generated from, insert COMMENT nodes into the tree.
    """
    # Tokenize the given file.
    tokens = []
    def tokeneater(typ,tok,start,end,line,tokens=tokens):
        print 'tokeneater', (typ, tok, start, end, line)
        lineno = start[0]
        print '  lineno', lineno
        tokens.append((typ,tok))
    tokenize.tokenize(open(filename).readline, tokeneater)

    # Reverse the tokens (so we can pop them off one at a time).
    tokens.append((tokenize.NEWLINE, '\n'))
    tokens.reverse()

    # Call our helper function to do the real work.
    try: _add_comments_to_ast_helper(ast, tokens, None)
    except IndexError:
        raise ValueError, 'Unable to align tokens to ast'

def _add_comments_to_ast_helper(ast, reversed_tokens, stmt):
    """
    Add comments to the syntax tree for a Python module.
    """
    if ast == '':
        return
    elif type(ast) is StringType:
        while reversed_tokens:
            # Find a token to match the ast leaf.
            typ,tok = reversed_tokens.pop()
            if tok == ast: break
            # Attatch comments to the enclosing statement node.
            if typ == tokenize.COMMENT and stmt is not None:
                if tok.endswith('\n'): tok = tok[:-1]
                stmt.insert(-1, (tokenize.COMMENT, tok))
    else:
        # If we're entering a statement, update stmt.
        if ast[0] == symbol.stmt:
            stmt = ast

        # Recurse to our variables.
        for child in ast[1:]:
            _add_comments_to_ast_helper(child, reversed_tokens, stmt)

def main():
    from docinspector import DocInspector
    inspector = DocInspector()
    parser = DocParser(inspector.inspect(__builtins__))

    import sys
    print parser.find(sys.argv[1])

if __name__ == '__main__':
    main()
