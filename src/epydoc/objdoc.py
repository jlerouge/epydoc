#
# objdoc: epydoc object documentation classes
# Edward Loper
#
# Created [01/30/01 05:18 PM]
# $Id$
#

# To do:
#    - overriding/doc inheritance
#    - inheritance source pseudo-ClassDocs?
#    - clean up
#    - fix package link (when there's 1 package)

"""
Support for C{ObjDoc}s, which encode the information about a Python
object that is necessary to create its documentation.  C{ObjDoc}s are
created and managed by the C{DocMap} class, which acts like a
dictionary from L{UID}s to C{ObjDoc}s.

Textual documentation entries (e.g., module descriptions, method
descriptions, variable types, see-also entries) are encoded as DOM
L{Documents<xml.dom.minidom.Document>} and
L{Elements<xml.dom.minidom.Document>}, using the DTD described in the
L{epytext} module.

Each Python object is identified by a globally unique identifier,
implemented with the L{UID} class.  These identifiers are also used by
the C{Link} class to implement crossreferencing between C{ObjDoc}s.

@var DEFAULT_DOCFORMAT: The default value for C{__docformat__}, if it
is not specified by modules.  C{__docformat__} is a module variable
that specifies the markup language for the docstrings in a module.
Its value is a string, consisting the name of a markup language,
optionally followed by a language code (such as C{en} for English).
Some typical values for C{__docformat__} are:

    >>> __docformat__ = 'plaintext'
    >>> __docformat__ = 'epytext'
    >>> __docformat__ = 'epytext en'
"""
__docformat__ = 'epytext en'

##################################################
## Imports
##################################################

import inspect, UserDict, epytext, string, new, re, sys, types
import xml.dom.minidom

from epydoc.uid import UID, Link, make_uid

# Python 2.2 types
try:
    _WrapperDescriptorType = type(list.__add__)
    _MethodDescriptorType = type(list.append)
    _PropertyType = property
except:
    _WrapperDescriptorType = None
    _MethodDescriptorType = None
    _PropertyType = None

# This is used when we get a bad field tag, to distinguish between
# unknown field tags, and field tags that were just used in a bad
# context. 
_KNOWN_FIELD_TAGS = ('var', 'variable', 'ivar', 'ivariable',
                     'cvar', 'cvariable', 'type', 'group',
                     'return', 'returns', 'rtype', 'returntype',
                     'param', 'parameter', 'arg', 'argument',
                     'raise', 'raises', 'exception', 'except')

##################################################
## Helper Functions
##################################################
def _flatten(tree):
    """
    Recursively explore C{tree}, and return an in-order list of all
    leaves.
    
    @return: An in-order list of the leaves of C{tree}.
    @param tree: The tree whose leaves should be returned.  The tree
        structure of C{tree} is represented by tuples and lists.  In
        particular, every tuple or list contained in C{tree} is
        considered a subtree; and any other element is considered a
        leaf. 
    @type tree: C{list} or C{tuple}
    """
    lst = []
    for elt in tree:
        if type(elt) in (type(()), type([])):
            lst.extend(_flatten(elt))
        else:
            lst.append(elt)
    return lst

def _getdoc(obj):
    """
    Get the documentation string for an object.  This function is
    similar to L{inspect.getdoc}.  In particular, it finds the minimum
    indentation fromthe second line onwards, and removes that
    indentation from each line.  But it also checks to make sure that
    the docstring is actually a string (since some programs put other
    data in the docstrings).

    @param obj: The object whose documentation string should be returned.
    @type obj: any
    """
    if ((not hasattr(obj, '__doc__')) or
        type(obj.__doc__) is not types.StringType):
        return None
    else:
        return inspect.getdoc(obj)

def _find_docstring(uid):
    """
    @return: The file name and line number of the docstring for the
        given object; or C{None} if the docstring cannot be found.
        Line numbers are indexed from zero (i.e., the first line's
        line number is 0).
    @rtype: C{(string, int)} or C{(None, None)}
    """
    # This function is based on inspect.findsource; but I don't want
    # to use that function directly, because it's not as smart about
    # finding modules for objects (esp. functions).

    # Get the filename of the source file.
    object = uid.value()
    try:
        if uid.is_module(): muid = uid
        else: muid = uid.module()
        filename = muid.value().__file__
    except: return (None, None)
    if filename[-4:-1].lower() == '.py':
        filename = filename[:-1]

    # Read the source file's contents.
    try: lines = open(filename).readlines()
    except: return (None, None)

    # Figure out the starting line number of the object
    linenum = 0
    if inspect.isclass(object):
        pat = re.compile(r'^\s*class\s*%s\b' % object.__name__)
        for linenum in range(len(lines)):
            if pat.match(lines[linenum]): break
        else: return (None, None)
        linenum += 1
    if inspect.ismethod(object): object = object.im_func
    if inspect.isfunction(object): object = object.func_code
    if inspect.istraceback(object): object = object.tb_frame
    if inspect.isframe(object): object = object.f_code
    if inspect.iscode(object):
        if not hasattr(object, 'co_firstlineno'): return (None, None)
        linenum = object.co_firstlineno

    # Find the line number of the docstring.  Assume that it's the
    # first non-blank line after the start of the object, since the
    # docstring has to come first.
    for linenum in range(linenum, len(lines)):
        if lines[linenum].split('#', 1)[0].strip():
            return (filename, linenum)

    # We couldn't find a docstring line number.
    return (None, None)

_IDENTIFIER_LIST_REGEXP = re.compile(r'^([\w.]+[\s,:;]?\s*)*[\w.]+\s*$')
def _descr_to_identifiers(descr):
    """
    Given the XML DOM tree for a fragment of epytext that contains a
    list of identifiers, return a list of those identifier names.
    This is used by fields such as C{@group} and C{@sort}, which expect
    lists of identifiers as their values.

    @rtype: C{list} of C{string}
    @return: A list of the identifier names contained in C{descr}.
    @param descr: The DOM tree for a fragment of epytext containing
        a list of identifiers.  C{descr} must contain a single para
        element, whose contents consist of a list of identifiers,
        separated by spaces, commas, colons, or semicolons.  C{descr}
        should not contain any inline markup.
    @raise ValueError: If C{descr} does not contain a valid value (a
        single paragraph with no in-line markup)
    """
    if len(descr.childNodes) != 1:
        raise ValueError, 'Expected a single paragraph'
    para = descr.childNodes[0]
    if para.tagName != 'para':
        raise ValueError, 'Expected a para; got a %s' % para.tagName
    if len(para.childNodes) != 1:
        raise ValueError, 'Colorization is not allowed'
    idents = para.childNodes[0].data
    if not _IDENTIFIER_LIST_REGEXP.match(idents):
        raise ValueError, 'Bad Identifier list: %r' % idents
    return re.split('[ :;,]+', idents)

def _descr_to_docfield(arg, descr):
    tags = [s.lower() for s in re.split('[ :;,]+', arg)]
    
    if len(descr.childNodes) != 1:
        raise ValueError, 'Expected a single paragraph'
    para = descr.childNodes[0]
    if para.tagName != 'para':
        raise ValueError, 'Expected a para; got a %s' % para.tagName
    if len(para.childNodes) != 1:
        raise ValueError, 'Colorization is not allowed'

    args = re.split(' *[:;,]+ *', para.childNodes[0].data)
    if len(args) == 0 or len(args) > 3:
        raise ValueError, 'Wrong number of arguments'
    singular = args[0]
    if len(args) >= 2: plural = args[1]
    else: plural = None
    short = 0
    if len(args) >= 3:
        if args[2] == 'short': short = 1
        else: raise ValueError('Bad arg 2 (expected "short")')
    return DocField(tags, singular, plural, 1, short)

def _dfs_bases(cls):
    bases = [cls]
    for base in cls.__bases__: bases += _dfs_bases(base)
    return bases

def _find_base_order(cls):
    # Use new or old inheritance rules?
    new_inheritance = (sys.hexversion >= 0x02020000)

    # Depth-first search,
    base_order = _dfs_bases(cls)

    # Eliminate duplicates.  For old inheritance order, eliminate from
    # front to back; for new inheritance order, eliminate back to front.
    if new_inheritance: base_order.reverse()
    i = 0
    seen_bases = {}
    while i < len(base_order):
        if seen_bases.has_key(base_order[i]):
            del base_order[i]
        else:
            seen_bases[base_order[i]] = 1
            i += 1
    if new_inheritance: base_order.reverse()

    return base_order

##################################################
## __docformat__
##################################################

DEFAULT_DOCFORMAT = 'epytext'
def set_default_docformat(new_format):
    """
    Change the default value for C{__docformat__} to the given value.
    The current default value for C{__docformat__} is recorded in
    C{DEFAULT_DOCFORMAT}.

    @param new_format: The new default value for C{__docformat__}
    @type new_format: C{string}
    @see: L{DEFAULT_DOCFORMAT}
    @rtype: C{None}
    """
    global DEFAULT_DOCFORMAT
    DEFAULT_DOCFORMAT = new_format

##################################################
## ObjDoc
##################################################

#////////////////////////////////////////////////////////
#// Var, Param, and Raise
#////////////////////////////////////////////////////////

