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
#// Var and Param
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
    def __init__(self, uid, descr=None, type=None, has_value=1):
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

    def __repr__(self):
        return '<Variable '+self._name+'>'

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
        return '<Variable '+self._name+'>'

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
        - X{authors}: A list of the object's authors
        - X{version}: The object's version
        - X{seealsos}: A list of the object's see-also links
        - X{requires}: Requirements for using the object
        - X{warnings}: Warnings about the object
        - X{sortorder}: The object's sort order, as defined by its
          C{__epydoc_sort__} variable.

    @ivar _uid: The object's unique identifier
    @type _uid: L{UID}
    @ivar _descr: The object's description, encoded as epytext.
    @type _descr: L{xml.dom.minidom.Document}
    @ivar _authors: Author(s) of the object
    @type _authors: C{list} of L{xml.dom.minidom.Element}
    @ivar _version: Version of the object
    @type _version: L{xml.dom.minidom.Element}
    @ivar _seealsos: See also entries
    @type _seealsos: C{list} of L{xml.dom.minidom.Element}
    @ivar _requires: Requirements of the object
    @type _requires: C{list} of L{xml.dom.minidom.Element}
    @ivar _warnings: Warnings about the object
    @type _warnings: C{list} of L{xml.dom.minidom.Element}

    @ivar _parse_warnings: Warnings generated when parsing the
        object's docstring.
    @ivar _parse_errors: Errors generated when parsing the object's
        docstring.
    @ivar _field_warnings: Warnings generated when processing the
        object's docstring's fields.
    """
    # The following field tags are currently under consideration:
    #     - @group: ...
    #     - @attention: ...
    #     - @note: ...
    #     - @bug: ...
    #     - @depreciated: ...
    #     - @invariant: ...
    #     - @precondition: ...
    #     - @postcondition: ...
    #     - @since: ...
    #     - @todo: ...
    def __init__(self, obj, verbosity=0):
        """
        Create the documentation for the given object.
        
        @param obj: The object to document.
        @type obj: any
        @param verbosity: The verbosity of output produced when
            creating documentation for the object.  More positive
            numbers produce more verbose output; negative numbers
            supress warnings and errors.
        @type verbosity: C{int}
        """
        self._uid = make_uid(obj)

        # Initialize fields.
        self._authors = []
        self._version = None
        self._seealsos = []
        self._descr = None
        self._requires = []
        self._warnings = []

        # Initialize errors/warnings, and remember verbosity.
        self.__verbosity = verbosity
        self._parse_errors = []
        self._parse_warnings = []
        self._field_warnings = []

        # If there's an __epydoc_sort__ attribute, keep it.
        if hasattr(obj, '__epydoc_sort__'):
            self._sortorder = obj.__epydoc_sort__
        elif hasattr(obj, '__all__'):
            self._sortorder = obj.__all__
        else:
            self._sortorder = None

        # Look up __docformat__
        if self._uid.is_module(): module = self._uid
        else: module = self._uid.module()
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
    
    def authors(self):
        """
        @return: A list of the authors of the object documented by
        this C{ObjDoc}.
        @rtype: C{list} of L{xml.dom.minidom.Element}
        """
        return self._authors
    
    def version(self):
        """
        @return: The version of the object documented by this
        C{ObjDoc}.
        @rtype: L{xml.dom.minidom.Element}
        """
        return self._version
    
    def seealsos(self):
        """
        @return: A list of descriptions of resources that are related
        to the object documented by this C{ObjDoc}.
        @rtype: C{list} of L{xml.dom.minidom.Element}
        """
        return self._seealsos

    def requires(self):
        """
        @return: A list of requirements for using the object
        documented by this C{ObjDoc}.
        @rtype: C{list} of L{xml.dom.minidom.Element}
        """
        return self._requires

    def warnings(self):
        """
        @return: A list of warnings about the object documented by
        this C{ObjDoc}.
        @rtype: C{list} of L{xml.dom.minidom.Element}
        """
        return self._warnings

    def sortorder(self):
        """
        @return: The object's C{__epydoc_sort__} list.
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
        if tag == 'author':
            if arg != None:
                warnings.append(tag+' did not expect an argument')
            self._authors.append(descr)
        elif tag == 'version':
            if arg != None:
                warnings.append(tag+' did not expect an argument')
            if self._version != None:
                warnings.append('Version redefined')
            self._version = descr
        elif tag in ('see', 'seealso'):
            if arg != None:
                warnings.append(tag+' did not expect an argument')
            self._seealsos.append(descr)
        elif tag in ('requires', 'require', 'requirement'):
            if arg != None:
                warnings.append(tag+' did not expect an argument')
            self._requires.append(descr)
        elif tag in ('warn', 'warning'):
            if arg != None:
                warnings.append(tag+' did not expect an argument')
            self._warnings.append(descr)
        else:
            warnings.append('Unknown field tag %r' %tag)
    
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
    def __init__(self, mod, verbosity=0):
        self._tmp_var = {}
        self._tmp_type = {}
        ObjDoc.__init__(self, mod, verbosity)

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
                         '__path__', '__name__', '__epydoc_sort__',
                         '__docformat__'):
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
                descr = self._tmp_var.get(field)
                if descr is not None: del self._tmp_var[field]
                typ = self._tmp_type.get(field)
                if typ is not None: del self._tmp_type[field]
                else: typ = epytext.parse_type_of(val)
                self._variables.append(Var(vuid, descr, typ, 1))

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

        # Print out any errors/warnings that we encountered.
        self._print_errors()

    def _process_field(self, tag, arg, descr, warnings):
        if tag in ('variable', 'var'):
            if arg == None:
                warnings.append(tag+' expected an argument')
                arg = ''
            if self._tmp_var.has_key(arg):
                warnings.append('Redefinition of @%s %s' % (tag, arg))
            self._tmp_var[arg] = descr
        elif tag == 'type':
            if arg == None:
                warnings.append(tag+' expected an argument')
                arg = ''
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

    #////////////////////////////
    #// Accessors
    #////////////////////////////
        
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
        - X{ivariables}: A list of the instance variables defined by the
          class
        - X{cvariables}: A list of the class variables defined by the
          class
        - X{module}: The module that defines the class

    For more information on the standard documentation fields, see
    L{ObjDoc}.

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
    def __init__(self, cls, verbosity=0):
        self._tmp_ivar = {}
        self._tmp_cvar = {}
        self._tmp_type = {}
        ObjDoc.__init__(self, cls, verbosity)

        # Handle methods & class variables
        self._methods = []
        self._cvariables = []
        self._ivariables = []

        try: items = cls.__dict__.items()
        except AttributeError: items = []
        for (field, val) in items:
            # Convert functions to methods.  (Since we're getting
            # values via __dict__)
            if type(val) is types.FunctionType:
                val = new.instancemethod(val, None, cls)
            vuid = make_uid(val, self._uid, field)
            
            # Don't do anything for these special variables:
            if field in ('__doc__', '__module__', '__epydoc_sort__',
                         '__dict__', '__weakref__'):
                continue
            # Don't do anything if it doesn't have a full-path UID.
            if vuid is None: continue
            # Don't do anything for modules.
            if vuid.is_module(): continue

            # Is it a method?  
            if vuid.is_routine():
                self._methods.append(Link(field, vuid))

            # Is it a class variable?
            else:
                descr = self._tmp_cvar.get(field)
                if descr is not None: del self._tmp_cvar[field]
                typ = self._tmp_type.get(field)
                if typ is not None: del self._tmp_type[field]
                else: typ = epytext.parse_type_of(val)
                self._cvariables.append(Var(vuid, descr, typ, 1))

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
                       if type(base) in (types.ClassType, types.TypeType)]

        # Initialize subclass list.  (Subclasses get added
        # externally with add_subclass())
        self._subclasses = []

        # How do I want to handle inheritance?
        self._methodbyname = {}
        for m in self._methods:
            self._methodbyname[m.target().shortname()] = 1
        for base in bases:
            self._inherit_methods(base)

        # Is it an exception?
        try: self._is_exception = issubclass(cls, Exception)
        except TypeError: self._is_exception = 0
        
        # Inherited variables (added externally with inherit())
        self._inh_cvariables = []
        self._inh_ivariables = []

        # Print out any errors/warnings that we encountered.
        self._print_errors()

    def _process_field(self, tag, arg, descr, warnings):
        if tag in ('cvariable', 'cvar'):
            if arg == None:
                warnings.append(tag+' expected an argument')
                arg = ''
            if self._tmp_cvar.has_key(arg):
                warnings.append('Redefinition of @%s %s' % (tag, arg))
            self._tmp_cvar[arg] = descr
        elif tag in ('ivariable', 'ivar'):
            if arg == None:
                warnings.append(tag+' expected an argument')
                arg = ''
            if self._tmp_ivar.has_key(arg):
                warnings.append('Redefinition of @%s %s' % (tag, arg))
            self._tmp_ivar[arg] = descr
        elif tag == 'type':
            if arg == None:
                warnings.append(tag+' expected an argument')
                arg = ''
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

    def _inherit_methods(self, base):
        for (field, val) in base.__dict__.items():
            if self._methodbyname.has_key(field): continue
            # Convert functions to methods.  (Since we're getting
            # values via __dict__)
            if type(val) is types.FunctionType:
                val = new.instancemethod(val, None, base)
            if type(val) not in (types.MethodType, types.BuiltinMethodType):
                continue
            vuid = make_uid(val, self._uid, field)
            if vuid is None: continue
            if not vuid.is_routine(): continue
            self._methodbyname[field] = 1
            self._methods.append(Link(field, vuid))

        for nextbase in base.__bases__:
            self._inherit_methods(nextbase)
            
