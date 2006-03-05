# epydoc -- Docstring processing
#
# Copyright (C) 2005 Edward Loper
# Author: Edward Loper <edloper@loper.org>
# URL: <http://epydoc.sf.net>
#
# $Id$

"""
Parse the docstrings of APIDoc objects.
"""


######################################################################
## Imports
######################################################################

import logging, re, sys
from epydoc import markup
from epydoc.apidoc import *
from epydoc.docinspector import inspect_docstring_lineno
from epydoc.util import py_src_filename
from epydoc import log
import __builtin__, exceptions

######################################################################
## Docstring Fields
######################################################################

class DocstringField:
    """
    A generic docstring field.  Docstring field are used to describe
    specific information about an object, such as its author or its
    version.  Generic docstring fields are fields that take no
    arguments, and are displayed as simple sections.

    @ivar tags: The set of tags that can be used to identify this
        field.
    @ivar singular: The label that should be used to identify this
        field in the output, if the field contains one value.
    @ivar plural: The label that should be used to identify this
        field in the output, if the field contains multiple values.
    @ivar short: If true, then multiple values should be combined
        into a single comma-delimited list.  If false, then
        multiple values should be listed separately in a bulleted
        list.
    @ivar multivalue: If true, then multiple values may be given
        for this field; if false, then this field can only take a
        single value, and a warning should be issued if it is
        redefined.
    @ivar takes_arg: If true, then this field expects an argument;
        and a separate field section will be constructed for each
        argument value.  The label (and plural label) should include
        a '%s' to mark where the argument's string rep should be
        added.
    """
    def __init__(self, tags, label, plural=None,
                 short=0, multivalue=1, takes_arg=0):
        if type(tags) in (list, tuple):
            self.tags = tuple(tags)
        elif type(tags) is str:
            self.tags = (tags,)
        else: raise TypeError('Bad tags: %s' % tags)
        self.singular = label
        if plural is None: self.plural = label
        else: self.plural = plural
        self.multivalue = multivalue
        self.short = short
        self.takes_arg = takes_arg

    def __cmp__(self, other):
        if not isinstance(other, DocstringField): return -1
        return cmp(self.tags, other.tags)
    
    def __hash__(self):
        return hash(self.tags)

    def __repr__(self):
        return '<Field: %s>' % self.tags[0]

######################################################################
## Field Errors
######################################################################

class DocstringFieldError(ValueError):
    def __init__(self, tag):
        ValueError.__init__(self, self.MSG % tag)
class UnexpectedArgError(DocstringFieldError):
    MSG = '%s did not expect an argument'
class ExpectedArgError(DocstringFieldError):
    MSG = '%s expected an argument'
class InvalidContextError(DocstringFieldError):
    MSG = 'Invalid context for %s'
class AlreadyDefinedError(DocstringFieldError):
    MSG = '%s already defined'
class UnsupportedError(DocstringFieldError): # [XX]
    MSG = '%s not supported yet'

######################################################################
## Docstring Parser
######################################################################

DEFAULT_DOCFORMAT = 'plaintext'
DEFAULT_DOCFORMAT = 'epytext'