class Var:
    """
    The documentation for a variable.  This documentation consists of
    the following fields:
    
        - X{uid}: The variable's UID
        - X{descr}: A description of the variable
        - X{type}: A description of the variable's type
        - X{has_value}: A flag indicating whether a variable has a
          value.  If this flag is true, then the value can be accessed
          via the C{Var}'s UID.
        
    C{Var}s are used by L{ModuleDoc} to document variables; and by
    L{ClassDoc} to document instance and class variables.
    """
    def __init__(self, uid, descr=None, type=None, has_value=1,
                 autogenerated=0):
        """
        Construct the documentation for a variable.

        @param uid: A unique identifier for the variable.
        @type uid: C{string}
        @param descr: The DOM representation of an epytext description
            of the variable (as produced by C{epytext.parse}).
        @type descr: L{xml.dom.minidom.Element}
        @param type: The DOM representation of an epytext description
            of the variable's type (as produced by C{epytext.parse}).
        @type type: L{xml.dom.minidom.Element}
        @param has_value: Whether the documented variable has a value.
        """
        self._uid = uid
        self._descr = descr
        self._type = type
        self._has_value = has_value
        self._autogen = autogenerated
        
    def uid(self):
        """
        @return: The UID of the variable documented by this C{Var}.
        @rtype: L{UID}
        """
        return self._uid

    def name(self):
        """
        @return: The short name of this variable.
        @rtype: C{string}
        """
        return self._uid.shortname()
    
    def type(self):
        """
        @return: The DOM representation of an epytext description of
            this variable's type.
        @rtype: L{xml.dom.minidom.Element}
        """
        return self._type
    
    def descr(self):
        """
        @return: The DOM representation of an epytext description of
            this variable.
        @rtype: L{xml.dom.minidom.Element}
        """
        return self._descr

    def has_value(self):
        """
        @return: True if the variable documented by this C{Var} has a
            value.  If this function returns true, then the value can
            be accessed via the C{Var}'s UID.
        @rtype: C{boolean}
        """
        return self._has_value

    def autogenerated(self):
        """
        @return: True if this variable documentation was generated
            automatically from a module variable (i.e., not from a
            C{@var} field or a C{@type} field).
        @rtype: C{boolean}
        """
        return self._autogen

    def __repr__(self):
        return '<Variable %s>' % self._uid

class Param:
    """
    The documentation for a function parameter.  This documentation
    consists of the following fields:

        - X{name}: The name of the parameter
        - X{descr}: A description of the parameter
        - X{type}: A description of the parameter's type
        - X{default}: The parameter's default value

    C{Param}s are used by L{FuncDoc} to document parameters.
    """
    def __init__(self, name, descr=None, type=None, default=None):
        """
        Construct the documentation for a parameter.

        @param name: The name of the parameter.
        @type name: C{string}
        @param descr: The DOM representation of an epytext description
            of the parameter (as produced by C{epytext.parse}).
        @type descr: L{xml.dom.minidom.Element}
        @param type: The DOM representation of an epytext description
            of the parameter's type (as produced by C{epytext.parse}).
        @type type: L{xml.dom.minidom.Element}
        @param default: A string representation of the parameter's
            default value; or C{None} if it has no default value.
        @type default: C{string} or C{None}
        """
        self._name = name
        self._descr = descr
        self._type = type
        self._default = default
        
    def name(self):
        """
        @return: The name of this parameter.
        @rtype: C{string}
        """
        return self._name
    
    def type(self):
        """
        @return: The DOM representation of an epytext description of
            this parameter's type.
        @rtype: L{xml.dom.minidom.Element}
        """
        return self._type
    
    def descr(self):
        """
        @return: The DOM representation of an epytext description of
            this parameter.
        @rtype: L{xml.dom.minidom.Element}
        """
        return self._descr
    
    def default(self):
        """
        @return:  A string representation of the parameter's
            default value; or C{None} if it has no default value.
        @rtype: C{string} or C{None}
        """
        return self._default

    def set_type(self, type):
        """
        Set this parameter's type.
        
        @param type: The DOM representation of an epytext description
            of the parameter's type (as produced by C{epytext.parse}).
        @type type: L{xml.dom.minidom.Element}
        @rtype: C{None}
        """
        self._type = type
        
    def set_descr(self, descr):
        """
        Set this parameter's description.
        
        @type descr: L{xml.dom.minidom.Element}
        @param descr: The DOM representation of an epytext description
            of the parameter's type (as produced by C{epytext.parse}).
        @rtype: C{None}
        """
        self._descr = descr
        
    def set_default(self, default):
        """
        Set this parameter's default value.
        
        @param default: A string representation of the parameter's
            default value; or C{None} if it has no default value.
        @type default: C{string} or C{None}
        @rtype: C{None}
        """
        self._default = default
        
    def __repr__(self):
        return '<Parameter '+self._name+'>'

class Raise:
    """
    The documentation for the raising of an exception.  This consists
    of the exception's name and its description.  Exceptions are used
    by L{FuncDoc}.
    """
    def __init__(self, name, descr):
        """
        Construct the documentation for the raising of an exception.

        @param name: The name of the exception.
        @type name: C{string}
        @param descr: The DOM representation of an epytext description
            of when the exception is raised (as produced by
            C{epytext.parse}). 
        @type descr: L{xml.dom.minidom.Element}
        """
        self._name = name
        self._descr = descr
        
    def name(self):
        """
        @return: The name of the exception.
        @rtype: C{string}
        """
        return self._name
    
    def descr(self):
        """
        @return: The DOM representation of an epytext description
            of when the exception is raised (as produced by
            C{epytext.parse}).
        @rtype: L{xml.dom.minidom.Element}
        """
        return self._descr
        
    def __repr__(self):
        return '<Raise '+self._name+'>'

#////////////////////////////////////////////////////////
#// Generalized Fields
#////////////////////////////////////////////////////////

class DocField:
    """
    A documentation field for the object.
    """
    def __init__(self, tags, singular, plural=None,
                 multivalue=1, short=0):
        if type(tags) in (type(()), type([])):
            self.tags = tuple(tags)
        elif type(tags) == type(''):
            self.tags = (tags,)
        else: raise TypeError('Bad tags: %s' % tags)
        self.singular = singular
        self.plural = plural
        self.multivalue = multivalue
        self.short = short

    def __cmp__(self, other):
        if not isinstance(other, DocField): return -1
        return cmp(self.tags, other.tags)
    
    def __hash__(self):
        return hash(self.tags)

    def __repr__(self):
        return '<Field: %s>' % self.tags[0]