#     # This never gets called right now!
#     def inherit(self, *basedocs):
#         self._inh_cvariables = []
#         self._inh_ivariables = []
#         for basedoc in basedocs:
#             if basedoc is None: continue
            
#             cvars = [cv.name() for cv
#                      in self._cvariables + self._inh_cvariables]
#             ivars = [iv.name() for iv
#                      in self._ivariables + self._inh_ivariables]
          
#             for cvar in basedoc.cvariables():
#                 if cvar.name() not in cvars:
#                     self._inh_cvariables.append(cvar)
    
#             for ivar in basedoc.ivariables():
#                 if ivar.name() not in ivars:
#                     self._inh_ivariables.append(ivar)
#         print self.uid(), 'IC', self._inh_cvariables
#         print self.uid(), 'IV', self._inh_ivariables

    #////////////////////////////
    #// Accessors
    #////////////////////////////

#     def inherited_cvariables(self): return self._inh_cvariables 
#     def inherited_ivariables(self): return self._inh_ivariables

    def is_exception(self):
        """
        @return: True if this C{ClassDoc} documents an exception
            class. 
        @rtype: C{boolean}
        """
        return self._is_exception

    def methods(self):
        """
        @return: A list of all methods defined by the class documented
            by this C{ClassDoc}.
        @rtype: C{list} of L{Link}
        """
        return self._methods
    
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
    
    def add_subclass(self, cls):
        """
        Register a subclass for the class doumented by this
        CC{ClassDoc}.  This must be done externally, since we can't
        determine a class's subclasses through introspection
        alone.  This is automatically called by L{DocMap.add} when new
        classes are added to a C{DocMap}.

        @param cls: The unique identifier of the subclass.
        @type cls: L{UID}
        @rtype: C{None}
        """
        cuid = make_uid(cls, self._uid, cls.__name__)
        self._subclasses.append(Link(cls.__name__, cuid))