# [XX] rename to SIMPLE_FIELDS?
# Note: order is significant.
STANDARD_FIELDS = [
    # If it's deprecated, put that first.
    DocstringField(['deprecated', 'depreciated'],
             'Deprecated', multivalue=0),

    # Status info
    DocstringField(['version'], 'Version', multivalue=0),
    DocstringField(['date'], 'Date', multivalue=0),
    DocstringField(['status'], 'Status', multivalue=0),
    
    # Bibliographic Info
    DocstringField(['author', 'authors'], 'Author', 'Authors', short=1),
    DocstringField(['contact'], 'Contact', 'Contacts', short=1),
    DocstringField(['organization', 'org'],
                   'Organization', 'Organizations'),
    DocstringField(['copyright', '(c)'], 'Copyright', multivalue=0),
    DocstringField(['license'], 'License', multivalue=0),

    # Various warnings etc.
    DocstringField(['bug'], 'Bug', 'Bugs'),
    DocstringField(['warning', 'warn'], 'Warning', 'Warnings'),
    DocstringField(['attention'], 'Attention'),
    DocstringField(['note'], 'Note', 'Notes'),

    # Formal conditions
    DocstringField(['requires', 'require', 'requirement'], 'Requires'),
    DocstringField(['precondition', 'precond'],
             'Precondition', 'Preconditions'),
    DocstringField(['postcondition', 'postcond'],
             'Postcondition', 'Postconditions'),
    DocstringField(['invariant'], 'Invariant'),

    # When was it introduced (version # or date)
    DocstringField(['since'], 'Since', multivalue=0),

    # Crossreferences
    DocstringField(['see', 'seealso'], 'See Also', short=1),

    # Future Work
    DocstringField(['todo'], 'To Do', takes_arg=True),
    ]

# [xx] keep track of which ones we've already done, in case we're
# asked to process one twice?  e.g., for @include we might have to
# parse the included docstring earlier than we might otherwise..??

def parse_docstring(api_doc, docindex):
    """
    @param docindex: A DocIndex, used to find the containing
        module (to look up the docformat); and to find any
        user docfields defined by containing objects.
    """
    initialize_api_doc(api_doc)

    # If there's no docstring, then there's nothing more to do.
    if (api_doc.docstring in (None, UNKNOWN)):
        return

    # Remove leading indentation from the docstring.
    api_doc.docstring = unindent_docstring(api_doc.docstring)

    # Extract a signature from the docstring, if it has one.  This
    # overrides any signature we got via inspection/parsing.
    if isinstance(api_doc, RoutineDoc):
        parse_function_signature(api_doc)

    # Parse the docstring.  Any errors encountered are stored as
    # `ParseError` objects in the errors list.
    docformat = get_docformat(api_doc, docindex)
    parse_errors = []
    parsed_docstring = markup.parse(api_doc.docstring, docformat,
                                    parse_errors)
        
    # Divide the docstring into a description and a list of
    # fields.
    descr, fields = parsed_docstring.split_fields(parse_errors)
    api_doc.descr = descr

    # Process fields
    field_warnings = []
    for field in fields:
        try:
            process_field(api_doc, docindex, field.tag(),
                               field.arg(), field.body())
        except ValueError, e: field_warnings.append(str(e))

    # Take care of any postprocessing tasks.
    postprocess_api_doc(api_doc, field_warnings)

    # Report any errors that occured
    report_errors(api_doc, docindex, parse_errors, field_warnings)

def initialize_api_doc(api_doc):
    # Initialize the attributes that are set by the docstring
    # contents (including docstring fields).
    if api_doc.descr is UNKNOWN:
        api_doc.descr = None
    if api_doc.summary is UNKNOWN:
        api_doc.summary = None
    if api_doc.metadata is UNKNOWN:
        api_doc.metadata = {}
    if isinstance(api_doc, RoutineDoc):
        if api_doc.arg_descrs is UNKNOWN:
            api_doc.arg_descrs = []
        if api_doc.arg_types is UNKNOWN:
            api_doc.arg_types = {}
        if api_doc.return_descr is UNKNOWN:
            api_doc.return_descr = None
        if api_doc.return_type is UNKNOWN:
            api_doc.return_type = None
        if api_doc.exception_descrs is UNKNOWN:
            api_doc.exception_descrs = []
    if isinstance(api_doc, (VariableDoc, PropertyDoc)):
        if api_doc.type_descr is UNKNOWN:
            api_doc.type_descr = None
    if isinstance(api_doc, NamespaceDoc):
        if api_doc.group_specs is UNKNOWN:
            api_doc.group_specs = []
        if api_doc.sort_spec is UNKNOWN:
            api_doc.sort_spec = []

def postprocess_api_doc(api_doc, field_warnings):
    # Extract a summary
    if api_doc.summary is None and api_doc.descr is not None:
        api_doc.summary = api_doc.descr.summary()

    # Make sure we don't have types/param descrs for unknown
    # vars/params.