#////////////////////////////////////////////////////////
#// Base ObjDoc Class
#////////////////////////////////////////////////////////
class ObjDoc:
    """
    A base class for encoding the information about a Python object
    that is necessary to create its documentation.  This base class
    defines the following documentation fields:

        - X{uid}: The object's unique identifier
        - X{descr}: A description of the object
        - X{fields}: A dictionary containing standard fields,
          such as authors, version, and notes.  The complete
          list of fields is defined by the variable
          L{ObjDoc.FIELDS}.
        - X{sortorder}: The object's sort order, as defined by the
          C{@sort} field.

    @group Accessors: documented, uid, descr, fields, field_values,
        sortorder
    @group Error Handling: _print_errors, _parse_warnings,
        _parse_errors, _field_warnings
    @group Docstring Parsing: __parse_docstring, _process_field,
        _descr, _fields, FIELDS

    @ivar _uid: The object's unique identifier
    @type _uid: L{UID}
    @ivar _descr: The object's description, encoded as epytext.
    @type _descr: L{xml.dom.minidom.Document}

    @ivar _fields: Documentation fields that were extracted from
        the object's docstring.  The list of fields that are
        accepted by epydoc is defined by L{ObjDoc.FIELDS}.
    @type _fields: C{dictionary} from L{DocField} to C{list} of
                   L{xml.dom.minidom.Element}
    @cvar FIELDS: The set of standard docstring fields that
        epydoc accepts.  The order of fields is significant:
        when the fields are rendered, they will be listed in
        the order that they are given in here.  Note that this
        list does X{not} include special fields, such as
        \"group\"; it just includes \"standard\" fields, which
        contain a single textual description or a list of
        textual descriptions.
    @type FIELDS: C{List} of L{DocField}
                   
    @ivar _parse_warnings: Warnings generated when parsing the
        object's docstring.
    @ivar _parse_errors: Errors generated when parsing the object's
        docstring.
    @ivar _field_warnings: Warnings generated when processing the
        object's docstring's fields.
    """
    FIELDS = [
        # If it's depreciated, put that first.
        DocField(['depreciated'], 'Depreciated', multivalue=0),

        # Then version & author
        DocField(['version'], 'Version', multivalue=0),
        DocField(['author', 'authors'], 'Author', 'Authors', short=1),

        # Various warnings etc.
        DocField(['bug'], 'Bug', 'Bugs'),
        DocField(['warn', 'warning'], 'Warning', 'Warnings'),
        DocField(['attention'], 'Attention'),
        DocField(['note'], 'Note', 'Notes'),

        # Formal conditions
        DocField(['requires', 'require', 'requirement'], 'Requires'),
        DocField(['precondition', 'precond'],
                 'Precondition', 'Preconditions'),
        DocField(['postcondition', 'postcond'],
                 'Postcondition', 'Postconditions'),
        DocField(['invariant'], 'Invariant'),

        # When was it introduced (version # or date)
        DocField(['since'], 'Since', multivalue=0),

        # Crossreferences
        DocField(['see', 'seealso'], 'See Also', short=1),

        # Future Work
        DocField(['todo'], 'To Do'),
        ]
    def __init__(self, uid, verbosity=0):
        """
        Create the documentation for the given object.
        
        @param uid: The UID of the object to document.
        @type uid: L{UID}
        @param verbosity: The verbosity of output produced when
            creating documentation for the object.  More positive
            numbers produce more verbose output; negative numbers
            supress warnings and errors.
        @type verbosity: C{int}
        """
        obj = uid.value()
        self._uid = uid

        # Default: no description
        self._descr = None

        # Default: no sort order
        self._sortorder = None

        # Initialize errors/warnings, and remember verbosity.
        self.__verbosity = verbosity
        self._parse_errors = []
        self._parse_warnings = []
        self._field_warnings = []

        # Look up our module.  We use this to look up both
        # __docformat__ and __extra_epydoc_fields__.
        if self._uid.is_module(): module = self._uid
        else: module = self._uid.module()

        # Give a warning if there's an __epydoc_sort__ attribute.
        if hasattr(obj, '__epydoc_sort__'):
            estr = 'Warning: __epydoc_sort__ is depreciated'
            self._field_warnings.append(estr)
        
        # Initialize fields.  Add any extra fields.
        self._fields = self.FIELDS[:]
        if module is not None:
            try:
                for field in module.value().__extra_epydoc_fields__:
                    if type(field) == type(''):
                        self._fields.append(DocField(field.lower(), field))
                    else:
                        self._fields.append(DocField(*field))
            except: self._fields = self.FIELDS

        # Initialize the fields map.  This is where field values are
        # actually kept.
        self._fields_map = {}

        # Look up __docformat__
        self._docformat = DEFAULT_DOCFORMAT
        if module is not None:
            try: self._docformat = module.value().__docformat__.lower()
            except: pass
            
        # Ignore __docformat__ region codes.
        try: self._docformat = self._docformat.split()[0]
        except: pass

        # Check that it's an acceptable format.
        if (self._docformat not in ('epytext', 'plaintext') and
            self._uid.is_module()):
            estr = ("Unknown __docformat__ value %s; " % self._docformat +
                    "treating as plaintext.")
            self._field_warnings.append(estr)
            self._docformat = 'plaintext'

        # If there's a doc string, parse it.
        docstring = _getdoc(obj)
        if type(docstring) == type(''): docstring = docstring.strip()
        if docstring:
            self._documented = 1
            if self._docformat == 'epytext':
                self.__parse_docstring(docstring)
            else:
                self._descr = epytext.parse_as_literal(docstring)
        else:
            self._documented = 0
    
    #////////////////////////////
    #// Accessors
    #////////////////////////////

    def documented(self):
        """
        @return: True if the object documented by this C{ObjDoc} has a
        docstring.
        @rtype: C{boolean}
        """
        return self._documented
            
    def uid(self):
        """
        @return: The UID of the object documented by this C{ObjDoc}.
        @rtype: L{UID}
        """
        return self._uid

    def descr(self):
        """
        @return: A description of the object documented by this
        C{ObjDoc}.
        @rtype: L{xml.dom.minidom.Document}
        """
        return self._descr

    def fields(self):
        """
        @return: A list of the fields that are given values in the
            docstring of the object documented by this C{ObjDoc}.
            The fields are listed in the order that they first
            appear in the docstring.
        @rtype: C{list} of L{DocField}
        """
        # Sort by self._fields:
        return [f for f in self._fields if self._fields_map.has_key(f)]

    def field_values(self, field):
        """
        @return: A list of the values that are specified for the
            given field in the docstring of the object documented
            by this C{ObjDoc}.  Values are listed in the order that
            they appear in the docstring.
        @rtype: C{list} of L{xml.dom.minidom.Element}
        """
        return self._fields_map[field]
    
    def sortorder(self):
        """
        @return: A list specifying the sort order that should be used
            for the object's children.  Elements that are in this list
            should appear before elements that are not in this list;
            and elements that are in this list should appear in the
            order that they appear in this list.
        @rtype: C{list} of C{string}
        """
        return self._sortorder

    #////////////////////////////
    #// Protected
    #////////////////////////////

    def _process_field(self, tag, arg, descr, warnings):
        """
        This method should be overridden, and called as the default
        case.
        """
        if tag in ('deffield', 'newfield'):
            try:
                field = _descr_to_docfield(arg, descr)
                self._fields.append(field)
            except ValueError:
                warnings.append('Bad %s' % tag)
            return
        
        if tag == 'sort':
            if arg is not None:
                warnings.append(tag+' did not expect an argument')
                return
            if self._sortorder is None: self._sortorder = []
            try:
                self._sortorder += _descr_to_identifiers(descr)
            except ValueError, e:
                warnings.append('Bad sort order list')
            return
                
        for field in self._fields:
            if tag not in field.tags: continue
            
            # Special handling for @todo <version>: ...
            if tag == 'todo' and arg is not None:
                field = DocField(['todo:%s' % arg],
                                 'To Do for Version %s' % arg)
                if not self._fields_map.has_key(field):
                    self._fields.append(field)
                arg = None
                    
            # Create the field, if it doesn't exist yet.
            if not self._fields_map.has_key(field):
                self._fields_map[field] = []
            values = self._fields_map[field]

            if arg is not None:
                warnings.append(tag+' did not expect an argument')
                return
            if not field.multivalue and len(values) > 0:
                warnings.append(tag+ ' redefined')
                del values[:]
            values.append(descr)
            return

        if tag in _KNOWN_FIELD_TAGS:
            warnings.append('Invalid context for field tag %r' % tag)
        else:
            warnings.append('Unknown field tag %r' % tag)
        
    #////////////////////////////
    #// Private
    #////////////////////////////

    def __parse_docstring(self, docstring):
        # Parse the documentation, and store any errors or warnings.
        parse_warnings = self._parse_warnings
        parse_errors = self._parse_errors
        field_warnings = self._field_warnings
        pdoc = epytext.parse(docstring, parse_errors, parse_warnings)

        # If there were any errors, handle them by simply treating
        # the docstring as a single literal block.
        if parse_errors:
            self._descr = epytext.parse_as_literal(docstring)
            return

        # Extract and process any fields
        if (pdoc.hasChildNodes() and pdoc.childNodes[0].hasChildNodes() and
            pdoc.childNodes[0].childNodes[-1].tagName == 'fieldlist'):
            fields = pdoc.childNodes[0].childNodes[-1].childNodes
            pdoc.childNodes[0].removeChild(pdoc.childNodes[0].childNodes[-1])
            for field in fields:
                # Get the tag
                tag = field.childNodes[0].childNodes[0].data.lower()
                field.removeChild(field.childNodes[0])

                # Get the argument.
                if field.childNodes and field.childNodes[0].tagName == 'arg':
                    arg = field.childNodes[0].childNodes[0].data
                    field.removeChild(field.childNodes[0])
                else:
                    arg = None

                # Process the field.
                field.tagName = 'epytext'
                self._process_field(tag, arg, field, field_warnings)

        # Save the remaining docstring as the description..
        if pdoc.hasChildNodes() and pdoc.childNodes[0].hasChildNodes():
            self._descr = pdoc
        else:
            self._descr = None

    def _print_errors(self, stream=None):
        """
        Print any errors that were encountered while constructing this
        C{ObjDoc} to C{stream}.  This method should be called at the
        end of the constructor of every class that is derived from
        C{ObjDoc}.
        
        @rtype: C{None}
        """
        parse_warnings = self._parse_warnings
        parse_errors = self._parse_errors
        field_warnings = self._field_warnings

        # Set it every time, in case something changed sys.stderr
        # (like epydoc.gui :) )
        if stream is None: stream = sys.stderr
        
        # Supress warnings/errors, if requested
        if self.__verbosity <= -1: parse_warnings = []
        if self.__verbosity <= -2: field_warnings = []
        if self.__verbosity <= -3: parse_errors = []
        
        # Print the errors and warnings.
        if (parse_warnings or parse_errors or field_warnings):
            # Figure out our file and line number, if possible.
            try:
                (filename, startline) = _find_docstring(self._uid)
                if startline is None: startline = 0
            except:
                (filename, startline) = (None, 0)
            
            if stream.softspace: print >>stream
            print >>stream, '='*75
            if filename is not None:
                print >>stream, filename
                print >>stream, ('In %s docstring (line %s):' %
                                 (self._uid, startline+1))
            else:
                print >>stream, 'In %s docstring:' % self._uid
            print >>stream, '-'*75
            for error in parse_errors:
                error.linenum += startline
                print >>stream, error.as_error()
            for warning in parse_warnings:
                warning.linenum += startline
                print >>stream, warning.as_warning()
            for warning in field_warnings:
                if startline is None:
                    print >>stream, '       '+warning
                else:
                    estr =' Warning: %s' % warning
                    estr = epytext.wordwrap(estr, 7, startindex=7).strip()
                    print >>stream, '%5s: %s' % ('L'+`startline+1`, estr) 
            print >>stream
        