#////////////////////////////////////////////////////////
#// FuncDoc
#////////////////////////////////////////////////////////
class FuncDoc(ObjDoc):
    """
    The documentation for a function of method.  This documentation
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
    def __init__(self, func, verbosity=0):
        self._tmp_param = {}
        self._tmp_type = {}
        self._raises = []
        self._overrides = None
        ObjDoc.__init__(self, func, verbosity)

        if self._uid.is_method(): func = func.im_func
        if type(func) is types.FunctionType:
            self._init_signature(func)
            self._init_params()
        elif self._uid.is_routine():
            self._init_builtin_signature(func)
            self._init_params()
        else:
            raise TypeError("Can't document %s" % func)
        if self._uid.is_method() and not self.documented():
            self._find_override(self._uid.cls().value())

        # Print out any errors/warnings that we encountered.
        self._print_errors()

    # The regular expression that is used to check whether a builtin
    # function or method has a signature in its docstring.  Err on the
    # side of conservatism in detecting signatures.
    _SIGNATURE_RE = re.compile(
        # Class name (for builtin methods)
        r'^\s*((?P<class>\w+)\.)?' +
        
        # The function name (must match exactly)
        r'(?P<func>\w+)' +
        
        # The parameters
        r'\((?P<params>(\s*\[?\s*[\w\-\.]+(=.+?)?'+
        r'(\s*\[?\s*,\s*\]?\s*[\w\-\.]+(=.+?)?)*\]*)?)\s*\)' +
        
        # The return value (optional)
        r'(\s*->\s*(?P<return>\S.*))?'+
        
        # The end marker
        r'\s*(\n|\s+--\s+|$)')
        
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
            # Extract the return type from the signature
            if rtype:
                self._return.set_type(epytext.parse_as_para(rtype))

            # Remove the signature from the description.
            text = self._descr.childNodes[0].childNodes[0].childNodes[0]
            text.data = FuncDoc._SIGNATURE_RE.sub('', text.data, 1)
        else:
            self._vararg_param = Param('...')

        # What do we do with documented parameters?
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
        @return: True if we haven't found an overridden method yet.
        @rtype: C{boolean}
        """
        name = self.uid().shortname()
        for base in cls.__bases__:
            if base.__dict__.has_key(name):
                # We found a candidate for an overriden method.
                base_method = base.__dict__[name]
                if type(base_method) is types.FunctionType:
                    base_method = new.instancemethod(base_method, None, base)

                # Make sure it's a method.
                if type(base_method) not in (types.MethodType,
                                            types.BuiltinMethodType):
                    return 0

                # Check that the parameters match.
                if (type(base_method) is types.MethodType and
                    type(self._uid.value() is types.MethodType) and
                    type(base_method.im_func) is types.FunctionType):
                    self_func = self._uid.value().im_func
                    base_func = base_method.im_func
                    self_argspec = inspect.getargspec(self_func)
                    base_argspec = inspect.getargspec(base_func)
                    
                    if self_argspec[:3] != base_argspec[:3]:
                        if name == '__init__': return 0
                        estr =(('The parameters of %s do not match the '+
                                'parameters of the base class method '+
                                '%s; not inheriting documentation.')
                               % (self.uid(), make_uid(base_method)))
                        self._field_warnings.append(estr)
                        return 0
                
                # We've found the method that we override.
                self._overrides = make_uid(base_method)
                return 0
            else:
                if not self._find_override(base): return 0
        return 1

    def _process_field(self, tag, arg, descr, warnings):
        # return, rtype, arg, type, raise
        if tag in ('return', 'returns'):
            if arg != None:
                warnings.append(tag+' did not expect an argument')
            if self._tmp_param.has_key('return'):
                warnings.append('Redefinition of @%s' % tag)
            self._tmp_param['return'] = descr
        elif tag in ('returntype', 'rtype'):
            if arg != None:
                warnings.append(tag+' did not expect an argument')
            if self._tmp_type.has_key('return'):
                warnings.append('Redefinition of @%s' % tag)
            self._tmp_type['return'] = descr
        elif tag in ('param', 'parameter', 'arg', 'argument'):
            if arg == None:
                warnings.append(tag+' expected an argument')
                arg = ''
            if self._tmp_param.has_key(arg):
                warnings.append('Redefinition of @%s %s' % (tag, arg))
            self._tmp_param[arg] = descr
        elif tag == 'type':
            if arg == None:
                warnings.append(tag+' expected an argument')
                arg = ''
            if self._tmp_type.has_key(arg):
                warnings.append('Redefinition of @%s %s' % (tag, arg))
            self._tmp_type[arg] = descr
        elif tag in ('raise', 'raises', 'exception', 'except'):
            if arg == None:
                warnings.append(tag+' expected an argument')
                arg = ''
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

    # , include_varargs, include_kwargs, include_return ??
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
    
    def __init__(self, verbosity=0, document_bases=1):
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
        """
        self._verbosity = verbosity
        self._document_bases = document_bases
        self.data = {} # UID -> ObjDoc
        self._class_children = {} # UID -> list of UID
        self._package_children = {} # UID -> list of UID
        self._top = None
        self._inherited = 0

    def add_one(self, obj):
        """
        Add an object's documentation to this documentation map.  If
        you also want to include the objects contained by C{obj}, then
        use L{add}.

        @param obj: The object whose documentation should be added to
            this documentation map.
        @type obj: any
        @rtype: C{None}
        """
        self._inherited = 0
        self._top = None
        objID = make_uid(obj)
            
        # If we've already documented it, don't do anything.
        if self.data.has_key(objID): return

        # If we couldn't find a UID, don't do anything.
        if objID is None: return
        
        if objID.is_module():
            self.data[objID] = ModuleDoc(obj, self._verbosity)
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

        elif objID.is_class():
            self.data[objID] = ClassDoc(obj, self._verbosity)
            for child in self._class_children.get(objID, []):
                self.data[objID].add_subclass(child)
            try: bases = obj.__bases__
            except: bases = []
            for base in bases:
                if type(base) not in (types.ClassType, types.TypeType):
                    continue
                baseID=make_uid(base)
                if self.data.has_key(baseID):
                    self.data[baseID].add_subclass(obj)
                if self._class_children.has_key(baseID):
                    self._class_children[baseID].append(obj)
                else:
                    self._class_children[baseID] = [obj]

        elif objID.is_function() or objID.is_method():
            self.data[objID] = FuncDoc(obj, self._verbosity)
        elif objID.is_routine():
            self.data[objID] = FuncDoc(obj, self._verbosity)

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
        if type(obj) not in (types.ModuleType, types.ClassType, types.TypeType,
                             types.BuiltinFunctionType, types.MethodType,
                             types.BuiltinMethodType, types.FunctionType):
            if sys.stderr.softspace: print >>sys.stderr
            estr = 'Error: docmap cannot add a %s' % type(object).__name__
            print >>sys.stderr, estr
            return
        
        objID = make_uid(obj)
        if self.data.has_key(objID): return

        # Add ourselves.
        self.add_one(obj)

        # Recurse to any related objects.
        if objID.is_module():
            for (field, val) in obj.__dict__.items():
                vuid = make_uid(val, objID, field)

                # Skip any imported values.
                if vuid.is_class() or vuid.is_function():
                    if vuid.module() != objID: continue

                if vuid.is_class():
                    self.add(val)
                elif vuid.is_routine():
                    self.add(val)
        elif objID.is_class():
            try: items = obj.__dict__.items()
            except AttributeError: items = []
            for (field, val) in items:
                # Convert functions to methods.  (Since we're getting
                # values via __dict__)
                if type(val) is types.FunctionType:
                    val = new.instancemethod(val, None, obj)

                vuid = make_uid(val, objID, field)
                if vuid.is_routine():
                    self.add(val)
                elif vuid.is_class():
                    self.add(val)
                    
            if self._document_bases:
                # Make sure all bases are added.
                for base in self.data[objID].bases():
                    self.add(base.target().value())

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
#         # Make sure all inheritences are taken care of.
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
