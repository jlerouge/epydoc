"""
API documentation extraction based on source code parsing.  The
L{DocParser} class parses the source code from individual modules, and
generates C{ModuleDocs} that contain their API documentation.
"""

######################################################################
## Debugging
######################################################################

# Force reload of volatile modules:
import epydoc.astmatcher; reload(epydoc.astmatcher); del epydoc.astmatcher
import epydoc.apidoc; reload(epydoc.apidoc); del epydoc.apidoc
    
######################################################################
## Imports
######################################################################

# Python source code parsing:
import parser, symbol, token, tokenize
# File services:
import os, os.path
# API documentation encoding:
from epydoc.apidoc import *
# Syntax tree matching:
from epydoc.astmatcher import compile_ast_matcher
# Type comparisons:
from types import StringType, ListType, TupleType, IntType

True = getattr(__builtins__, 'True', 1)   #: For backwards compatibility
False = getattr(__builtins__, 'False', 0) #: For backwards compatibility

######################################################################
## Doc Parser
######################################################################

class DocParser:
    """    
    An API documentation extractor based on source code parsing.
    C{DocParser} parses the source code from individual modules, and
    generates C{ModuleDocs} that contain their API documentation.

    C{DocParser} extracts documentation from the following source code
    constructions:
    
      - class definition blocks (C{class M{c}(...): ...})
      - function definition blocks (C{def M{f}(...): ...})
      - assignment statements, including assignment statements
        with multiple left-hand sides and with complex left-hand
        sides.

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

      - A subclass can override various helper methods to customize
        the behavior of the handler methods.  Some likely candidates
        are L{rhs_to_valuedoc}, ....

    @group Entry Point: parse
    @group Parse Handler Methods: parse_import, parse_classdef,
        parse_funcdef, parse_simple_assignment,
        parse_complex_assignment, parse_multi_assignment, parse_try,
        parse_if, parse_while, parse_for, parse_multi_stmt
    @group Docstring Extraction: get_docstring, get_pseudo_docstring,
        get_comment_docstring
    @group Name Lookup: lookup_name, lookup_dotted_name
    @group Identifier Parsing: testlist_to_dotted_names,
        ast_to_dotted_name, _power_to_dotted_name

    @group Configuration Constants: USE_NESTED_SCOPES, PARSE_*
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

    #////////////////////////////////////////////////////////////
    # Configuration Constants
    #////////////////////////////////////////////////////////////

    #: Should nested scopes be used for name lookup?
    USE_NESTED_SCOPES = True
    #: Should the contents of C{try} blocks be examined?
    PARSE_TRY_BLOCKS = True
    #: Should the contents of C{except} blocks be examined?
    PARSE_EXCEPT_BLOCKS = True
    #: Should the contents of C{finally} blocks be examined?
    PARSE_FINALLY_BLOCKS = True
    #: Should the contents of C{if} blocks be examined?
    PARSE_IF_BLOCKS = True
    #: Should the contents of C{else} and C{elif} blocks be examined?
    PARSE_ELSE_BLOCKS = True
    #: Should the contents of C{while} blocks be examined?
    PARSE_WHILE_BLOCKS = False
    #: Should the contents of C{for} blocks be examined?
    PARSE_FOR_BLOCKS = False

    #////////////////////////////////////////////////////////////
    # Entry Point
    #////////////////////////////////////////////////////////////

    def parse(self, filename):
        """
        Parse the given python module, and return a C{ModuleDoc}
        containing its API documentation.
        
        @param filename: The filename of the module to parse.
        @type filename: C{string}
        @rtype: L{ModuleDoc}
        """
        # Find the basedir of the package & the full module name.
        (basedir, module_name) = _find_module_from_filename(filename)

        # Create a new ModuleDoc for the module.
        moduledoc = ModuleDoc(dotted_name=module_name)

        # Initialize the context & the parentdocs stack.
        self.context = module_name
        self.parentdocs = [moduledoc]
        
        # Read the source code & parse it into a syntax tree.
        try:
            # Read the source file, and fix up newlines.
            source_code = open(filename).read()
            ast = parser.suite(source_code.replace('\r\n','\n')+'\n')
            # Parse the source file into a syntax tree.
            ast = ast.tolist()
            # Add comments to the syntax tree.
            add_comments_to_ast(ast, filename)
        except:
            raise
            return None # Couldn't parse it!

        # Parse each statement in the (comment-agumented) syntax tree.
        self.process_suite(ast)

        # Return the completed ModuleDoc
        return self.parentdocs[0]

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

        The handler method is called with parameters based on the
        matcher's variables.  The handler is also given one additional
        parameter, C{pseudo_docstring}: if the statement is
        immediately followed by a string constant, then
        C{pseudo_docstring} is the contents of that string constant;
        otherwise, C{pseudo_docstring} is C{None}.
    
        @param suite: A Python syntax tree containing the suite to be
            processed (as generated by L{parser.ast2list}).
        @type suite: C{list}
        @rtype: C{None}
        """
        assert suite[0] in (symbol.file_input, symbol.suite)
        stmts = suite[1:]
        for i in range(len(stmts)):
            # Check if stmts[i] matches any of our statement patterns.
            for (name, matcher) in self.STMT_PATTERNS:
                match, vars = matcher.match(stmts[i])
                if match:
                    # Check for a pseudo-docstring.
                    docstring = self.get_pseudo_docstring(stmts, i)
                    # Delegate to the appropriate handler.
                    handler_method = getattr(self, name)
                    handler_method(pseudo_docstring=docstring, **vars)
                    break
        
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
    #: C{pseudo_docstring}: if the statement is immediately followed
    #: by a string constant, then C{pseudo_docstring} is the contents
    #: of that string constant; otherwise, C{pseudo_docstring} is
    #: C{None}.
    #:
    #: If no matchers match a statement, then that statement is
    #: ignored.
    STMT_PATTERNS = [
        # Import statement: "import foo"
        ('process_import', compile_ast_matcher("""
            (stmt COMMENT*
             (simple_stmt
              (small_stmt
               (import_stmt NAME:cmd (...)*:names))
              NEWLINE))""")),
        # Class definition: "class A(B): ..."
        ('process_classdef', compile_ast_matcher("""
            (stmt COMMENT*
             (compound_stmt (classdef
                NAME
                NAME:classname
                LPAR? (testlist...)?:bases RPAR?
                COLON
                (suite ...):body)))""")),
        # Function definition: "def f(x): ..."
        ('process_funcdef', compile_ast_matcher("""
            (stmt COMMENT*
             (compound_stmt (funcdef
                NAME
                NAME:funcname
                (parameters ...):parameters
                COLON
                (suite ...): body)))""")),
        # Simple assignment: "x=y" or "x.y=z"
        ('process_simple_assignment', compile_ast_matcher("""
            (stmt COMMENT*:comments
             (simple_stmt (small_stmt (expr_stmt
              (testlist (test (and_test (not_test (comparison (expr
               (xor_expr (and_expr (shift_expr (arith_expr (term
                (factor (power (atom NAME)
                               (trailer DOT NAME)*))))))))))))):lhs
              EQUAL (...):rhs)) NEWLINE:nl_comment))""")),
        # Complex-LHS assignment: "(a,b)=c" or "[a,b]=c"
        ('process_complex_assignment', compile_ast_matcher("""
            (stmt COMMENT*
             (simple_stmt (small_stmt (expr_stmt
              (testlist...):lhs EQUAL (...):rhs)) NEWLINE))""")),
        # Multi assignment: "a=b=c"
        ('process_multi_assignment', compile_ast_matcher("""
            (stmt COMMENT*
             (simple_stmt (small_stmt (expr_stmt
              (testlist...):lhs EQUAL
              (...)*:rhs)) NEWLINE))""")),
        # Try stmt
        ('process_try', compile_ast_matcher("""
            (stmt COMMENT*
             (compound_stmt
              (try_stmt NAME COLON (suite ...):trysuite
              (...)*:rest)))""")),
        # If-then statement
        ('process_if', compile_ast_matcher("""
            (stmt COMMENT*
             (compound_stmt
              (if_stmt NAME (test ...) COLON (suite ...):ifsuite
               NAME? (test ...)? COLON? (suite ...)?:elifsuite
               NAME? COLON? (suite ...)?:elsesuite)))""")),
        # While statement
        ('process_while', compile_ast_matcher("""
            (stmt COMMENT*
             (compound_stmt
              (while_stmt NAME (test ...) COLON (suite ...):whilesuite
               NAME? COLON? (suite ...)?:elsesuite)))""")),
        # For stmt
        ('process_for', compile_ast_matcher("""
            (stmt COMMENT*
             (compound_stmt
              (for_stmt NAME (exprlist...):loopvar NAME 
               (testlist...) COLON (suite ...):forsuite
               NAME? COLON? (suite ...)?:elsesuite)))""")),
        # Semicolon-separated statements: "x=1; y=2"
        ('process_multi_stmt', compile_ast_matcher("""
            (stmt COMMENT*
             (simple_stmt
              (small_stmt ...):stmt1
              SEMI
              (...)*:rest))""")),
        ]

    #////////////////////////////////////////////////////////////
    # Parse Handler: Imports
    #////////////////////////////////////////////////////////////
     
    def process_import(self, cmd, names, pseudo_docstring):
        """
        The statement handler for import statements.  This handler
        adds a C{VariableDoc} to the parent C{APIDoc} for each name
        that is created by importing.  These C{VariableDoc}s have
        empty C{ValueDoc}s, and are marked as imported (i.e.,
        C{L{is_imported<VariableDoc.is_imported>}=True}).

        @param cmd: The import command (C{'from'} or C{'import'}
        @param nams: The contents of the import statement, from
            which the import names are taken.
        @param pseudo_docstring: The pseudo-docstring for the
            import statement (ignored).
        @rtype: C{None}
        """
        # If we're not in a namespace, then ignore import statements.
        parentdoc = self.parentdocs[-1]
        if not isinstance(parentdoc, NamespaceDoc): return

        # Create a list of the variable names created by the import:
        varnames = []

        # from module import *
        if cmd == 'from' and names[-1][0] == token.STAR:
            return # Not much we can do. :-/

        # from __future__ import ...
        elif cmd == 'from' and names[0][1][1] == '__future__':
            return # Ignore __future__ statements.

        # import module1 [as name1], ...
        elif cmd == 'import':
            for name in names:
                if name[0] == symbol.dotted_as_name:
                    # dotted_as_name: dotted_name
                    if len(name) == 2:
                        varnames.append(name[1][1][1])
                    # dotted_as_name: dotted_name 'as' NAME
                    elif len(name) == 4:
                        varnames.append(name[3][1])
                        
        # from module import name1 [as alias1], ...
        elif (cmd == 'from' and names[-1][0] != token.STAR and
              names[0][1][1] != '__future__'):
            for name in names[2:]:
                if name[0] == symbol.import_as_name:
                    # import_as_name: NAME
                    if len(name) == 2:
                        varnames.append(name[1][1])
                    # import_as_name: import_name 'as' NAME
                    elif len(name) == 4:
                        varnames.append(name[3][1])
                        
        # Add all the variables we found.
        for varname in varnames:
            vardoc = VariableDoc(varname, ValueDoc(), is_alias=0,
                                 is_imported=1)
            parentdoc.children[varname] = vardoc

    #////////////////////////////////////////////////////////////
    # Parse Handler: Simple Assignments
    #////////////////////////////////////////////////////////////

    def process_simple_assignment(self, comments, lhs, rhs, nl_comment,
                                  pseudo_docstring):
        """
        The statement handler for assignment statements whose
        left-hand side is a single identifier.  The behavior of this
        handler depends on the contents of the assignment statement
        and the context:

          - If the assignment statement occurs inside an __init__
            function, and is documented by a pseudo-docstring or
            comments, then the handler creates a new C{VariableDoc}
            in the containing class and sets
            C{L{is_instvar<VariableDoc.is_instvar>}=True}.

          - If the assignment's right-hand side is a single identifier
            with a known value, then the handler creates a new
            C{VariableDoc} in the containing namespace whose
            C{valuedoc} is that value's documentation, and sets
            C{L{is_alias<VariableDoc.is_alias>}=True}.

          - Otherwise, the handler creates a new C{VariableDoc} in the
            containing namespace, whose C{ValueDoc} is computed from
            the right-hand side by L{rhs_to_valuedoc}.

        @param comments: The comments preceeding the assignment
            statement (if any).
        @param lhs: The left-hand side of the assignment statement.
        @param rhs: The right-hand side of the assignment statement.
        @param nl_comment: The comment on the same line as the
            assignment statement (if any).
        @param pseudo_docstring: The pseudo-docstring for the
            assignment statement (if any).
        @rtype: C{None}
        """
        # The APIDoc for our container.
        parentdoc = self.parentdocs[-1]

        is_alias = 0        # Is the variable an alias?
        is_instvar = 0      # Is the variable an instance variable?
        docstring = None    # What's the variable's docstring?
        valuedoc = None     # What's the variable's value?
        
        # Get the variable's docstring, if it has one.  Check for a
        # pseudo-docstring first, and then look in its comments.
        if pseudo_docstring is not None:
            docstring = pseudo_docstring
        else:
            docstring = self.get_comment_docstring(comments, nl_comment)

        # Extract the var name from the left-hand side.  If the
        # left-hand side isn't a var name, then just return.
        var_dotted_name = self.ast_to_dotted_name(lhs)
        if var_dotted_name is None: return

        # Inside __init__ functions, look for instance variables.
        if self._inside_init():
            # To be recorded, instance variables must have the form
            # "self.x", and must have a non-empty docstring.
            if (docstring is None or len(var_dotted_name) != 2 or
                len(parentdoc.args) == 0 or
                var_dotted_name[0] != parentdoc.args[0].name):
                return
            valuedoc = ValueDoc(repr=ast_to_string(rhs))
            is_instvar = 1
            # Set parentdoc to the containing class.
            parentdoc = self.parentdocs[-2]

        # Outside __init__, ignore any assignment to a dotted name
        # with more than one identifier (e.g. "a.b.c").
        if valuedoc is None and len(var_dotted_name) > 1: return
        varname = var_dotted_name[-1]

        # If the RHS is a single identifier that we have a value for,
        # then create an alias variable.
        if valuedoc is None and rhs[0] == symbol.testlist:
            rhs_dotted_name = self.ast_to_dotted_name(rhs)
            if rhs_dotted_name is not None:
                valuedoc = self.lookup_dotted_name(rhs_dotted_name)
                if valuedoc is not None:
                    is_alias = 1
                
        # Otherwise, use rhs_to_valuedoc to find a valuedoc for rhs.
        if valuedoc is None:
            valuedoc = self.rhs_to_valuedoc(rhs)

        # Create the VariableDoc, and add it to its parent.
        vardoc = VariableDoc(varname, valuedoc, is_imported=0,
                             is_alias=is_alias, is_instvar=is_instvar,
                             docstring=docstring)

        if isinstance(parentdoc, NamespaceDoc):
            parentdoc.add_child(vardoc)

    #: A pattern matcher used to find C{classmethod} and
    #: C{staticmethod} wrapper functions on the right-hand side
    #: of assignment statements.
    WRAPPER_PATTERN = compile_ast_matcher("""
        (testlist (test (and_test (not_test (comparison (expr
         (xor_expr (and_expr (shift_expr (arith_expr (term (factor
          (power (atom NAME:funcname)
           (trailer LPAR (arglist (argument (test (and_test (not_test
            (comparison (expr (xor_expr (and_expr (shift_expr
             (arith_expr (term (factor
              (power (atom NAME) (trailer DOT NAME)*):arg)))))))))))))
            RPAR))))))))))))))""")

    def rhs_to_valuedoc(self, rhs):
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
        match, vars2 = self.WRAPPER_PATTERN.match(rhs)
        if match:
            arg_dotted_name = self.ast_to_dotted_name(vars2['arg'])
            arg_valuedoc = self.lookup_dotted_name(arg_dotted_name)
            if (arg_valuedoc is not None and
                isinstance(arg_valuedoc, RoutineDoc)):
                if vars2['funcname'] == 'classmethod':
                    return cm_doc_from_routine_doc(arg_valuedoc)
                elif vars2['funcname'] == 'staticmethod':
                    return sm_doc_from_routine_doc(arg_valuedoc)
        
        # Otherwise, it's a simple assignment
        return ValueDoc(repr=ast_to_string(rhs))

    #////////////////////////////////////////////////////////////
    # Parse Handler: Complex Assignments
    #////////////////////////////////////////////////////////////

    def process_complex_assignment(self, lhs, rhs, pseudo_docstring):
        """
        The statement handler for assignment statements whose
        left-hand side is a single complex expression, such as a tuple
        or list.  This handler creates a new C{VariableDoc} in the
        containing namespace for each non-dotted variable name on the
        left-hand side.  The pseudo-docstring and right-hand side are
        ignored.

        @param lhs: The left-hand side of the assignment statement.
        @param rhs: The right-hand side of the assignment statement.
        @param pseudo_docstring: The pseudo-docstring for the
            assignment statement (ignored).
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
        lhs = self.testlist_to_dotted_names(lhs)

        # Otherwise, just create VariableDocs in the namespace.
        for dotted_name in flatten(lhs):
            if len(dotted_name) == 1:
                varname = dotted_name[0]
                vardoc = VariableDoc(varname, ValueDoc(),
                                     is_imported=False)
                parentdoc.children[varname] = vardoc

    #////////////////////////////////////////////////////////////
    # Parse Handler: Multi-Assignments
    #////////////////////////////////////////////////////////////

    def process_multi_assignment(self, lhs, rhs, pseudo_docstring):
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
        @param pseudo_docstring: The pseudo-docstring for the
            assignment statement (ignored).
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

    def process_try(self, trysuite, rest, pseudo_docstring):
        """
        The statement handler for C{try} blocks.  This handler calls
        C{process_suite} on the suites contained by the C{try} block.

        @param trysuite: The contents of the C{try} block.
        @param rest: The contents of the C{finally/except/else} blocks.
        @param pseudo_docstring: The pseudo-docstring for the
            C{try} statement (ignored).
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
    
    def process_if(self, ifsuite, elifsuite, elsesuite, pseudo_docstring):
        """
        The statement handler for C{if} blocks.  This handler calls
        C{process_suite} on the suites contained by the C{if} block.

        @param ifsuite: The contents of the C{if} block.
        @param elifsuite: The contents of the C{elif} block.
        @param elsesuite: The contents of the C{else} block.
        @param pseudo_docstring: The pseudo-docstring for the
            C{if} statement (ignored).
        @rtype: C{None}
        """
        if self.PARSE_IF_STMT:
            self.process_suite(ifsuite)
        if self.PARSE_ELSE_BLOCKS:
            if elifsuite is not None:
                self.process_suite(elifsuite)
            if elsesuite is not None:
                self.process_suite(elsesuite)

    def process_while(self, whilesuite, elsesuite, pseudo_docstring):
        """
        The statement handler for C{while} blocks.  This handler calls
        C{process_suite} on the suites contained by the C{while}
        block.

        @param whilesuite: The contents of the C{while} block.
        @param elsesuite: The contents of the C{else} block.
        @param pseudo_docstring: The pseudo-docstring for the
            C{while} statement (ignored).
        @rtype: C{None}
        """
        if self.PARSE_WHILE_BLOCKS:
            self.process_suite(whilesuite)
            if elsesuite is not None:
                self.process_suite(elsesuite)
        
    def process_for(self, loopvar, forsuite, elsesuite, pseudo_docstring):
        """
        The statement handler for C{for} blocks.  This handler calls
        C{process_suite} on the suites contained by the C{for} block;
        and creates a C{VariableDoc} in the containing namespace for
        the loop variable.

        @param loopvar: The loop variable.
        @param forsuite: The contents of the C{for} block.
        @param elsesuite: The contents of the C{else} block.
        @param pseudo_docstring: The pseudo-docstring for the
            C{for} statement (ignored).
        @rtype: C{None}
        """
        # The APIDoc for our container.
        parentdoc = self.parentdocs[-1]
        
        if self.PARSE_FOR_BLOCKS:
            self.process_suite(forsuite)
            if elsesuite is not None:
                self.process_suite(elsesuite)
                
            # Create a VariableDoc for the loop variable.
            loopvar_dotted_name = self.ast_to_dotted_name(loopvar)
            if len(loopvar_dotted_name) == 1:
                loopvar_name = loopvar_dotted_name[0]
                vardoc = VariableDoc(loopvar_name, ValueDoc(),
                                     is_imported=False)
                if isinstance(parentdoc, NamespaceDoc):
                    parentdoc.children[loopvar_name] = vardoc

    #////////////////////////////////////////////////////////////
    # Parse Handler: Function Definitions
    #////////////////////////////////////////////////////////////

    def process_funcdef(self, funcname, parameters, body, pseudo_docstring):
        """
        The statement handler for function definition blocks.  This
        handler constructs the documentation for the function, and
        adds it to the containing namespaces.  If the function is a
        method's C{__init__} method, then it calls L{process_suite} to
        process the function's body.

        @param funcname: The name of the function.
        @param parameters: The function's parameter list.
        @param body: The function's body.
        @param pseudo_docstring: The pseudo-docstring for the
            function definition (ignored).
        @rtype: C{None}
        """
        # If we're not in a namespace, then ignore the funcdef.
        parentdoc = self.parentdocs[-1]
        if not isinstance(parentdoc, NamespaceDoc): return
        
        # Create the function's RoutineDoc & VariableDoc.
        if isinstance(self.parentdocs[-1], ClassDoc):
            funcdoc = InstanceMethodDoc()
        else:
            funcdoc = RoutineDoc()
        vardoc = VariableDoc(funcname, funcdoc, is_imported=False,
                             is_alias=False)

        # Add the VariableDoc to our container.
        parentdoc.add_child(vardoc)
        
        # Add the function's parameters.
        self._add_parameters(parameters, funcdoc)

        # Add the function's docstring.
        funcdoc.docstring = self.get_docstring(body)

        # Add the function's canonical name
        funcdoc.dotted_name = DottedName(self.context, funcname)
        
        # Parse the suite (if we're in an __init__ method).
        if self._inside_init():
            self.context = DottedName(self.context, funcname)
            self.parentdocs.append(funcdoc)
            self.process_suite(body)
            self.context = DottedName(*self.context[:-1])
            self.parentdocs.pop()

    def _add_parameters(self, parameters, funcdoc):
        """
        Set C{funcdoc}'s parameter fields (C{args}, C{vararg}, and
        C{kwarg}) based on C{parameters}.
        
        @param parameters: The syntax tree for the function's
           parameter list (as generated by L{parser.ast2list}).
        """
        # parameters: '(' [varargslist] ')'
        if len(parameters) == 3: return
        varargslist = parameters[2]

        # Check for kwarg.
        if len(varargslist) > 3 and varargslist[-2][0] == token.DOUBLESTAR:
            funcdoc.kwarg = ArgDoc(varargslist[-1][1])
            del varargslist[-3:]

        # Check for vararg.
        if len(varargslist) > 3 and varargslist[-2][0] == token.STAR:
            funcdoc.vararg = ArgDoc(varargslist[-1][1])
            del varargslist[-3:]

        # The rest should all be fpdef's.
        funcdoc.args = []
        for elt in varargslist[1:]:
            if elt[0] == symbol.fpdef:
                funcdoc.args.append(ArgDoc(self._fpdef_to_name(elt)))
            elif elt[0] == symbol.test:
                funcdoc.args[-1].default = ast_to_string(elt)

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
    # Parse Handler: Class Definitions
    #////////////////////////////////////////////////////////////

    def process_classdef(self, classname, bases, body, pseudo_docstring):
        """
        The statement handler for class definition blocks.  This
        handler constructs the documentation for the class, and adds
        it to the containing namespaces.  The handler then calls
        L{process_suite} to process the class's body.

        @param classname: The name of the class
        @param bases: The class's base list
        @param body: The class's body
        @param pseudo_docstring: The pseudo-docstring for the class
            definition (ignored).
        @rtype: C{None}
        """
        # If we're not in a namespace, then ignore the classdef.
        parentdoc = self.parentdocs[-1]
        if not isinstance(parentdoc, NamespaceDoc): return
        
        # Create the class's ClassDoc & VariableDoc.
        classdoc = ClassDoc()
        vardoc = VariableDoc(classname, classdoc, is_imported=False,
                             is_alias=False)

        # Add the VariableDoc to our container.
        parentdoc.add_child(vardoc)

        # Find our base classes.
        if bases is not None:
            base_dotted_names = self.testlist_to_dotted_names(bases)
            for base in base_dotted_names:
                valuedoc = self.lookup_dotted_name(base)
                if valuedoc is not None:
                    classdoc.bases.append(valuedoc)
                else:
                    # Unknown base!
                    classdoc.bases.append(ClassDoc())

        # Register ourselves as a subclass.
        for basedoc in classdoc.bases:
            basedoc.subclasses.append(classdoc)
        
        # Add the class's docstring.
        classdoc.docstring = self.get_docstring(body)
        
        # Add the class's canonical name
        classdoc.dotted_name = DottedName(self.context, classname)
        
        # Parse the suite.
        self.context = DottedName(self.context, classname)
        self.parentdocs.append(classdoc)
        self.process_suite(body)
        self.context = DottedName(*self.context[:-1])
        self.parentdocs.pop()
     
    #////////////////////////////////////////////////////////////
    # Parse Handler: Semicolon-Separated Statements
    #////////////////////////////////////////////////////////////

    def process_multi_stmt(self, stmt1, rest, pseudo_docstring):
        """
        The statement handler for a set of semicolon-separated
        statements, such as:
        
            >>> x=1; y=2; z=3
            
        This handler wraps the individual statements in a suite, and
        delegates to C{process_suite}.
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
    # Docstring Extraction
    #////////////////////////////////////////////////////////////
     
    _STRING_STMT_PATTERN = compile_ast_matcher("""
        (stmt (simple_stmt (small_stmt (expr_stmt (testlist (test
          (and_test (not_test (comparison (expr (xor_expr (and_expr
            (shift_expr (arith_expr (term (factor (power (atom
              STRING:stringval)))))))))))))))) NEWLINE))""")
    """A pattern matcher that matches a statement containing a single
    string literal.  This pattern matcher is used to find docstrings
    and pseudo-docstrings."""

    COMMENT_MARKER = '#: '
    """The prefix used to mark comments that contain pseudo-docstrings
    for variables."""

    def get_docstring(self, suite):
        """
        @return: The docstring for the given suite.  I.e., if the
        first statement in C{suite} is a string literal, then return
        its contents; otherwise, return C{None}.
        @rtype: C{string} or C{None}
        """
        # Find the first statement in the suite.
        if len(suite) == 2 and suite[1][0] == symbol.simple_stmt:
            # suite: simple_stmt
            first_stmt = (symbol.stmt, suite[1])
        else:
            # suite: NEWLINE INDENT stmt+ DEDENT
            first_stmt = suite[3]

        # Match it against _STRING_STMT_PATTERN
        match, stmtvars = self._STRING_STMT_PATTERN.match(first_stmt)
        if match: return eval(stmtvars['stringval'])
        else: return None
            
    def get_pseudo_docstring(self, stmts, i):
        """
        @return: The pseudo-docstring for statement C{stmts[i]}, if it
        has one.  I.e., if C{stmts[i+1]} is a string literal, then
        return its contents; otherwise, return C{None}.
        @rtype: C{string} or C{None}
        """
        if i+1 < len(stmts):
            match, vars = self._STRING_STMT_PATTERN.match(stmts[i+1])
            if match: return eval(vars['stringval'])
        return None

    def get_comment_docstring(self, comments, nl_comment=''):
        """
        @return: The pseudo-docstring contained in a statement's
            comments.  Each line of a pseudo-docstring comment must
            begin with L{COMMENT_MARKER}.
        @rtype: C{string}
        @param comments: The comment lines preceeding the statement
        @param nl_comment: The comment on the same line as the
            statement (directly following it), or C{None} if there
            is none.
        """
        # Discard any comments that are not marked with the comment
        # marker.
        for i in range(len(comments)-1, -1, -1):
            if not comments[i].startswith(self.COMMENT_MARKER):
                del comments[:i+1]
                break

        # Add the newline comment on.
        if nl_comment.startswith(self.COMMENT_MARKER):
            comments.append(nl_comment)

        # If we didn't find anything, return None.
        if not comments: return None

        # Strip off the comment marker, and join them into one string.
        cm_len = len(self.COMMENT_MARKER)
        comments = [comment[cm_len:] for comment in comments]
        return '\n'.join(comments)

    #////////////////////////////////////////////////////////////
    # Name Lookup
    #////////////////////////////////////////////////////////////

    def lookup_name(self, name):
        """
        @rtype: L{ValueDoc}
        """
        assert type(name) == StringType
        
        # Decide which namespaces to check.
        if self.USE_NESTED_SCOPES:
            namespaces = [self.builtins_moduledoc] + self.parentdocs
        else:
            namespaces = [self.builtins_moduledoc,
                          self.parentdocs[0],
                          self.parentdocs[-1]]

        # Check the namespaces, from closest to farthest.
        for i in range(len(namespaces)-1, -1, -1):
            if isinstance(namespaces[i], NamespaceDoc):
                if namespaces[i].children.has_key(name):
                    return namespaces[i].children[name].valuedoc

        # We didn't find it; return None.
        return None

    def lookup_dotted_name(self, dotted_name):
        """
        @rtype: L{ValueDoc}
        """
        valuedoc = self.lookup_name(dotted_name[0])
        for ident in dotted_name[1:]:
            if valuedoc is None: return None
            if not isinstance(valuedoc, NamespaceDoc): return None
            valuedoc = valuedoc.children.get(ident).valuedoc
        return valuedoc

    #////////////////////////////////////////////////////////////
    # Identifier extraction
    #////////////////////////////////////////////////////////////

    LHS_PATTERN = compile_ast_matcher("""
        (test (and_test (not_test (comparison (expr (xor_expr
         (and_expr (shift_expr (arith_expr (term (factor 
          (power (atom...):atom (trailer DOT NAME)*):power)))))))))))""")

    def testlist_to_dotted_names(self, testlist):
        assert testlist[0] in (symbol.testlist, symbol.listmaker)
        names = []

        # Traverse the testlist, looking for variables.
        for test in testlist[1:]:
            match, vars = self.LHS_PATTERN.match(test)
            if match:
                atom = vars['atom']
                
                # Is it a name?
                if atom[1][0] == token.NAME:
                    names.append(self._power_to_dotted_name(vars['power']))

                # Is it a sub-list or sub-tuple?
                elif atom[1][0] in (token.LSQB, token.LPAR):
                    testlist = atom[2]
                    names.append(self.testlist_to_dotted_names(testlist))

        return names
     
    DOTTED_NAME_PATTERN = compile_ast_matcher("""
        (power (atom NAME:varname) (trailer DOT NAME)*:trailers)""")

    def ast_to_dotted_name(self, ast):
        # Walk down the syntax tree to symbol.power.  If the tree
        # branches or we get to a token first, then return None.
        while ast[0] != symbol.power:
            if len(ast)!=2 or type(ast[1]) == StringType: return None
            ast = ast[1]

        return self._power_to_dotted_name(ast)

    def _power_to_dotted_name(self, power_node):
        assert power_node[0] == symbol.power
        match, vars = self.DOTTED_NAME_PATTERN.match(power_node)
        if not match: return None
        atom = vars['varname']
        trailers = [t[2][1] for t in vars['trailers']]
        return DottedName(atom, *trailers)
    
######################################################################
## Helper Functions
######################################################################

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
    """
    Display a Python syntax tree in a human-readable format.
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
        if type(elt) is ListType:
            flatten(elt, out)
        else:
            out.append(elt)
    return out