#////////////////////////////////////////////////////////
#// ModuleDoc
#////////////////////////////////////////////////////////
class ModuleDoc(ObjDoc):
    """
    The documentation for a module or package.  This documentation
    consists of standard documentation fields (descr, author, etc.)
    and the following module-specific fields:
    
        - X{classes}: A list of all classes contained in the
          module/package 
        - X{functions}: A list of all functions contained in the
          module/package
        - X{variables}: A list of all variables contained in the
          module/package
        - X{modules}: A list of all modules contained in the
          package (packages only)

    For more information on the standard documentation fields, see
    L{ObjDoc}.

    @group Accessors: groups, functions, classes, variables,
        imported_functions, imported_classes, package, ispackage,
        ismodule, modules
    @group Modifiers: remove_autogenerated_variables, add_module

    @type _classes: C{list} of L{Link}
    @ivar _classes: A list of all classes contained in the
        module/package. 
    
    @type _functions: C{list} of L{Link}
    @ivar _functions: A list of all functions contained in the
        module/package.

    @type _variables: C{list} of L{Var}
    @ivar _variables: A list of all variables defined by this
        module/package. 
    
    @type _modules: C{list} of L{Link}
    @ivar _modules: A list of all modules conained in the package
        (package only).
    """
    def __init__(self, uid, verbosity=0):
        mod = uid.value()
        self._tmp_var = {}
        self._tmp_type = {}
        self._tmp_groups = {}
        self._tmp_group_order = []
        ObjDoc.__init__(self, uid, verbosity)

        # If mod is a package, then it will contain a __path__
        if mod.__dict__.has_key('__path__'): self._modules = []
        else: self._modules = None

        # Handle functions, classes, and variables.
        self._classes = []
        self._functions = []
        self._imported_classes = []
        self._imported_functions = []
        self._variables = []
        for (field, val) in mod.__dict__.items():
            vuid = make_uid(val, self._uid, field)
                
            # Don't do anything for these special variables:
            if field in ('__builtins__', '__doc__', '__all__', '__file__',
                         '__path__', '__name__', 
                         '__extra_epydoc_fields__', '__docformat__'):
                continue
            # Don't do anything if it doesn't have a full-path UID.
            if vuid is None: continue
            # Don't do anything for modules.
            if vuid.is_module(): continue

            # Is it a function?
            if vuid.is_function() or vuid.is_builtin_function():
                if vuid.module() == self._uid:
                    self._functions.append(Link(field, vuid))
                else:
                    self._imported_functions.append(Link(field, vuid))

            # Is it a class?
            elif vuid.is_class():
                if vuid.module() == self._uid:
                    self._classes.append(Link(field, vuid))
                else:
                    self._imported_classes.append(Link(field, vuid))

            # Is it a variable?
            else:
                autogen = 1 # is it autogenerated?
                descr = self._tmp_var.get(field)
                if descr is not None:
                    del self._tmp_var[field]
                    autogen = 0
                typ = self._tmp_type.get(field)
                if typ is not None:
                    del self._tmp_type[field]
                    autogen = 0
                else: typ = epytext.parse_type_of(val)
                self._variables.append(Var(vuid, descr, typ, 1, autogen))

        # Add the remaining variables
        for (name, descr) in self._tmp_var.items():
            typ = self._tmp_type.get(name)
            if typ is not None: del self._tmp_type[name]
            vuid = make_uid(None, self._uid, name)
            self._variables.append(Var(vuid, descr, typ, 0))

        # Make sure we used all the type fields.
        if self._tmp_type != {}:
            for key in self._tmp_type.keys():
                estr = '@type for unknown variable %s' % key
                self._field_warnings.append(estr)
        del self._tmp_var
        del self._tmp_type

        # Wait until later to handle groups (after all modules have
        # been registered.)
        self._groups = None

        # Print out any errors/warnings that we encountered.
        self._print_errors()

    def _process_field(self, tag, arg, descr, warnings):
        if tag == 'group':
            if arg is None:
                warnings.append(tag+' expected an argument (group name)')
                return
            try:
                idents = _descr_to_identifiers(descr)
            except ValueError, e:
                warnings.append('Bad group identifier list')
                return
            self._tmp_groups[arg] = idents
            self._tmp_group_order.append(arg)
        elif tag in ('variable', 'var'):
            if arg is None:
                warnings.append(tag+' expected a single argument')
                return
            if self._tmp_var.has_key(arg):
                warnings.append('Redefinition of @%s %s' % (tag, arg))
            self._tmp_var[arg] = descr
        elif tag == 'type':
            if arg is None:
                warnings.append(tag+' expected a single argument')
                return
            if self._tmp_type.has_key(arg):
                warnings.append('Redefinition of @%s %s' % (tag, arg))
            self._tmp_type[arg] = descr
        else:
            ObjDoc._process_field(self, tag, arg, descr, warnings)

    def __repr__(self):
        str = '<ModuleDoc: '+`self._uid`+' ('
        if (not self._modules and not self._classes and
            not self._functions and not self._variables):
            return str[:-2]+'>'
        if self._modules:
            str += `len(self._modules)`+' modules; '
        if self._classes:
            str += `len(self._classes)`+' classes; '
        if self._functions:
            str += `len(self._functions)`+' functions; '
        if self._variables:
            str += `len(self._variables)`+' variables; '
        return str[:-2]+')>'

    def _find_groups(self):
        # Put together groups
        self._groups = []
        if self._tmp_groups:
            elts = {}
            if self.ispackage():
                for m in self.modules(): elts[m.name()] = m.target()
            for c in self.classes(): elts[c.name()] = c.target()
            for f in self.functions(): elts[f.name()] = f.target()
            for v in self.variables(): elts[v.name()] = v.uid()
            for name in self._tmp_group_order:
                members = self._tmp_groups[name]
                group = []
                for member in members:
                    try:
                        group.append(elts[member])
                    except KeyError:
                        estr = ('Group member not found: %s.%s' %
                                (self.uid(), member))
                        self._field_warnings.append(estr)
                if group:
                    self._groups.append((name, group))
                else:
                    estr = 'Empty group %r deleted' % name
                    self._field_warnings.append(estr)

    #////////////////////////////
    #// Accessors
    #////////////////////////////

    def groups(self):
        if self._groups is None: self._find_groups()
        return self._groups
        
    def functions(self):
        """
        @return: A list of all functions defined by the
            module/package documented by this C{ModuleDoc}.
        @rtype: C{list} of L{Link}
        """
        return self._functions
    
    def classes(self):
        """
        @return: A list of all classes defined by the
            module/package documented by this C{ModuleDoc}. 
        @rtype: C{list} of L{Link}
        """
        return self._classes
    
    def variables(self):
        """
        @return: A list of all variables defined by the
            module/package documented by this C{ModuleDoc}. 
        @rtype: C{list} of L{Var}
        """
        return self._variables

    def imported_functions(self):
        """
        @return: A list of all functions contained in the
            module/package documented by this C{ModuleDoc} that are
            not defined by that module/package.
        @rtype: C{list} of L{Link}
        """
        return self._imported_functions
    
    def imported_classes(self):
        """
        @return: A list of all classes contained in the
            module/package documented by this C{ModuleDoc} that are
            not defined by that module/package.
        @rtype: C{list} of L{Link}
        """
        return self._imported_classes
    
    def package(self):
        """
        @return: The package that contains the module documented by
            this C{ModuleDoc}, or C{None} if no package contains the
            module. 
        @rtype: L{UID} or C{None}
        """
        return self._uid.package()    

    def ispackage(self):
        """
        @return: True if this C{ModuleDoc} documents a package (not a
            module). 
        @rtype: C{boolean}
        """
        return self._modules != None
    
    def ismodule(self):
        """
        @return: True if this C{ModuleDoc} documents a module (not a
            package). 
        @rtype: C{boolean}
        """
        return self._modules == None
    
    def modules(self):
        """
        @return: A list of the known modules and subpackages conained
            in the package documented by this C{ModuleDoc}. 
        @rtype: C{list} of L{Link}
        @raise TypeError: If this C{ModuleDoc} does not document a
            package. 
        """
        if self._modules == None:
            raise TypeError('This ModuleDoc does not '+
                            'document a package.')
        return self._modules
    
    #////////////////////////////
    #// Modifiers
    #////////////////////////////

    def remove_autogenerated_variables(self):
        self._variables = [v for v in self._variables
                           if not v.autogenerated()]

    def add_module(self, module):
        """
        Register a submodule for the package doumented by this
        C{ModuleDoc}.  This must be done externally, since we can't
        determine the submodules of a package through introspection
        alone.  This is automatically called by L{DocMap.add} when new
        modules are added to a C{DocMap}.

        @param module: The unique identifier of the module or subpackage.
        @type module: L{UID}
        @rtype: C{None}
        """
        if self._modules == None:
            raise TypeError('This ModuleDoc does not '+
                            'document a package.')
        name = (module.__name__.split('.'))[-1]
        self._modules.append(Link(name, make_uid(module, self._uid, name)))

