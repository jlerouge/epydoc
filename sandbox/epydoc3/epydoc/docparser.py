import parser, symbol, token, os, os.path
from apidoc import *
#import apidoc; reload(apidoc); from apidoc import *
import astmatcher; reload(astmatcher); from astmatcher import *
from types import *

# To build the ModuleDoc for __builtins__:
import docinspector

"""
2 use cases:
  - parsing from scratch
  - adding missed info
    - variable docstrings (string literal only)
    - imported vs locally defined

What info can we miss when inspecting?
  - imported vs locally defined
  - variable docstrings
  - default values in a different format

Would it be better to get these from regexp matching/tokenizing?
  - variable docstrings (string literals & comments)
  - imported vs locally defined
"""

# Define True and False, for backwards compatibility:
True = getattr(__builtins__, 'True', 1)
False = getattr(__builtins__, 'False', 0)

######################################################################
## Doc Parser
######################################################################

class DocParser:
    """
    Create VarDoc's from scratch, via parsing.
    """
    def __init__(self, apidoc_graph):
        self._apidoc_graph = apidoc_graph

        self.apidoc_stack = []
        """A stack containing the C{APIDoc}s for the blocks containing
        the parse tree node that we're currently parsing.  The top of
        the stack (C{apidoc_stack[-1]}) ..."""

        inspector = docinspector.DocInspector()
        self.builtins = inspector.inspect(__builtins__)

        self.context = None
        """The dotted name for the parse tree node that we're
        currently parsing.
        @type: L{DottedName}"""

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

    DEBUG=2

    #////////////////////////////////////////////////////////////
    # Entry Point
    #////////////////////////////////////////////////////////////

    # Return a ValueDoc for the given filename.
    def parse(self, filename):
        
        # Find the basedir of the package & the full module name.
        (basedir, module_name) = _find_module_from_filename(filename)

        # Look up the module's existing documentation, or create it if
        # it doesn't have any yet.
        moduledoc = self._apidoc_graph.get(module_name)
        if moduledoc is None:
            moduledoc = ModuleDoc()
            self._apidoc_graph[module_name] = moduledoc
        self.apidoc_stack = [moduledoc]

        # Set the context.
        self.context = module_name
        
        # Read the source code & parse it into a syntax tree.
        try:
            source_code = open(filename).read()
            ast = parser.suite(source_code.replace('\r\n','\n')+'\n')
            ast = ast.tolist()
        except:
            raise
            return # Couldn't parse it!

        # Add comments to the syntax tree.
        add_comments_to_ast(ast, filename)

        #print pp_ast(ast)
        #print '-'*70, '\n', ast_to_string(ast), '-'*70
        
        # Start parsing!
        self.parse_suite(ast)

        # Return the ModuleDoc
        return self.apidoc_stack[0]

    #////////////////////////////////////////////////////////////
    # Suite/Statement Parsing
    #////////////////////////////////////////////////////////////

    STMT_PATTERNS = [
        # Import statement: "import foo"
        ('parse_import', compile_ast_matcher("""
            (stmt COMMENT*
             (simple_stmt
              (small_stmt
               (import_stmt NAME:cmd (*...)*:names))
              NEWLINE))""")),
        # Simple assignment: "x=y" or "x.y=z"
        ('parse_simple_assignment', compile_ast_matcher("""
            (stmt COMMENT*:comments
             (simple_stmt (small_stmt (expr_stmt
              (testlist (test (and_test (not_test (comparison (expr
               (xor_expr (and_expr (shift_expr (arith_expr (term
                (factor (power (atom NAME)
                               (trailer DOT NAME)*))))))))))))):lhs
              EQUAL (*...):rhs)) NEWLINE:nl_comment))""")),
        # Tuple/list assignment: "(a,b)=c" or "[a,b]=c"
        ('parse_tuple_assignment', compile_ast_matcher("""
            (stmt COMMENT*
             (simple_stmt (small_stmt (expr_stmt
              (testlist...):lhs EQUAL (*...):rhs)) NEWLINE))""")),
        # Multi assignment: "a=b=c"
        ('parse_multi_assignment', compile_ast_matcher("""
            (stmt COMMENT*
             (simple_stmt (small_stmt (expr_stmt
              (testlist...):lhs EQUAL
              (*...)*:rhs)) NEWLINE))""")),
        # Function definition: "def f(x): ..."
        ('parse_funcdef', compile_ast_matcher("""
            (stmt COMMENT*:comments
             (compound_stmt (funcdef
                NAME
                NAME:funcname
                (parameters ...):parameters
                COLON
                (suite ...): body)))""")),
        # Class definition: "class A(B): ..."
        ('parse_classdef', compile_ast_matcher("""
            (stmt COMMENT*:comments
             (compound_stmt (classdef
                NAME
                NAME:classname
                LPAR? (testlist...)?:bases RPAR?
                COLON
                (suite ...):body)))""")),
        # Try stmt
        ('parse_try', compile_ast_matcher("""
            (stmt COMMENT*
             (compound_stmt
              (try_stmt NAME COLON (suite ...):trysuite
              (*...)*:rest)))""")),
        # If-then statement
        ('parse_if', compile_ast_matcher("""
            (stmt COMMENT*
             (compound_stmt
              (if_stmt NAME (test ...) COLON (suite ...):ifsuite
               NAME? (test ...)? COLON? (suite ...)?:elifsuite
               NAME? COLON? (suite ...)?:elsesuite)))""")),
        # While statement
        ('parse_while', compile_ast_matcher("""
            (stmt COMMENT*
             (compound_stmt
              (while_stmt NAME (test ...) COLON (suite ...):whilesuite
               NAME? COLON? (suite ...)?:elsesuite)))""")),
        # For stmt
        ('parse_for', compile_ast_matcher("""
            (stmt COMMENT*
             (compound_stmt
              (for_stmt NAME (exprlist...):loopvar NAME 
               (testlist...) COLON (suite ...):forsuite
               NAME? COLON? (suite ...)?:elsesuite)))""")),
        # Semicolon-separated statements: "x=1; y=2"
        ('parse_multistmt', compile_ast_matcher("""
            (stmt COMMENT*:comments
             (simple_stmt
              (small_stmt ...):stmt1
              SEMI
              (*...)*:rest))""")),
        ]
    """A table used by L{parse_suite} to find statements of interest,
    and delegate them to appropriate handlers.  Each table entry has
    the form C{(name, matcher)}.  C{matcher} is an L{ASTMatcher} that
    matches statements of interest, and C{name} is the name of a
    handler method that can parse statements matched by C{matcher}.

    For each statement, the matchers are tried in order.  For the
    first matcher that matches a statement, the corresponding handler
    is called, with parameters corresponding from the matcher's
    variables.  The handler is given one additional parameter,
    C{pseudo_docstring}: if the statement is immediately followed by a
    string constant, then C{pseudo_docstring} is the contents of that
    string constant; otherwise, C{pseudo_docstring} is C{None}.

    If no matchers match a statement, then that statement is ignored.
    """

    INDENT = ''
    def parse_suite(self, ast):
        assert ast[0] in (symbol.file_input, symbol.suite)

        if self.DEBUG>0: print self.INDENT+'Suite: %s' % self.context
        if self.DEBUG>0: self.INDENT += '  '
        stmts = ast[1:]
        for i in range(len(stmts)):
            # Check if it matches any of our statement patterns.
            for (name, matcher) in self.STMT_PATTERNS:
                match, vars = matcher.match(stmts[i])
                if match:
                    if self.DEBUG > 1: print self.INDENT+'Found a', name[6:]
                    # Check for a pseudo-docstring
                    pseudo_docstring = self.get_pseudo_docstring(stmts, i)
                    # Delegate to the appropriate handler.
                    parse_method = getattr(self, name)
                    vardoc = parse_method(pseudo_docstring=pseudo_docstring,
                                          **vars)
                    break
        if self.DEBUG>0: self.INDENT = self.INDENT[:-2]
        
    #////////////////////////////////////////////////////////////
    # Docstring Extraction
    #////////////////////////////////////////////////////////////
     
    STRING_STMT_PATTERN = compile_ast_matcher("""
        (stmt (simple_stmt (small_stmt (expr_stmt (testlist (test
          (and_test (not_test (comparison (expr (xor_expr (and_expr
            (shift_expr (arith_expr (term (factor (power (atom
              STRING:stringval)))))))))))))))) NEWLINE))""")

    def get_docstring(suite):
        """
        @return: The docstring for the given suite.  I.e., if the
        first statement in C{suite} is a string literal, then return
        its contents; otherwise, return C{None}.
        """
        # Find the first statement in the suite.
        if len(suite) == 2 and suite[1][0] == symbol.simple_stmt:
            # suite: simple_stmt
            first_stmt = (symbol.stmt, suite[1])
        else:
            # suite: NEWLINE INDENT stmt+ DEDENT
            first_stmt = suite[3]

        # Match it against STRING_STMT_PATTERN
        match, stmtvars = self.STRING_STMT_PATTERN.match(first_stmt)
        if match: funcdoc.docstring = eval(stmtvars['stringval'])
        else: return None
            
    def get_pseudo_docstring(self, stmts, i):
        """
        @return: The pseudo-docstring for statement C{stmts[i]}, if it
        has one.  I.e., if C{stmts[i+1]} is a string literal, then
        return its contents; otherwise, return C{None}.
        """
        if i+1 < len(stmts):
            match, vars = self.STRING_STMT_PATTERN.match(stmts[i+1])
            if match: return eval(vars['stringval'])
        return None

    #////////////////////////////////////////////////////////////
    # Import Statements
    #////////////////////////////////////////////////////////////
     
    def parse_import(self, cmd, names, pseudo_docstring):
        # The APIDoc for our container.
        parentdoc = self.apidoc_stack[-1]

        # If we're not in a namespace, ignore import statements.
        if not isinstance(parentdoc, NamespaceDoc):
            return

        # The variable names created by imports:
        varnames = [] 

        # from module import *
        if cmd == 'from' and names[-1][0] == token.STAR:
            return # Not much we can do. :-/

        # from __future__ import ...
        elif cmd == 'from' and names[0][1][1] != '__future__':
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
    # Simple Assignment Statements
    #////////////////////////////////////////////////////////////
    # E.g.: x=1 or x.y=1

    def parse_simple_assignment(self, comments, lhs, rhs, nl_comment,
                                pseudo_docstring):
        """
        Parse a simple assignment, i.e., an assignment whose left hand
        side is a single identifier.  C{parse_simple_assignment}
        handles:
          - instance variable assignments
          - aliases (C{x = y})
          - classmethod & staticmethod wrappers
            (C{f = classmethod(f)})
          - simple variable assignments (C{x = 12+y})
        """
        # The APIDoc for our container.
        parentdoc = self.apidoc_stack[-1]

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
        if self.inside_init():
            # To be recorded, instance variables must have the form
            # "self.x", and must have a non-empty docstring.
            if (docstring is None or len(var_dotted_name) != 2 or
                len(parentdoc.args) == 0 or
                var_dotted_name[0] != parentdoc.args[0].name):
                return
            valuedoc = ValueDoc(repr=ast_to_string(rhs))
            is_instvar = 1
            # Set parentdoc to the containing class.
            parentdoc = self.apidoc_stack[-2]

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
                
        # Otherwise, use ast_to_valuedoc to find a valuedoc for rhs.
        if valuedoc is None:
            valuedoc = self.ast_to_valuedoc(rhs)

        # Create the VariableDoc, and add it to its parent.
        vardoc = VariableDoc(varname, valuedoc, is_imported=0,
                             is_alias=is_alias, is_instvar=is_instvar,
                             docstring=docstring)

        if isinstance(parentdoc, NamespaceDoc):
            parentdoc.add_child(vardoc)

    # For classmethod() & staticmethod():
    WRAPPER_PATTERN = compile_ast_matcher("""
        (testlist (test (and_test (not_test (comparison (expr
         (xor_expr (and_expr (shift_expr (arith_expr (term (factor
          (power
           (atom NAME:funcname)
            (trailer LPAR
             (arglist (argument (test ...): arg)) RPAR))))))))))))))""")

    # subclasses can override this:
    def ast_to_valuedoc(self, rhs):
        # If the RHS is a classmethod or staticmethod wrapper, then
        # create a ClassMethodDoc/StaticMethodDoc
        match, vars2 = self.WRAPPER_PATTERN.match(rhs)
        if match:
            arg_dotted_name = self.ast_to_dotted_name(vars2['arg'])
            if arg_dotted_name is not None:
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
    # Tuple Assignment Statements
    #////////////////////////////////////////////////////////////
    # E.g.: (x,y)=1 or [x,y]=1

    # [XX] try aligning lhs and rhs??
    def parse_tuple_assignment(self, lhs, rhs, pseudo_docstring):
        # The APIDoc for our container.
        parentdoc = self.apidoc_stack[-1]
        
        lhs = self.testlist_to_dotted_names(lhs)

        # If we're not in a namespace (eg in __init__), then
        # ignore tuple assignments.
        if not isinstance(parentdoc, NamespaceDoc):
            return

        # Otherwise, just create vars...
        for dotted_name in flatten(lhs):
            if len(dotted_name) == 1:
                varname = dotted_name[0]
                vardoc = VariableDoc(varname, ValueDoc(),
                                     is_imported=False)
                parentdoc.children[varname] = vardoc

    #////////////////////////////////////////////////////////////
    # Multi Assignment Statements
    #////////////////////////////////////////////////////////////
    # E.g.: x=y=1

    def parse_multi_assignment(self, lhs, rhs, pseudo_docstring):
        # expr_stmt: testlist ('=' testlist)*

        # Get a list of all the testlists.
        testlists = [lhs] + [e for e in rhs if e[0]==symbol.testlist]

        # Manually unroll the multi-assignment into a suite.
        suite = [symbol.suite]
        for i in range(len(testlists)-2, -1, -1):
            suite.append((symbol.stmt, (symbol.simple_stmt,
                            (symbol.small_stmt, (symbol.expr_stmt,
                               testlists[i], (token.EQUAL, '='),
                               testlists[i+1])),
                          (token.NEWLINE, ''))))

        # Delegate to parse_suite
        self.parse_suite(suite)
        
    #////////////////////////////////////////////////////////////
    # Control blocks
    #////////////////////////////////////////////////////////////
    # try/except/else, try/finally, if/elif/else, while, for

    def parse_try(self, trysuite, rest, pseudo_docstring):
        if self.PARSE_TRY_BLOCKS:
            self.parse_suite(trysuite)
        if len(rest)>3 and rest[-3] == (token.NAME, 'finally'):
            if self.PARSE_FINALLY_BLOCKS:
                self.parse_suite(rest[-1])
        elif self.PARSE_EXCEPT_BLOCKS:
            for elt in rest:
                if elt[0] == symbol.suite:
                    self.parse_suite(elt)
    
    def parse_if(self, ifsuite, elifsuite, elsesuite, pseudo_docstring):
        if self.PARSE_IF_STMT:
            self.parse_suite(ifsuite)
        if self.PARSE_ELSE_BLOCKS:
            if elifsuite is not None:
                self.parse_suite(elifsuite)
            if elsesuite is not None:
                self.parse_suite(elsesuite)

    def parse_while(self, whilesuite, elsesuite, pseudo_docstring):
        if self.PARSE_WHILE_BLOCKS:
            self.parse_suite(whilesuite)
            if elsesuite is not None:
                self.parse_suite(elsesuite)
        
    def parse_for(self, loopvar, forsuite, elsesuite, pseudo_docstring):
        # The APIDoc for our container.
        parentdoc = self.apidoc_stack[-1]
        
        if self.PARSE_FOR_BLOCKS:
            self.parse_suite(forsuite)
            if elsesuite is not None:
                self.parse_suite(elsesuite)
                
            # Create a VariableDoc for the loop variable.
            loopvar_dotted_name = self.ast_to_dotted_name(loopvar)
            if len(loopvar_dotted_name) == 1:
                loopvar_name = loopvar_dotted_name[0]
                vardoc = VariableDoc(loopvar_name, ValueDoc(),
                                     is_imported=False)
                if isinstance(parentdoc, NamespaceDoc):
                    parentdoc.children[loopvar_name] = vardoc

    #////////////////////////////////////////////////////////////
    # Function definitions
    #////////////////////////////////////////////////////////////

    def parse_funcdef(self, comments, funcname, parameters,
                      body, pseudo_docstring):
        # If we're not in a namespace, then ignore the funcdef.
        parentdoc = self.apidoc_stack[-1]
        if not isinstance(parentdoc, NamespaceDoc): return
        
        # Create the function's RoutineDoc & VariableDoc.
        if isinstance(self.apidoc_stack[-1], ClassDoc):
            funcdoc = InstanceMethodDoc()
        else:
            funcdoc = RoutineDoc()
        vardoc = VariableDoc(funcname, funcdoc, is_imported=False,
                             is_alias=False)

        # Add the VariableDoc to our container.
        parentdoc.add_child(vardoc)
        
        # Add the function's parameters.
        self.parse_parameters(parameters, funcdoc)

        # Add the function's docstring.
        funcdoc.docstring = self.get_docstring(body)
        
        # Parse the suite (if we're in an __init__ method).
        if self.inside_init():
            self.context = DottedName(self.context, funcname)
            self.apidoc_stack.append(funcdoc)
            self.parse_suite(body)
            self.context = DottedName(*self.context[:-1])
            self.apidoc_stack.pop()

    def parse_parameters(self, parameters, funcdoc):
        # parameters: '(' [varargslist] ')'
        if len(parameters) == 3: return
        varargslist = parameters[2]

        # Check for kwarg.
        if len(varargslist) > 3 and varargslist[-2][0] == token.DOUBLESTAR:
            funcdoc.kwarg = varargslist[-1][1]
            del varargslist[-3:]

        # Check for vararg.
        if len(varargslist) > 3 and varargslist[-2][0] == token.STAR:
            funcdoc.vararg = varargslist[-1][1]
            del varargslist[-3:]

        # The rest should all be fpdef's.
        funcdoc.args = []
        for elt in varargslist[1:]:
            if elt[0] == symbol.fpdef:
                funcdoc.args.append(ArgDoc(self.parse_fpdef(elt)))
            elif elt[0] == symbol.test:
                funcdoc.args[-1].default = ast_to_string(elt)

    def parse_fpdef(self, fpdef):
        # fpdef: NAME | '(' fplist ')'
        if fpdef[1][0] == token.NAME:
            return fpdef[1][1]
        else:
            fplist = fpdef[2] # fplist: fpdef (',' fpdef)* [',']
            return tuple([self.parse_fpdef(e) for e in fplist[1:]
                          if e[0] == symbol.fpdef])

    def inside_init(self):
        """
        @return: True if the current context of the C{DocParser} is
        the C{__init__} method of a class.
        """
        return (len(self.apidoc_stack)>=2 and 
                isinstance(self.apidoc_stack[-2], ClassDoc) and
                isinstance(self.apidoc_stack[-1], RoutineDoc) and
                self.context[-1] == '__init__')
    
    #////////////////////////////////////////////////////////////
    # Class definitions
    #////////////////////////////////////////////////////////////

    def parse_classdef(self, comments, classname,
                       bases, body, pseudo_docstring):
        # If we're not in a namespace, then ignore the classdef.
        parentdoc = self.apidoc_stack[-1]
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
        
        # Parse the suite.
        self.context = DottedName(self.context, classname)
        self.apidoc_stack.append(classdoc)
        self.parse_suite(body)
        self.context = DottedName(*self.context[:-1])
        self.apidoc_stack.pop()
     
    #////////////////////////////////////////////////////////////
    # Semicolon-separated statements (x=1; y=2)
    #////////////////////////////////////////////////////////////

    def parse_multistmt(self, vars, pseudo_docstring):
        """
        Parse a set of semicolon-separated statements, such as:
            >>> x=1; y=2; z=3
        C{parse_multistmt} simply wraps the statements in a suite,
        and delegates to C{parse_suite}.
        """
        # Get a list of the small-statements.
        small_stmts = ([vars['stmt1']] +
                       [s for s in vars['rest'] if s[0] == symbol.small_stmt])
                        
        # Wrap them up to look like a suite.
        stmts = [[symbol.stmt, [symbol.simple_stmt, s, [token.NEWLINE, '']]]
                 for s in small_stmts]
        suite = [symbol.suite] + stmts

        # Delegate to parse_suite.
        self.parse_suite(suite)

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
            namespaces = [self.builtins] + self.apidoc_stack
        else:
            namespaces = [self.builtins,
                          self.apidoc_stack[0],
                          self.apidoc_stack[-1]]

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
    # Comment handling
    #////////////////////////////////////////////////////////////

    COMMENT_MARKER = '#: '
    """The prefix used to mark comments that contain
    pseudo-docstrings for variables."""

    def get_comment_docstring(self, comments, nl_comment=''):
        if comments is None: comments = []

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
        if not comments:
            return None

        # Strip off the comment marker
        cm_len = len(self.COMMENT_MARKER)
        comments = [comment[cm_len:] for comment in comments]
        return '\n'.join(comments)

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
                    names.append(self.power_to_dotted_name(vars['power']))

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

        return self.power_to_dotted_name(ast)

    def power_to_dotted_name(self, power_node):
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

print DocParser(DocCollection()).parse('epydoc_test.py').pp(depth=4,
                                     exclude=['subclasses'])
#print DocParser(DocCollection()).parse('epydoc_test.py').pp(depth=-1,
#                 exclude=['subclasses', 'value'])
#print DocParser(DocCollection()).parse('docparser.py')
 