def ast_to_string(ast, indent=0):
    """
    Given a Python parse tree, return a string that could be parsed to
    produce that tree.
    @param ast: The Python syntax tree.
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
            if s[-4:] != '    ':
                print `s[-10:]`
            assert s[-4:] == '    '
            s = s[:-4]
            indent -= 1
        elif elt[0] == tokenize.COMMENT:
            s += elt[1].rstrip() + '\n' + '    '*indent
        else:
            s = _ast_string_join(s, ast_to_string(elt, indent))

    return s

def _ast_string_join(left, right):
    if (right=='' or left=='' or
        left in '-`' or right in '}])`:' or
        right[0] in '.,' or left[-1] in '([{.\n ' or
        (right[0] == '(' and left[-1] not in ',=')):
        return '%s%s' % (left, right)
    else:
        return '%s %s' % (left, right)

def add_comments_to_ast(ast, filename):
    """
    Given a Python syntax tree and the filename of the file that it
    was generated from, insert COMMENT nodes into the tree.
    """
    
    # Tokenize the given file.
    tokens = []
    def tokeneater(typ,tok,start,end,line,tokens=tokens):
        tokens.append((typ,tok))
    tokenize.tokenize(open(filename).readline, tokeneater)

    # Reverse the tokens (so we can pop them off one at a time).
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
        while 1:
            # Find a token to match the ast leaf.
            typ,tok = reversed_tokens.pop()
            if tok == ast: break
            # Attatch comments to the enclosing statement node.
            if typ == tokenize.COMMENT and stmt is not None:
                if tok[-1] == '\n': tok = tok[:-1]
                stmt.insert(-1, (tokenize.COMMENT, tok))
    else:
        # If we're entering a statement, update stmt.
        if ast[0] == symbol.stmt:
            stmt = ast

        # Recurse to our children.
        for child in ast[1:]:
            _add_comments_to_ast_helper(child, reversed_tokens, stmt)

######################################################################
## Testing
######################################################################

if __name__ == '__main__':
    # Create a builtins moduledoc
    try: builtins_doc
    except:
        import docinspector
        builtins_doc = docinspector.DocInspector().inspect(__builtins__)
    
    print DocParser(builtins_doc).parse('epydoc_test.py').pp(depth=4,
                       exclude=['subclasses'])