#////////////////////////////////////////////////////////
#// ClassDoc
#////////////////////////////////////////////////////////
class ClassDoc(ObjDoc):
    """
    The documentation for a class.  This documentation consists of
    standard documentation fields (descr, author, etc.)  and the
    following class-specific fields:
    
        - X{bases}: A list of the class's base classes
        - X{subclasses}: A list of the class's known subclasses
        - X{methods}: A list of the methods defined by the class
        - X{staticmethods}: A list of static methods defined by
          the class.
        - X{classmethods}: A list of class methods defined by the
          class.
        - X{properties}: A list of properties defined by the class.
        - X{ivariables}: A list of the instance variables defined by the
          class
        - X{cvariables}: A list of the class variables defined by the
          class
        - X{module}: The module that defines the class

    For more information on the standard documentation fields, see
    L{ObjDoc}.

    @group Accessors: groups, is_exception, methods, classmethods,
        staticmethods, properties, allmethods, cvariables,
        ivariables, bases, subclasses, property_type, base_order
    @group Inheritance: add_subclass, inherit, _inherit_vars,
        _inherit_groups

    @type _methods: C{list} of L{Link}
    @ivar _methods: A list of all methods contained in this class. 

    @type _ivariables: C{list} of L{Var}
    @ivar _ivariables: A list of all instance variables defined by this 
        class.
    
    @type _cvariables: C{list} of L{Var}
    @ivar _cvariables: A list of all class variables defined by this 
        class.

    @type _bases: C{list} of L{Link}
    @ivar _bases: A list of the identifiers of this class's bases.
    """
    def __init__(self, uid, verbosity=0):
        cls = uid.value()
        self._tmp_ivar = {}
        self._tmp_cvar = {}
        self._tmp_type = {}
        self._tmp_groups = {}
        self._tmp_group_order = []
        self._property_type = {}
        ObjDoc.__init__(self, uid, verbosity)

        # Handle methods & class variables
        self._methods = []
        self._cvariables = []
        self._ivariables = []
        self._staticmethods = []
        self._classmethods = []
        self._properties = []

        # Find the order that bases are searched in.
        self._base_order = _find_base_order(cls)

        try: fields = dir(cls)
        except: fields = []
        for field in fields:
            val = getattr(cls, field)
            
            # Don't do anything for these special variables:
            if field in ('__doc__', '__module__', '__dict__', '__weakref__'):
                continue

            # Find the class that defines the field; and get the value
            # directly from that class (so methods have the right uid).
            container = None
            for base in self._base_order:
                if base.__dict__.has_key(field):
                    container = make_uid(base)
                    val = getattr(base, field)
                    break

            linkname = field
            private_prefix = '_%s__' % container.shortname()
            if field.startswith(private_prefix):
                if container == self._uid:
                    # If it's private and belongs to this class, then
                    # undo the private name mangling.
                    linkname = linkname[len(private_prefix)-2:]
                else:
                    # If it's private, and belongs to a parent class,
                    # then don't even list it here.
                    continue

            # Deal with static/class methods and properties. (Python 2.2)
            try:
                # Get the un-munged value.
                try: rawval = container.value().__dict__.get(field)
                except: pass

                if isinstance(rawval, staticmethod):
                    vuid = make_uid(rawval, container, linkname)
                    vlink = Link(linkname, vuid)
                    self._staticmethods.append(vlink)
                    continue
                elif isinstance(rawval, classmethod):
                    vuid = make_uid(rawval, container, linkname)
                    vlink = Link(linkname, vuid)
                    self._classmethods.append(vlink)
                    continue
                elif isinstance(rawval, property):
                    vuid = make_uid(rawval, container, linkname)
                    vlink = Link(linkname, vuid)
                    self._properties.append(vlink)
                    continue
            except NameError: pass
                
            # Create a UID and Link for the field value.
            vuid = make_uid(val, container, linkname)
            vlink = Link(linkname, vuid)

            #print uid, field, container, vuid
            
            # Don't do anything if it doesn't have a full-path UID.
            if vuid is None: continue
            # Don't do anything for modules.
            if vuid.is_module(): continue

            # Is it a method?
            if vuid.is_routine():
                self._methods.append(vlink)

            elif container == self._uid:
                # Is it an instance variable?
                if self._tmp_ivar.has_key(field):
                    descr = self._tmp_ivar[field]
                    del self._tmp_ivar[field]
                    typ = self._tmp_type.get(field)
                    if typ is not None: del self._tmp_type[field]
                    else: typ = epytext.parse_type_of(val)
                    self._ivariables.append(Var(vuid, descr, typ, 1))
                    
                # Is it a class variable?
                else:
                    autogen = 1 # is it autogenerated?
                    descr = self._tmp_cvar.get(field)
                    if descr is not None:
                        del self._tmp_cvar[field]
                        autogen = 0
                    typ = self._tmp_type.get(field)
                    if typ is not None:
                        del self._tmp_type[field]
                        autogen = 0
                    else: typ = epytext.parse_type_of(val)
                    self._cvariables.append(Var(vuid, descr, typ, 1, autogen))

        # Keep track of types for properties.
        for prop in self._properties:
            name = prop.name()
            typ = self._tmp_type.get(name)
            if typ is not None:
                if prop.target().cls() != self._uid:
                    estr = "@type can't be used on an inherited properties"
                    self._field_warnings.append(estr)
                self._property_type[prop.target()] = typ
                del self._tmp_type[name]

        # Add the remaining class variables
        for (name, descr) in self._tmp_cvar.items():
            typ = self._tmp_type.get(name)
            if typ is not None: del self._tmp_type[name]
            vuid = make_uid(None, self._uid, name)
            self._cvariables.append(Var(vuid, descr, typ, 0))

        # Add the instance variables.
        for (name, descr) in self._tmp_ivar.items():
            typ = self._tmp_type.get(name)
            if typ is not None: del self._tmp_type[name]
            vuid = make_uid(None, self._uid, name)
            self._ivariables.append(Var(vuid, descr, typ, 0))

        # Make sure we used all the type fields.
        if self._tmp_type:
            for key in self._tmp_type.keys():
                estr = '@type for unknown variable %s' % key
                self._field_warnings.append(estr)
        del self._tmp_ivar
        del self._tmp_type

        # Add links to base classes.
        try: bases = cls.__bases__
        except AttributeError: bases = []
        self._bases = [Link(base.__name__, make_uid(base)) for base in bases
                       if (type(base) is types.ClassType or
                           (isinstance(base, types.TypeType)))]

        # Initialize subclass list.  (Subclasses get added
        # externally with add_subclass())
        self._subclasses = []

        # Is it an exception?
        try: self._is_exception = issubclass(cls, Exception)
        except TypeError: self._is_exception = 0

        # Inherited variables (added externally with inherit())
        self._inh_cvariables = []
        self._inh_ivariables = []

        # Put together the groups
        self._find_groups()

        # Print out any errors/warnings that we encountered.
        self._print_errors()

    def _process_field(self, tag, arg, descr, warnings):
        if tag == 'group':
            if arg is None:
                warnings.append(tag+' expected an argument (group name)')
            else:
                try:
                    idents = _descr_to_identifiers(descr)
                except ValueError, e:
                    warnings.append('Bad group identifier list: %s' % e)
                    return
                self._tmp_groups[arg] = idents
                self._tmp_group_order.append(arg)
        elif tag in ('cvariable', 'cvar'):
            if arg is None:
                warnings.append(tag+' expected a single argument')
                return
            if self._tmp_cvar.has_key(arg):
                warnings.append('Redefinition of @%s %s' % (tag, arg))
            self._tmp_cvar[arg] = descr
        elif tag in ('ivariable', 'ivar'):
            if arg is None:
                warnings.append(tag+' expected a single argument')
                return
            if self._tmp_ivar.has_key(arg):
                warnings.append('Redefinition of @%s %s' % (tag, arg))
            self._tmp_ivar[arg] = descr
        elif tag == 'type':
            if arg is None:
                warnings.append(tag+' expected a single argument')
                return
            if self._tmp_type.has_key(arg):
                warnings.append('Redefinition of @%s %s' % (tag, arg))
            self._tmp_type[arg] = descr
        else:
            ObjDoc._process_field(self, tag, arg, descr, warnings)

    def __repr__(self):
        str = '<ClassDoc: '+`self._uid`+' ('
        if (not self._bases and not self._methods and
            not self._cvariables and not self._ivariables and
            not self._subclasses):
            return str[:-2]+'>'
        if self._bases:
            str += `len(self._bases)`+' base classes; '
        if self._methods:
            str += `len(self._methods)`+' methods; '
        if self._cvariables:
            str += `len(self._cvariables)`+' class variabless; '
        if self._ivariables:
            str += `len(self._ivariables)`+' instance variables; '
        if self._subclasses:
            str += `len(self._subclasses)`+' subclasses; '
        return str[:-2]+')>'

    def _find_groups(self):
        # Put together groups
        self._groups = []
        
        if self._tmp_groups:
            elts = {}
            processed = {} # For error messages.
            for m in self.allmethods(): elts[m.name()] = m.target()
            for p in self.properties(): elts[p.name()] = p.target()
            for v in self.ivariables(): elts[v.name()] = v.uid()
            for v in self.cvariables(): elts[v.name()] = v.uid()
            for c in self.subclasses(): elts[c.name()] = c.uid()
            for name in self._tmp_group_order:
                members = self._tmp_groups[name]
                group = []
                for member in members:
                    try:
                        group.append(elts[member])
                        processed[member] = name
                        del elts[member]
                    except KeyError:
                        if processed.has_key(member):
                            estr = ('%s.%s is already in group %s.' %
                                    (self.uid(), member, processed[member]))
                        else:
                            estr = ('Group member not found: %s.%s' %
                                    (self.uid(), member))
                        self._field_warnings.append(estr)
                if group:
                    self._groups.append((name, group))
                else:
                    estr = 'Empty group %r deleted' % name
                    self._field_warnings.append(estr)

    #////////////////////////////
    #// Accessors
    #////////////////////////////