def report_errors(api_doc, docindex, parse_errors, field_warnings):
    if not parse_errors and not field_warnings: return

    # Get the name of the item containing the error, and the
    # filename of its containing module.
    name = api_doc.canonical_name
    module = docindex.module_that_defines(api_doc)
    if module is not None and module.filename not in (None, UNKNOWN):
        try: filename = py_src_filename(module.filename)
        except: filename = module.filename
    else:
        filename = '??'

    # [xx] Don't report markup errors for standard builtins.
    if (isinstance(api_doc, ValueDoc) and api_doc != module and
        (api_doc.pyval in __builtin__.__dict__.values() or
         (module is not None and 
          module.pyval in (__builtin__, exceptions)))):
        return

    # Get the start line of the docstring containing the error.
    startline = api_doc.docstring_lineno
    if startline in (None, UNKNOWN):
        startline = inspect_docstring_lineno(api_doc)
        if startline in (None, UNKNOWN):
            startline = None

    # Display a block header.
    header = 'File %s, ' % filename
    if startline is not None:
        header += 'line %d, ' % startline
    header += 'in %s' % name
    log.start_block(header)
    

    # Display all parse errors.  But first, combine any errors
    # with duplicate description messages.
    if startline is None:
        # remove dups, but keep original order:
        dups = {}
        for error in parse_errors:
            message = error.descr()
            if message not in dups:
                log.docstring_warning(message)
                dups[message] = 1
    else:
        # Combine line number fields for dup messages:
        messages = {} # maps message -> list of linenum
        for error in parse_errors:
            error.set_linenum_offset(startline)
            message = error.descr()
            messages.setdefault(message, []).append(error.linenum())
        message_items = messages.items()
        message_items.sort(lambda a,b:cmp(min(a[1]), min(b[1])))
        for message, linenums in message_items:
            if len(linenums) == 1:
                log.docstring_warning("Line %s: %s" % (linenums[0], message))
            else:
                linenums = ', '.join(['%s' % l for l in linenums])
                log.docstring_warning("Lines %s: %s" % (linenums, message))

    # Display all field warnings.
    for warning in field_warnings:
        log.docstring_warning(warning)

    # End the message block.
    log.end_block()

#////////////////////////////////////////////////////////////
# Field Processing
#////////////////////////////////////////////////////////////

def process_field(api_doc, docindex, tag, arg, descr):
    """
    @type warnings: C{list} of C{string}
    """
    # 1. standard special fields
    if tag in _field_dispatch_table:
        handler = _field_dispatch_table[tag]
        handler(api_doc, tag, arg, descr)
        return

    # 2. standard simple fields
    for field in STANDARD_FIELDS:
        if tag in field.tags:
            process_standard_field(api_doc, tag, arg, descr)
            return

    # 3. user-defined fields
    for field in user_docfields(api_doc, docindex):
        if tag in field.tags:
            process_standard_field(api_doc, tag, arg, descr)
            return

    # If we didn't handle the field, then report a warning.
    raise ValueError(UNKNOWN_TAG % tag)

def user_docfields(api_doc, docindex):
    docfields = []
    # Get any docfields from `api_doc` itself
    if api_doc.extra_docstring_fields not in (None, UNKNOWN):
        docfields += api_doc.extra_docstring_fields
    # Get any docfields from `api_doc`'s ancestors
    for i in range(len(api_doc.canonical_name)-1, 0, -1):
        ancestor = docindex.get_valdoc(api_doc.canonical_name.container())
        if ancestor.extra_docstring_fields not in (None, UNKNOWN):
            docfields += ancestor.extra_docstring_fields
    return docfields