#     def inherited_cvariables(self): return self._inh_cvariables 
#     def inherited_ivariables(self): return self._inh_ivariables

    def groups(self):
        return self._groups
        
    def is_exception(self):
        """
        @return: True if this C{ClassDoc} documents an exception
            class. 
        @rtype: C{boolean}
        """
        return self._is_exception

    def methods(self):
        """
        @return: A list of all (instance) methods defined by the
            class documented by this C{ClassDoc}.
        @rtype: C{list} of L{Link}
        """
        return self._methods
    
    def classmethods(self):
        """
        @return: A list of all class methods defined by the class
            documented by this C{ClassDoc}.
        @rtype: C{list} of L{Link}
        """
        return self._classmethods
    
    def staticmethods(self):
        """
        @return: A list of all static methods defined by the class
            documented by this C{ClassDoc}.
        @rtype: C{list} of L{Link}
        """
        return self._staticmethods

    def properties(self):
        """
        @return: A list of all properties defined by the class
            documented by this C{ClassDoc}.
        @rtype: C{list} of L{Link}
        """
        return self._properties

    def allmethods(self):
        """
        @return: A list of all instance, class, and static methods
            defined by the class documented by this C{ClassDoc}.
        @rtype: C{list} of L{Link}
        @see: L{methods}
        @see: L{staticmethods}
        @see: L{classmethods}
        """
        return self._methods + self._classmethods + self._staticmethods
    
    def cvariables(self):
        """
        @return: A list of all class variables defined by the class
            documented by this C{ClassDoc}.
        @rtype: C{list} of L{Var}
        """
        return self._cvariables
    
    def ivariables(self):
        """
        @return: A list of all instance variables defined by the class
            documented by this C{ClassDoc}.
        @rtype: C{list} of L{Var}
        """
        return self._ivariables

    def bases(self):
        """
        @return: A list of all base classes for the class documented
            by this C{ClassDoc}.
        @rtype: C{list} of L{Link}
        """
        return self._bases
    
    def subclasses(self):
        """
        @return: A list of known subclasses for the class documented by
            this C{ClassDoc}.
        @rtype: C{list} of L{Link}
        """
        return self._subclasses
    
    def property_type(self, uid):
        """
        @return: The type for the given property, as specified by the
        
            docstring of the class documented by this C{ClassDoc}.  If
            the docstring doesn't specify a type, then C{None} is
            returned.  (But note that the property can also specify
            its type in its own docstring).
        @rtype: L{xml.dom.minidom.Element} or C{None}
        """
        return self._property_type.get(uid, None)

    def base_order(self):
        """
        @return: A list of all base ancestors of the class documented
            by this C{ClassDoc}, listed in the order that they are
            searched by C{Python} for members.  The first element of
            this list will always be the C{UID} of the class documented
            by this C{ClassDoc}.
        @rtype: C{list} of L{UID}
        """
        return [make_uid(b) for b in self._base_order]

    #////////////////////////////
    #// Modifiers
    #////////////////////////////

    def add_subclass(self, cls):
        """
        Register a subclass for the class doumented by this
        C{ClassDoc}.  This must be done externally, since we can't
        determine a class's subclasses through introspection
        alone.  This is automatically called by L{DocMap.add} when new
        classes are added to a C{DocMap}.

        @param cls: The unique identifier of the subclass.
        @type cls: L{UID}
        @rtype: C{None}
        """
        cuid = make_uid(cls, self._uid, cls.__name__)
        self._subclasses.append(Link(cls.__name__, cuid))

    #////////////////////////////
    #// Inheritance
    #////////////////////////////

    def inherit(self, base_docs, inheritance_groups,
                inherit_groups):
        """
        Add inherited variables and groups to this C{ClassDoc}.  To
        search for inherited variables and groups, C{inherit} uses a
        list of the documentation objects for every base ancestor of
        the class documented by this C{ClassDoc}.  Typical usage is:

            >>> doc.inherit([docmap[b] for b in doc.base_order()])

        @type base_docs: C{list} of L{ClassDoc}
        @param base_docs: A list of the C{ClassDoc}s for every base
            ancestor of the class documented by this C{ClassDoc}.
            These should be the C{ClassDoc}s for the classes returned
            by L{base_order}, in the order that they are returned by
            L{base_order}.
        @type inheritance_groups: C{boolean}
        @param inheritance_groups: If true, then create a group for
            each base ancestor, containing the members that are
            inherited from that base.  These groups have names of
            the form C{'Inherited from M{base}'}.
        @type inherit_groups: C{boolean}
        @param inherit_groups: If true, then inherit groups from the
            base ancestors.
        @rtype: C{None}
        """
        self._inherit_vars(base_docs)
        if inheritance_groups:
            self._add_inheritance_groups()
        if inherit_groups:
            self._inherit_groups(base_docs)

    def _inherit_vars(self, base_docs):
        """
        Add inherited class and instance variables to this
        C{ClassDoc}.  To search for inherited variables,
        C{inherit_vars} uses a list of the documentation objects for
        every base ancestor of the class documented by this
        C{ClassDoc}.

        @type base_docs: C{list} of L{ClassDoc}
        @param base_docs: A list of the C{ClassDoc}s for every base
            ancestor of the class documented by this C{ClassDoc}.
            These should be the C{ClassDoc}s for the classes returned
            by L{base_order}, in the order that they are returned by
            L{base_order}.
        @rtype: C{None}
        """
        # Use these dictionaries to assign a Var to each variable
        # name.  The values of these dictionaries will give us the
        # ivariables and cvariables lists, when we're done.
        ivariables_map = {}
        cvariables_map = {}
        for ivar in self._ivariables:
            ivariables_map[ivar.uid().shortname()] = ivar
        for cvar in self._cvariables:
            cvariables_map[cvar.uid().shortname()] = cvar

        # Skip base_docs[0], since that's ourselves.
        for base_doc in base_docs[1:]:
            if base_doc is None: continue

            # Inherit instance variables.
            for base_ivar in base_doc.ivariables():
                # Ignore ivars that the base inherited from higher up
                if base_ivar.uid().cls() != base_doc.uid(): continue
                
                name = base_ivar.uid().shortname()
                if ivariables_map.has_key(name):
                    # We already have this ivariable.
                    pass
                elif cvariables_map.has_key(name):
                    # We have it listed as a cvariable.  If the cvar
                    # was autogenerated, then merge it with base_ivar,
                    # and list it under ivariables; otherwise, leave
                    # it as is.
                    cvar = cvariables_map[name]
                    if cvar.autogenerated() and not base_ivar.autogenerated():
                        ivar = Var(cvar.uid(), base_ivar.descr(), 
                                  base_ivar.type(), cvar.has_value, 0)
                        ivariables_map[name] = ivar
                        del cvariables_map[name]
                else:
                    # Copy the ivariable from the base class.
                    ivariables_map[name] = base_ivar

            # Update class variables.
            for base_cvar in base_doc.cvariables():
                # Ignore cvars that the base inherited from higher up
                if base_cvar.uid().cls() != base_doc.uid(): continue
                
                name = base_cvar.uid().shortname()
                if ivariables_map.has_key(name):
                    # We already have this listed as an ivariable.
                    pass
                elif cvariables_map.has_key(name):
                    # We already have this cvariable.  But if our cvar
                    # was autogenerated, then merge it with base_cvar.
                    cvar = cvariables_map[name]
                    if cvar.autogenerated() and not base_cvar.autogenerated():
                        cvar = Var(cvar.uid(), base_cvar.descr(),
                                   base_cvar.type(), cvar.has_value, 0)
                        cvariables_map[name] = cvar
                else:
                    # Copy the cvariable from the base class.
                    cvariables_map[name] = base_cvar

        # Extract the variable lists from the maps.
        self._ivariables = ivariables_map.values()
        self._cvariables = cvariables_map.values()

    def _inherit_groups(self, base_docs):
        """
        Inherit groups from the given list of C{ClassDoc}s.  These
        should be the C{ClassDoc}s for the classes returned by
        L{base_order}, in the order that they are returned by
        L{base_order}.

        @type base_docs: C{list} of L{ClassDoc}
        @param base_docs: The documentation for the 
        @rtype: C{None}
        """
        elts = None

        # Skip base_docs[0], since that's ourselves.
        for base_doc in base_docs[1:]:
            if base_doc is None: continue
            for name, members in base_doc.groups():
                # Initialize elts, if it's not already initialized.
                if elts is None:
                    elts = {}
                    for m in self.allmethods(): elts[m.name()] = m.target()
                    for p in self.properties(): elts[p.name()] = p.target()
                    for v in self.ivariables(): elts[v.name()] = v.uid()
                    for v in self.cvariables(): elts[v.name()] = v.uid()
                    for c in self.subclasses(): elts[c.name()] = c.uid()
                    
                # Find the corresponding group in our own group list;
                # if it's not there, then create it.
                for group in self._groups:
                    if group[0] == name: break
                else:
                    group = (name, [])
                    self._groups.append(group)

                # Copy all members of the base class's group into our
                # own group.  If something's been overridden, then add
                # the overriding object's uid to the group, too.
                for member in members:
                    if member not in group[1]:
                        if not elts.has_key(member.shortname()):
                            # Add the member.
                            group[1].append(member)
                            elts[member.shortname()] = member
                        else:
                            # Add whatever overrides the member.
                            overrider = elts[member.shortname()]
                            if overrider not in group[1]:
                                group[1].append(overrider)

    def _add_inheritance_groups(self):
        for (groupname, groupmembers) in self._groups:
            if groupname.startswith('Inherited'):
                estr = '"Inherited..." is a reserved group name.'
                self._field_warnings.append(estr)

        inh_groups = {}

        # Mark inherited methods & properties
        for link in self.allmethods()+self.properties():
            uid = link.target()
            if uid.cls() != self._uid:
                name = 'Inherited from %s' % uid.cls().shortname()
                if not inh_groups.has_key(name): inh_groups[name] = []
                inh_groups[name].append(uid)

        # Mark inherited variables
        for var in self.ivariables()+self.cvariables():
            uid = var.uid()
            if uid.cls() != self._uid:
                name = 'Inherited from %s' % uid.cls().shortname()
                if not inh_groups.has_key(name): inh_groups[name] = []
                inh_groups[name].append(uid)

        inh_groupnames = inh_groups.keys()
        inh_groupnames.sort()
        for groupname in inh_groupnames:
            self._groups.append((groupname, inh_groups[groupname]))

#////////////////////////////////////////////////////////
#// FuncDoc
#////////////////////////////////////////////////////////
class FuncDoc(ObjDoc):
    """
    The documentation for a function or method.  This documentation
    consists of the standard documentation fields (descr, author,
    etc.) and the following class-specific fields:

        - X{parameters}: A list of the function's parameters
        - X{vararg}: The function's vararg parameter, or C{None}
        - X{kwarg}: The function's keyword parameter, or C{None}
        - X{returns}: The function's return value
        - X{raises}: A list of exceptions that may be raised by the
          function. 
        - X{overrides}: The method that this method overrides.

    For more information on the standard documentation fields, see
    L{ObjDoc}.

    @group Accessors: parameters, vararg, kwarg, returns, raises,
        overrides, matches_override, parameter_list

    @type _params: C{list} of L{Var}
    @ivar _params: A list of this function's normal parameters.
    @type _vararg_param: L{Var}
    @ivar _vararg_param: This function's vararg parameter, or C{None}
        if it has none.
    @type _kwarg_param: L{Var}
    @ivar _kwarg_param: This function's keyword parameter, or C{None}
        if it has none.
    @type _return: L{Var}
    @ivar _return: This function's return value.
    @type _raises: C{list} of L{Raise}
    @ivar _raises: The exceptions that may be raised by this
        function.
    @cvar _SIGNATURE_RE: A regular expression that is used to check
        whether a builtin function or method has a signature in its
        docstring.
    """
    def __init__(self, uid, verbosity=0):
        func = uid.value()
        self._tmp_param = {}
        self._tmp_type = {}
        self._raises = []
        self._overrides = None
        self._matches_override = 0
        ObjDoc.__init__(self, uid, verbosity)

        if self._uid.is_method(): func = func.im_func
        if type(func) is types.FunctionType:
            self._init_signature(func)
            self._init_params()
        elif self._uid.is_routine():
            self._init_builtin_signature(func)
            self._init_params()
        else:
            raise TypeError("Can't document %s" % func)
        
        if self._uid.is_method():
            self._find_override(self._uid.cls().value())
            if self._overrides == self._uid:
                # Print a warning message, and set overrides=None
                if sys.stderr.softspace: print >>sys.stderr
                estr = 'Warning: %s appears to override itself' % self._uid
                print >>sys.stderr, estr
                self._overrides = None
                #raise ValueError('Circular override: %s' % self._uid)

        # Print out any errors/warnings that we encountered.
        self._print_errors()

    # The regular expression that is used to check whether a builtin
    # function or method has a signature in its docstring.  Err on the
    # side of conservatism in detecting signatures.
    _SIGNATURE_RE = re.compile(
        # Class name (for builtin methods)
        r'^\s*((?P<self>\w+)\.)?' +
        
        # The function name (must match exactly)
        r'(?P<func>\w+)' +
        
        # The parameters
        r'\((?P<params>(\s*\[?\s*[\w\-\.]+(=.+?)?'+
        r'(\s*\[?\s*,\s*\]?\s*[\w\-\.]+(=.+?)?)*\]*)?)\s*\)' +
        
        # The return value (optional)
        r'(\s*(->|<=+>)\s*(?P<return>\S.*?))?'+
        
        # The end marker
        r'\s*(\n|\s+--\s+|$|\.\s|\.\n)')
        
    def _init_builtin_signature(self, func):
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
        self._params = []
        self._kwarg_param = None
        self._vararg_param = None
        self._return = Param('return')

        m = FuncDoc._SIGNATURE_RE.match(_getdoc(func) or '')
        if m and m.group('func') == func.__name__:
            params = m.group('params')
            rtype = m.group('return')
            selfparam = m.group('self')
            
            if selfparam and not rtype: 
                self._vararg_param = Param('...')
                return
            
            # Extract the parameters from the signature.
            if params:
                # Figure out which parameters are optional.
                while '[' in params or ']' in params:
                    m2 = re.match(r'(.*)\[([^\[\]]+)\](.*)', params)
                    if not m2:
                        self._vararg_param = Param('...')
                        return
                    (start, mid, end) = m2.groups()
                    mid = re.sub(r'((,|^)\s*[\w\-\.]+)', r'\1=...', mid)
                    params = start+mid+end

                params = re.sub(r'=...=' , r'=', params)
                for name in params.split(','):
                    if '=' in name: (name, default) = name.split('=',1)
                    else: default = None
                    name = name.strip()
                    if name == '...':
                        self._vararg_param = Param('...', default=default)
                    elif name.startswith('**'):
                        self._kwarg_param = Param(name[1:], default=default)
                    elif name.startswith('*'):
                        self._vararg_param = Param(name[1:], default=default)
                    else:
                        self._params.append(Param(name, default=default))

            # Extract the return type/value from the signature
            if rtype:
                if selfparam:
                    self._return.set_descr(epytext.parse_as_para(rtype))
                else:
                    self._return.set_type(epytext.parse_as_para(rtype))

            # Add the self parameter, if it was specified.
            if selfparam:
                self._params.insert(0, Param(selfparam))

            # Remove the signature from the description.
            text = self._descr.childNodes[0].childNodes[0].childNodes[0]
            text.data = FuncDoc._SIGNATURE_RE.sub('', text.data, 1)
            if (text.data == '' and len(self._descr.childNodes) == 1 and
                len(self._descr.childNodes[0].childNodes) == 1 and
                len(self._descr.childNodes[0].childNodes[0].childNodes) == 1):
                # We dispensed of all documentation.
                self._descr = None
                
        else:
            # We couldn't parse the signature.
            self._vararg_param = Param('...')

        # What do we do with documented parameters?  Esp. if we just
        # got "..." for the argument spec.
        ## If they specified parameters, use them. ??
        ## What about ordering??
        #if self._tmp_param or self._tmp_type:
        #    vars = {}
        #    for (name, descr) in self._tmp_param.items():
        #        vars[name] = Param(name, descr)
        #    for (name, type_descr) in self._tmp_type.items():
        #        if not vars.has_key(name): vars[name] = Param(name)
        #        vars[name].set_type(type_descr)
        #    self._params =
        
    def _init_signature(self, func):
        # Get the function's signature
        (args, vararg, kwarg, defaults) = inspect.getargspec(func)

        # Construct argument/return Variables.
        self._params = self._params_to_vars(args, defaults)
        if vararg: self._vararg_param = Param(vararg)
        else: self._vararg_param = None
        if kwarg: self._kwarg_param = Param(kwarg)
        else: self._kwarg_param = None
        self._return = Param('return')

    def _init_params(self):
        # Add descriptions/types to argument/return Variables.
        vars = self.parameter_list()[:]
        if self._vararg_param: vars.append(self._vararg_param)
        if self._kwarg_param: vars.append(self._kwarg_param)
        if self._return: vars.append(self._return)
        for arg in vars:
            name = arg.name()
            if self._tmp_param.has_key(name):
                arg.set_descr(self._tmp_param[name])
                del self._tmp_param[name]
            if self._tmp_type.has_key(name):
                arg.set_type(self._tmp_type[name])
                del self._tmp_type[name]
        if self._tmp_param != {}:
            for key in self._tmp_param.keys():
                estr = '@param for unknown parameter %s' % key
                self._field_warnings.append(estr)
        if self._tmp_type != {}:
            for key in self._tmp_type.keys():
                estr = '@type for unknown parameter %s' % key
                self._field_warnings.append(estr)
        del self._tmp_param
        del self._tmp_type

    def _params_to_vars(self, params, defaults):
        vars = []
        if defaults == None: defaults = []
        for i in range(len(params)):
            try: defaultindex = i-(len(params)-len(defaults))
            except TypeError:
                # We couldn't figure out how to line up defaults with vars.
                defaultindex=-1
            if type(params[i]) is types.StringType:
                vars.append(Param(params[i]))
                if defaultindex >= 0:
                    try: vars[-1].set_default(`defaults[defaultindex]`)
                    except: vars[-1].set_default('...')
            elif defaultindex >= 0:
                vars.append(self._params_to_vars(params[i],
                                                 defaults[defaultindex]))
            else:
                vars.append(self._params_to_vars(params[i], []))
        return vars

    def _find_override(self, cls):
        """
        Find the method that this method overrides.
        @return: True if we should keep looking for an overridden method.
        @rtype: C{boolean}
        """
        name = self.uid().shortname()
        for base in cls.__bases__:
            if base.__dict__.has_key(name):
                # We found a candidate for an overriden method.
                base_method = base.__dict__[name]
                if type(base_method) is types.FunctionType:
                    base_method = getattr(base, name)

                # Make sure it's some kind of method.
                if type(base_method) not in (types.MethodType,
                                            types.BuiltinMethodType,
                                             _WrapperDescriptorType,
                                             _MethodDescriptorType):
                    return 0

                # We've found a method that we override.
                self._overrides = make_uid(base_method)

                # Get the base & child argspecs.  If either fails,
                # then one is probably a builtin of some sort, so
                # _match_overrides should be 0 anyway.
                try:
                    basespec = inspect.getargspec(base_method.im_func)
                    childspec = inspect.getargspec(self._uid.value().im_func)
                except:
                    return 0
                
                # Does the signature of this method match the
                # signature of the method it overrides?
                if self._signature_match(basespec, childspec):
                    self._matches_override = 1
                elif name != '__init__':
                    # Issue a warning if the parameters don't match.
                    estr =(('The parameters of %s do not match the '+
                            'parameters of the base class method '+
                            '%s; not inheriting documentation.')
                           % (self.uid(), make_uid(base_method)))
                    self._field_warnings.append(estr)
                    
                return 0
            else:
                # It's not in this base; try its ancestors.
                if not self._find_override(base): return 0
        return 1

    def _signature_match(self, basespec, childspec):
        """
        @rtype: C{boolean}
        @return: True if the signature of C{childfunc} matches the
        signature of C{basefunc} well enough that we should inherit
        its documentation.
        """
        (b_arg,b_vararg,b_kwarg,b_default) = basespec
        (c_arg,c_vararg,c_kwarg,c_default) = childspec
        b_default = b_default or ()
        c_default = c_default or ()
        
        # The child method must define all arguments that the base
        # method does.
        if b_arg != c_arg[:len(b_arg)]:
            return 0

        # Any arg that's not defined by the base method must have a
        # default value in the child method; and any arg that has a
        # default value in the base method must have a default value
        # in the child method.
        if (len(b_arg)-len(b_default)) < (len(c_arg)-len(c_default)):
            return 0

        # Varargs must match; but the child method may add a varargs,
        # if the base method doesn't have one.
        if b_vararg is not None and b_vararg != c_vararg:
            return 0
    
        # Kwargs must match; but the child method may add a kwargs,
        # if the base method doesn't have one.
        if b_kwarg is not None and b_kwarg != c_kwarg:
            return 0

        # Otherwise, they match.
        return 1

    def _process_field(self, tag, arg, descr, warnings):
        if tag in ('return', 'returns'):
            if arg is not None:
                warnings.append(tag+' did not expect an argument')
                return
            if self._tmp_param.has_key('return'):
                warnings.append('Redefinition of @%s' % tag)
            self._tmp_param['return'] = descr
        elif tag in ('returntype', 'rtype'):
            if arg is not None:
                warnings.append(tag+' did not expect an argument')
                return
            if self._tmp_type.has_key('return'):
                warnings.append('Redefinition of @%s' % tag)
            self._tmp_type['return'] = descr
        elif tag in ('param', 'parameter', 'arg', 'argument'):
            if arg is None:
                warnings.append(tag+' expected a single argument')
                return
            if self._tmp_param.has_key(arg):
                warnings.append('Redefinition of @%s %s' % (tag, arg))
            self._tmp_param[arg] = descr
        elif tag == 'type':
            if arg is None:
                warnings.append(tag+' expected a single argument')
                return
            if self._tmp_type.has_key(arg):
                warnings.append('Redefinition of @%s %s' % (tag, arg))
            self._tmp_type[arg] = descr
        elif tag in ('raise', 'raises', 'exception', 'except'):
            if arg is None:
                warnings.append(tag+' expected a single argument')
                return
            self._raises.append(Raise(arg, descr))
        else:
            ObjDoc._process_field(self, tag, arg, descr, warnings)

    def __repr__(self):
        n_params = len(self._params)
        if self._vararg_param: n_params += 1
        if self._kwarg_param: n_params += 1
        str = '<FuncDoc: '+`self._uid`+' ('
        if (n_params == 0 and not self._raises):
            return str[:-2]+'>'
        if self._params:
            str += `len(self._params)`+' parameters; '
        if self._raises:
            str += `len(self._raises)`+' exceptions; '
        return str[:-2]+')>'

    #////////////////////////////
    #// Accessors
    #////////////////////////////

    def parameters(self):
        """
        @rtype: C{list} of L{Var}
        @return: The parameters for the function/method documented by
            this C{FuncDoc}.  This is typically a list of parameters,
            but it can contain sublists if the function/method's
            signature contains sublists.  For example, for the function:

                >>> def f(a, (b, c), d): pass

            C{parameters} will return a three-element list, whose
            second element is a sublist containing C{Var}s for C{b}
            and C{c}.

            If you just want a list of all parameters used by the
            function/method, use L{parameter_list} instead. 
        """
        return self._params
    
    def vararg(self):
        """
        @return: The vararg parameter for the function/method
            documented by this C{FuncDoc}, or C{None} if it has no
            vararg parameter.
        @rtype: L{Var} or C{None}
        """
        return self._vararg_param
    
    def kwarg(self):
        """
        @return: The keyword parameter for the function/method
            documented by this C{FuncDoc}, or C{None} if it has no
            keyword parameter.
        @rtype: L{Var} or C{None}
        """
        return self._kwarg_param
    
    def returns(self):
        """
        @return: The return value for the function/method
            documented by this C{FuncDoc}, or C{None} if it has no
            return value.
        @rtype: L{Var} or C{None}
        """
        return self._return
    
    def raises(self):
        """
        @return: A list of exceptions that may be raised by the
            function/method documented by this C{FuncDoc}.
        @rtype: C{list} of L{Raise}
        """
        return self._raises
    
    def overrides(self):
        """
        @return: The method overridden by the method documented by
            this C{FuncDoc}; or C{None} if the method documented by
            this C{FuncDoc} does not override any method, or if this
            C{FuncDoc} documents a function.
        @rtype: L{Link} or C{None}
        """
        return self._overrides

    def matches_override(self):
        """
        @return: True if the method documented by this C{FuncDoc}
            overrides another method, and its signature matches the
            signature of the overridden method.
        @rtype: C{boolean}
        """
        return self._matches_override

    def parameter_list(self):
        """
        @return: A (flat) list of all parameters for the
            function/method documented by this C{FuncDoc}.  If you are
            interested in the signature of the function/method, you
            should use L{parameters} instead.
        @rtype: C{list} of L{Var}
        @see: L{parameters}
        """
        if not hasattr(self, '_param_list'):
            self._param_list = _flatten(self._params)
        return self._param_list