def process_standard_field(api_doc, tag, arg, descr):
    for field in STANDARD_FIELDS:
        if tag in field.tags:            
            # Use the cannonical tag name.
            tag = field.tags[0]
            if not field.takes_arg:
                _check(api_doc, tag, arg, expect_arg=False)
            if field.takes_arg and arg is not None:
                values = api_doc.metadata.setdefault((tag,arg), [])
            else:
                values = api_doc.metadata.setdefault(tag, [])
            if not field.multivalue and len(values) > 0:
                raise ValueError(REDEFINED % tag)
            values.append(descr)
            return

# Error messages:
UNEXPECTED_ARG = '%r did not expect an argument'
EXPECTED_ARG = '%r expected an argument'
EXPECTED_SINGLE_ARG = '%r expected a single argument'
BAD_CONTEXT = 'Invalid context for %r'
REDEFINED = 'Redefinition of %s'
UNKNOWN_TAG = 'Unknown field tag %r'

_field_dispatch_table = {}
# [xx] if I move to 2.4 only, this would be better done as a decorator.
def register_field_handler(handler, *field_tags):
    for field_tag in field_tags:
        _field_dispatch_table[field_tag] = handler

def process_summary_field(api_doc, tag, arg, descr):
    _check(api_doc, tag, arg, expect_arg=False)
    if api_doc.summary is not None:
        raise ValueError(REDEFINED % tag)
    api_doc.summary = descr

def process_include_field(api_doc, tag, arg, descr):
    # [xx] need docindex!!
    _check(api_doc, tag, arg, expect_arg=False)
    # options:
    #   a. just append the descr to our own
    #   b. append descr and update metadata
    #   c. append descr and process all fields.
    # in any case, mark any errors we may find as coming from an
    # imported docstring.
    
    # how does this interact with documentation inheritance??
    raise ValueError('%s not implemented yet' % tag)

def process_undocumented_field(api_doc, tag, arg, descr):
    _check(api_doc, tag, arg, context=NamespaceDoc, expect_arg=False)
    for ident in _descr_to_identifiers(descr):
        var_name_re = re.compile('^%s$' % ident.replace('*', '(.*)'))
        for var_name, var_doc in api_doc.variables.items():
            if var_name_re.match(var_name):
                # Remove the variable from `variables`.
                api_doc.variables.pop(var_name, None)

def process_group_field(api_doc, tag, arg, descr):
    _check(api_doc, tag, arg, context=NamespaceDoc, expect_arg=True)
    api_doc.group_specs.append( (arg, _descr_to_identifiers(descr)) )

def process_deffield_field(api_doc, tag, arg, descr):
    _check(api_doc, tag, arg, expect_arg=True)
    if api_doc.extra_docstring_fields is UNKNOWN:
        api_doc.extra_docstring_fields = []
    try:
        docstring_field = _descr_to_docstring_field(arg, descr)
        api_doc.extra_docstring_fields.append(docstring_field)
    except ValueError, e:
        raise ValueError('Bad %s: %s' % (tag, e))

def process_raise_field(api_doc, tag, arg, descr):
    _check(api_doc, tag, arg, context=RoutineDoc, expect_arg='single')
    try: name = DottedName(arg)
    except ValueError: name = arg
    api_doc.exception_descrs.append( (name, descr) )

def process_todo_field(api_doc, tag, arg, descr):
    raise ValueError('not implemented yet?')

def process_sort_field(api_doc, tag, arg, descr):
    _check(api_doc, tag, arg, context=NamespaceDoc, expect_arg=False)
    api_doc.sort_spec += _descr_to_identifiers(descr)

# [xx] should I notice when they give a type for an unknown var?
def process_type_field(api_doc, tag, arg, descr):
    # In namespace, "@type var: ..." describes the type of a var.
    if isinstance(api_doc, NamespaceDoc):
        _check(api_doc, tag, arg, expect_arg='single')
        set_var_type(api_doc, arg, descr)

    # For variables, "@type: ..." describes the variable.
    elif isinstance(api_doc, (VariableDoc, PropertyDoc)):
        _check(api_doc, tag, arg, expect_arg=False)
        if api_doc.type_descr is not None:
            raise ValueError(REDEFINED % tag)
        api_doc.type_descr = descr

    # For routines, "@type param: ..." describes a parameter.
    elif isinstance(api_doc, RoutineDoc):
        _check(api_doc, tag, arg, expect_arg='single')
        if arg in api_doc.arg_types:
            raise ValueError(REDEFINED % ('type for '+arg))
        api_doc.arg_types[arg] = descr
    else:
        raise ValueError(BAD_CONTEXT % arg)