#////////////////////////////////////////////////////////
#// PropertyDoc
#////////////////////////////////////////////////////////
class PropertyDoc(ObjDoc):
    """
    The documentation for a class property.  This documentation
    consists of the standard documentation fields (descr, author,
    etc.) and the following class-specific fields:

      - X{fget}: The property's get function
      - X{fset}: The property's set function
      - X{fdel}: The property's delete function
      - X{type}: The property's type

    For more information on the standard documentation fields, see
    L{ObjDoc}.

    @group Accessors: type, fget, fset, fdel
    """
    def __init__(self, uid, typ=None, verbosity=0):
        property = uid.value()
        self._fget = make_uid(property.fget)
        self._fset = make_uid(property.fset)
        self._fdel = make_uid(property.fdel)
        self._type = typ
        ObjDoc.__init__(self, uid, verbosity)

        # Print out any errors/warnings that we encountered.
        self._print_errors()

    def _process_field(self, tag, arg, descr, warnings):
        if tag == 'type':
            if arg is not None:
                warnings.append(tag+' did not expect an argument')
                return
            if self._type is not None:
                warnings.append('Redefinition of %s' % tag)
            self._type = descr
        else:
            ObjDoc._process_field(self, tag, arg, descr, warnings)

    def __repr__(self):
        return '<PropertyDoc: %s>' % self._uid

    #////////////////////////////
    #// Accessors
    #////////////////////////////

    def type(self):
        """
        @return: The DOM representation of an epytext description of
            this variable's type.
        @rtype: L{xml.dom.minidom.Element}
        """
        return self._type

    def fget(self):
        """
        @return: The UID of this property's get function.
        @rtype: L{UID}
        """
        return self._fget

    def fset(self):
        """
        @return: The UID of this property's set function.
        @rtype: L{UID}
        """
        return self._fset

    def fdel(self):
        """
        @return: The UID of this property's delete function.
        @rtype: L{UID}
        """
        return self._fdel

##################################################
## Documentation Management
##################################################

class DocMap(UserDict.UserDict):
    """
    A dictionary mapping each object to the object's documentation.
    Typically, modules or classes are added to the C{DocMap} using
    C{add}, which adds an object and everything it contains.  For
    example, the following code constructs a documentation map, adds
    the module "epydoc.epytext" to it, and looks up the documentation
    for "epydoc.epytext.parse":

        >>> docmap = DocMap()               # Construct a docmap
        >>> docmap.add(epydoc.epytext)      # Add epytext to it
        >>> docmap[epydoc.epytext.parse]    # Look up epytext.parse
        <FuncDoc: epydoc.epytext.parse (3 parameters; 1 exceptions)>
    """
    
    def __init__(self, verbosity=0, document_bases=1,
                 document_autogen_vars=1, inheritance_groups=0,
                 inherit_groups=1):
        """
        Create a new empty documentation map.

        @param verbosity: The verbosity of output produced when
            creating documentation for objects.  More positive numbers
            produce more verbose output; negative numbers supress
            warnings and errors.
        @type verbosity: C{int}
        @param document_bases: Whether or not documentation should
            automatically be built for the bases of classes that are
            added to the documentation map.
        @type document_bases: C{boolean}
        @type inheritance_groups: C{boolean}
        @param inheritance_groups: If true, then create a group for
            each base ancestor, containing the members that are
            inherited from that base.  These groups have names of
            the form C{'Inherited from M{base}'}.
        @type inherit_groups: C{boolean}
        @param inherit_groups: If true, then inherit groups from the
            base ancestors.
        """
        self._verbosity = verbosity
        self._document_bases = document_bases
        self._document_autogen_vars = document_autogen_vars
        self._inheritance_groups = inheritance_groups
        self._inherit_groups = inherit_groups
        self.data = {} # UID -> ObjDoc
        self._class_children = {} # UID -> list of UID
        self._package_children = {} # UID -> list of UID
        self._top = None
        self._inherited = 0

    def add_one(self, objID):
        """
        Add an object's documentation to this documentation map.  If
        you also want to include the objects contained by C{obj}, then
        use L{add}.

        @param obj: The object whose documentation should be added to
            this documentation map.
        @type obj: any
        @rtype: C{None}
        """
        obj = objID.value()
        self._inherited = 0
        self._top = None
            
        # If we've already documented it, don't do anything.
        if self.data.has_key(objID): return

        # If we couldn't find a UID, don't do anything.
        if objID is None: return
        
        if objID.is_module():
            self.data[objID] = ModuleDoc(objID, self._verbosity)
            for module in self._package_children.get(objID, []):
                self.data[objID].add_module(module)
            packageID = objID.package()
            if packageID is not None:
                if self.data.has_key(packageID):
                    self.data[packageID].add_module(obj)
                elif self._package_children.has_key(packageID):
                    self._package_children[packageID].append(obj)
                else:
                    self._package_children[packageID] = [obj]
            if not self._document_autogen_vars:
                self.data[objID].remove_autogenerated_variables()

        elif objID.is_class():
            self.data[objID] = ClassDoc(objID, self._verbosity)
            for child in self._class_children.get(objID, []):
                self.data[objID].add_subclass(child)
            try: bases = obj.__bases__
            except: bases = []
            for base in bases:
                if not (type(base) is types.ClassType or
                        (isinstance(base, types.TypeType))):
                    continue
                baseID=make_uid(base)
                if self.data.has_key(baseID):
                    self.data[baseID].add_subclass(obj)
                if self._class_children.has_key(baseID):
                    self._class_children[baseID].append(obj)
                else:
                    self._class_children[baseID] = [obj]

        elif objID.is_function() or objID.is_method():
            self.data[objID] = FuncDoc(objID, self._verbosity)
        elif objID.is_routine():
            self.data[objID] = FuncDoc(objID, self._verbosity)
        elif objID.is_property():
            # Does the class specify a type for the property?
            clsdoc = self.data[objID.parent()]
            typ = clsdoc.property_type(objID)

            self.data[objID] = PropertyDoc(objID, typ, self._verbosity)

    def add(self, obj):
        """
        Add the documentation for an object, and everything contained
        by that object, to this documentation map.

        @param obj: The object whose documentation should be added to
            this documentation map.
        @type obj: any
        @rtype: C{None}
        """
        # Check that it's a good object, and if not, issue a warning.
        if ((type(obj) not in (types.ModuleType, _MethodDescriptorType,
                             types.BuiltinFunctionType, types.MethodType,
                             types.BuiltinMethodType, types.FunctionType,
                             _WrapperDescriptorType, types.ClassType) and
             not isinstance(obj, types.TypeType))):
            if sys.stderr.softspace: print >>sys.stderr
            estr = 'Error: docmap cannot add an object with type '
            estr += type(obj).__name__
            print >>sys.stderr, estr
            return
        
        objID = make_uid(obj)
        self._add(objID)

    def _add(self, objID):
        if self.data.has_key(objID): return
        
        # Add ourselves.
        self.add_one(objID)
        doc = self.get(objID)
        if not doc: return

        # Recurse to any related objects.
        if objID.is_module():
            for link in doc.functions() + doc.classes():
                self._add(link.target())
        elif objID.is_class():
            for link in doc.allmethods():
                self._add(link.target())
            for var in doc.cvariables():
                if var.uid().is_class():
                    self._add(var.uid())
            for link in doc.properties():
                self.add_one(link.target())
            
            # Make sure all bases are added.
            if self._document_bases:
                for base in doc.bases():
                    self._add(base.target())

            doc.inherit([self.data.get(b) for b in doc.base_order()],
                        self._inheritance_groups, self._inherit_groups)

    def _toplevel(self, uid):
        """
        @return: True if the object identified by C{uid} is not
            contained (as a sub-package, module contents, class
            contents, etc.) by any other object in this docmap.
        @rtype: C{boolean}
        @param uid: The C{UID} to check.
        @type uid: L{UID}
        """
        for doc in self.values():
            if isinstance(doc, ModuleDoc):
                if uid.is_function():
                    if uid in [l.target() for l in doc.functions()]:
                        return 0
                elif uid.is_class():
                    if uid in [l.target() for l in doc.classes()]:
                        return 0
                if uid in [l.target() for l in doc.variables()]:
                    return 0
            elif isinstance(doc, ClassDoc):
                if uid.is_method():
                    if uid in [l.target() for l in doc.methods()]:
                        return 0
                if uid in [l.target() for l in doc.cvariables()]:
                    return 0
                if uid in [l.target() for l in doc.ivariables()]:
                    return 0
        return 1

    def top(self):
        """
        @return: The list of top-level objects documented by this
            documentation map.  The top-level objects are those that
            are not contained (as sub-packages, module contents, class
            contents, etc) by any other objects in the documentation
            map.
        @rtype: C{list} of L{UID}
        """
        if self._top is None:
            self._top = [uid for uid in self.keys()
                         if self._toplevel(uid)]
        return self._top

    def __getitem__(self, key):
        """
        @return: The documentation for the given object; or the object
            identified by C{key}, if C{key} is a L{UID}.
        @rtype: C{ObjDoc}
        @param key: The object whose documentation should be returned.
        @type key: any
        @raise KeyError: If the documentation for the object
            identified by C{key} is not contained in this
            documentation map.
        """
#         # Make sure all inheritances are taken care of.
#         if not self._inherited:
#             # this really needs to be done top-down.. how?
#             self._inherited = 1
#             for cls in self.keys():
#                 if not cls.is_class(): continue
#                 self[cls].inherit(*[self.get(UID(baseid)) for baseid
#                                     in cls.value().__bases__])

        if isinstance(key, UID):
            return self.data[key]
        else:
            raise TypeError()

    def __repr__(self):
        return '<Documentation: '+`len(self.data)`+' objects>'