def process_var_field(api_doc, tag, arg, descr):
    _check(api_doc, tag, arg, context=ModuleDoc, expect_arg=True)
    for ident in re.split('[:;, ] *', arg):
        set_var_descr(api_doc, ident, descr)
        
def process_cvar_field(api_doc, tag, arg, descr):
    _check(api_doc, tag, arg, context=ClassDoc, expect_arg=True)
    for ident in re.split('[:;, ] *', arg):
        set_var_descr(api_doc, ident, descr)
        api_doc.variables[ident].is_instvar = False
        
def process_ivar_field(api_doc, tag, arg, descr):
    _check(api_doc, tag, arg, context=ClassDoc, expect_arg=True)
    for ident in re.split('[:;, ] *', arg):
        set_var_descr(api_doc, ident, descr)
        api_doc.variables[ident].is_instvar = True

def process_return_field(api_doc, tag, arg, descr):
    _check(api_doc, tag, arg, context=RoutineDoc, expect_arg=False)
    if api_doc.return_descr is not None:
        raise ValueError(REDEFINED % 'return value description')
    api_doc.return_descr = descr

def process_rtype_field(api_doc, tag, arg, descr):
    _check(api_doc, tag, arg, context=RoutineDoc, expect_arg=False)
    if api_doc.return_type is not None:
        raise ValueError(REDEFINED % 'return value description')
    api_doc.return_type = descr

def process_arg_field(api_doc, tag, arg, descr):
    _check(api_doc, tag, arg, context=RoutineDoc, expect_arg=True)
    idents = re.split('[:;, ] *', arg)
    api_doc.arg_descrs.append( (idents, descr) )

def process_kwarg_field(api_doc, tag, arg, descr):
    # [xx] these should -not- be checked if they exist..
    # and listed separately or not??
    _check(api_doc, tag, arg, context=RoutineDoc, expect_arg=True)
    idents = re.split('[:;, ] *', arg)
    api_doc.arg_descrs.append( (idents, descr) )

register_field_handler(process_group_field, 'group')
register_field_handler(process_deffield_field, 'deffield', 'newfield')
register_field_handler(process_sort_field, 'sort')
register_field_handler(process_summary_field, 'summary')
register_field_handler(process_undocumented_field, 'undocumented')
register_field_handler(process_include_field, 'include')
register_field_handler(process_var_field, 'var', 'variable')
register_field_handler(process_type_field, 'type')
register_field_handler(process_cvar_field, 'cvar', 'cvariable')
register_field_handler(process_ivar_field, 'ivar', 'ivariable')
register_field_handler(process_return_field, 'return', 'returns')
register_field_handler(process_rtype_field, 'rtype', 'returntype')
register_field_handler(process_arg_field, 'arg', 'argument',
                                          'parameter', 'param')
register_field_handler(process_kwarg_field, 'kwarg', 'keyword', 'kwparam')
register_field_handler(process_raise_field, 'raise', 'raises',
                                            'except', 'exception')

#////////////////////////////////////////////////////////////
# Helper functions (2)
#////////////////////////////////////////////////////////////

def set_var_descr(api_doc, ident, descr):
    if ident not in api_doc.variables:
        api_doc.variables[ident] = VariableDoc(container=api_doc,
                                               name=ident)
                                      
    var_doc = api_doc.variables[ident]
    if var_doc.descr not in (None, UNKNOWN):
        raise ValueError(REDEFINED % ('description for '+ident))
    var_doc.descr = descr
    if var_doc.summary in (None, UNKNOWN):
        var_doc.summary = var_doc.descr.summary()

def set_var_type(api_doc, ident, descr):
    if ident not in api_doc.variables:
        api_doc.variables[ident] = VariableDoc(container=api_doc,
                                               name=ident)
    var_doc = api_doc.variables[ident]
    if var_doc.type_descr not in (None, UNKNOWN):
        raise ValueError(REDEFINED % ('type for '+ident))
    var_doc.type_descr = descr
        
def _check(api_doc, tag, arg, context=None, expect_arg=None):
    if context is not None:
        if not isinstance(api_doc, context):
            raise ValueError(BAD_CONTEXT % tag)
    if expect_arg is not None:
        if expect_arg == True:
            if arg is None:
                raise ValueError(EXPECTED_ARG % tag)
        elif expect_arg == False:
            if arg is not None:
                raise ValueError(UNEXPECTED_ARG % tag)
        elif expect_arg == 'single':
            if (arg is None or ' ' in arg):
                raise ValueError(EXPECTED_SINGLE_ARG % tag)
        else:
            assert 0, 'bad value for expect_arg'

#////////////////////////////////////////////////////////////
# Helper functions (1)
#////////////////////////////////////////////////////////////

def get_docformat(api_doc, docindex):
    """
    Return the name of the markup language that should be used to
    parse the API documentation for the given object.
    """
    # Find the module that defines api_doc.
    module = docindex.module_that_defines(api_doc)
    # Look up its docformat.
    if module is not None and module.docformat not in (None, UNKNOWN):
        docformat = module.docformat
    else:
        docformat = DEFAULT_DOCFORMAT
    # Convert to lower case & strip region codes.
    try: return docformat.lower().split()[0]
    except: return DEFAULT_DOCFORMAT

def unindent_docstring(docstring):
    # [xx] copied from inspect.
    
    if docstring == '': return ''
    lines = docstring.expandtabs().split('\n')

    # Find minimum indentation of any non-blank lines after first line.
    margin = sys.maxint
    for line in lines[1:]:
        content = len(line.strip())
        if content:
            indent = len(line) - content
            margin = min(margin, indent)
    # Remove indentation.
    if lines:
        lines[0] = lines[0].lstrip()
    if margin < sys.maxint:
        for i in range(1, len(lines)): lines[i] = lines[i][margin:]
    # Remove any trailing (but not leading!) blank lines.
    while lines and not lines[-1]:
        lines.pop()
    #while lines and not lines[0]:
    #    lines.pop(0)
    return '\n'.join(lines)
                           
#////////////////////////////////////////////////////////////
# Function signature extraction.
#////////////////////////////////////////////////////////////

# [XX] todo: add optional type modifiers?
_SIGNATURE_RE = re.compile(
    # Class name (for builtin methods)
    r'^\s*((?P<self>\w+)\.)?' +
    # The function name (must match exactly) [XX] not anymore!
    r'(?P<func>\w+)' +
    # The parameters
    r'\((?P<params>(\s*\[?\s*\*{0,2}[\w\-\.]+(=.+?)?'+
    r'(\s*\[?\s*,\s*\]?\s*\*{0,2}[\w\-\.]+(=.+?)?)*\]*)?)\s*\)' +
    # The return value (optional)
    r'(\s*(->)\s*(?P<return>\S.*?))?'+
    # The end marker
    r'\s*(\n|\s+(--|<=+>)\s+|$|\.\s+|\.\n)')
"""A regular expression that is used to extract signatures from
docstrings."""
    
def parse_function_signature(func_doc):
    """
    Construct the signature for a builtin function or method from
    its docstring.  If the docstring uses the standard convention
    of including a signature in the first line of the docstring
    (and formats that signature according to standard
    conventions), then it will be used to extract a signature.
    Otherwise, the signature will be set to a single varargs
    variable named C{"..."}.

    @rtype: C{None}
    """
    # If there's no docstring, then don't do anything.
    if not func_doc.docstring: return False

    m = _SIGNATURE_RE.match(func_doc.docstring)
    if m is None: return False

    if not (m.group('func') == func_doc.canonical_name[-1] or
            '_'+m.group('func') == func_doc.canonical_name[-1]):
        log.warning("Not extracting function signature from %s's "
                    "docstring, since the name doesn't match." %
                    func_doc.canonical_name)
        return False
    
    params = m.group('params')
    rtype = m.group('return')
    selfparam = m.group('self')
    
    # Extract the parameters from the signature.
    func_doc.posargs = []
    func_doc.vararg = None
    func_doc.kwarg = None
    if func_doc.posarg_defaults is UNKNOWN:
        func_doc.posarg_defaults = []
    if params:
        # Figure out which parameters are optional.
        while '[' in params or ']' in params:
            m2 = re.match(r'(.*)\[([^\[\]]+)\](.*)', params)
            if not m2: return False
            (start, mid, end) = m2.groups()
            mid = re.sub(r'((,|^)\s*[\w\-\.]+)', r'\1=...', mid)
            params = start+mid+end

        params = re.sub(r'=...=' , r'=', params)
        for name in params.split(','):
            if '=' in name:
                (name, default_repr) = name.split('=',1)
                default = ValueDoc(repr=default_repr)
            else:
                default = None
            name = name.strip()
            if name == '...':
                func_doc.vararg = '...'
            elif name.startswith('**'):
                func_doc.kwarg = name[2:]
            elif name.startswith('*'):
                func_doc.vararg = name[1:]
            else:
                func_doc.posargs.append(name)
                if len(func_doc.posarg_defaults) < len(func_doc.posargs):
                    func_doc.posarg_defaults.append(default)
                elif default is not None:
                    argnum = len(func_doc.posargs)-1
                    func_doc.posarg_defaults[argnum] = default

    # Extract the return type/value from the signature
    if rtype:
        func_doc.return_descr = markup.parse(rtype, 'plaintext')

    # Add the self parameter, if it was specified.
    if selfparam:
        func_doc.posargs.insert(0, selfparam)
        func_doc.posarg_defaults.insert(0, None)

    # Remove the signature from the docstring.
    func_doc.docstring = func_doc.docstring[m.end():]
        
    # We found a signature.
    return True


_IDENTIFIER_LIST_REGEXP = re.compile(r'^[\w.\*]+([\s,:;]\s*[\w.\*]+)*$')
def _descr_to_identifiers(descr):
    """
    Given a C{ParsedDocstring} that contains a list of identifiers,
    return a list of those identifiers.  This is used by fields such
    as C{@group} and C{@sort}, which expect lists of identifiers as
    their values.  To extract the identifiers, the docstring is first
    converted to plaintext, and then split.  The plaintext content of
    the docstring must be a a list of identifiers, separated by
    spaces, commas, colons, or semicolons.
    
    @rtype: C{list} of C{string}
    @return: A list of the identifier names contained in C{descr}.
    @type descr: L{markup.ParsedDocstring}
    @param descr: A C{ParsedDocstring} containing a list of
        identifiers.
    @raise ValueError: If C{descr} does not contain a valid list of
        identifiers.
    """
    idents = descr.to_plaintext(None).strip()
    idents = re.sub(r'\s+', ' ', idents)
    if not _IDENTIFIER_LIST_REGEXP.match(idents):
        raise ValueError, 'Bad Identifier list: %r' % idents
    rval = re.split('[:;, ] *', idents)
    return rval
    
def _descr_to_docstring_field(arg, descr):
    tags = [s.lower() for s in re.split('[:;, ] *', arg)]
    descr = descr.to_plaintext(None).strip()
    args = re.split('[:;,] *', descr)
    if len(args) == 0 or len(args) > 3:
        raise ValueError, 'Wrong number of arguments'
    singular = args[0]
    if len(args) >= 2: plural = args[1]
    else: plural = None
    short = 0
    if len(args) >= 3:
        if args[2] == 'short': short = 1
        else: raise ValueError('Bad arg 2 (expected "short")')
    return DocstringField(tags, singular, plural, short)



