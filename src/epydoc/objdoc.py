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
dictionary from Python objects to C{ObjDoc}s.

Textual documentation entries (e.g., module descriptions, method
descriptions, variable types, see-also entries) are encoded as DOM
C{Elements}, using the DTD described in the C{epytext} module.

Each Python object is identified by a globally unique identifier,
implemented with the C{UID} class.  These identifiers are also used by
the C{Link} class to implement crossreferencing between C{ObjDoc}s.
"""

##################################################
## Imports
##################################################

import inspect, UserDict, epytext, string, new, re
import xml.dom.minidom
import types

from epydoc.uid import UID, Link

##################################################
## Helper
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

def _type(obj):
    """
    @return: an epytext representation of the type of C{obj}.  If
        C{obj} is an instance of a class, then the epytext
        representation contains a link to the instance's class.
        Otherwise, it contains the name of C{obj}'s type.
    @rtype: L{xml.dom.minidom.Element}
    """
    text = xml.dom.minidom.Element('epytext')
    para = xml.dom.minidom.Element('para')
    text.appendChild(para)
    if type(obj) is types.InstanceType:
        link = xml.dom.minidom.Element('link')
        name = xml.dom.minidom.Element('name')
        target = xml.dom.minidom.Element('target')
        para.appendChild(link)
        link.appendChild(name)
        link.appendChild(target)
        name.appendChild(xml.dom.minidom.Text(str(obj.__class__)))
        target.appendChild(xml.dom.minidom.Text(str(obj.__class__)))
    else:
        code = xml.dom.minidom.Element('code')
        para.appendChild(code)
        code.appendChild(xml.dom.minidom.Text(type(obj).__name__))
    return text

##################################################
## ObjDoc
##################################################

#////////////////////////////////////////////////////////
#// Var and Param
#////////////////////////////////////////////////////////

class Var:
    """
    The documentation for an individual variable.  This consists of
    the variable's name, its description, and its type.  C{Var}s are 
    used by L{ModuleDoc} (variables) and L{ClassDoc} (ivariables and
    cvariables); and L{FuncDoc} (params, vararg, kwarg, retval).
    """
    def __init__(self, name, descr=None, type=None, value=None):
        """
        Construct the documentation for a variable or parameter.

        @param name: The name of the variable.
        @type name: C{string}
        @param descr: The DOM representation of an epytext description
            of the variable (as produced by C{epytext.parse}).
        @type descr: C{xml.dom.minidom.Element}
        @param type: The DOM representation of an epytext description
            of the variable's type (as produced by C{epytext.parse}).
        @type type: C{xml.dom.minidom.Element}
        @param value:
          For variables:
            - C{None} if the variable's value is unknown
            - The UID of the variable's value, if it is a module,
              class, function, method, or type.
            - A string representation of the variable's value,
              otherwise.
          For parameters:
            - C{None} if the parameter has no default value.
            - A string representation of the parameter's default
              value, otherwise.
        @type value: C{string} or L{UID} or C{None}
        """
        self._name = name
        self._descr = descr
        self._type = type
        self._value = value
        
    def type(self):
        """
        @return: The DOM representation of an epytext description of
            this variable's type.
        @rtype: C{xml.dom.minidom.Element}
        """
        return self._type
    
    def descr(self):
        """
        @return: The DOM representation of an epytext description of
            this variable.
        @rtype: C{xml.dom.minidom.Element}
        """
        return self._descr
    
    def name(self):
        """
        @return: The name of this variable.
        @rtype: C{string}
        """
        return self._name
    
    def value(self):
        """
        @return: The value of this variable.
        
          For variables:
            - C{None} if the variable's value is unknown
            - The UID of the variable's value, if it is a module,
              class, function, method, or type.
            - A string representation of the variable's value,
              otherwise.
          For parameters:
            - C{None} if the parameter has no default value.
            - A string representation of the parameter's default
              value, otherwise.
        @rtype: C{string} or C{None}
        """
        return self._value

    def set_type(self, type):
        """
        Set this variable's type.
        
        @param type: The DOM representation of an epytext description
            of the variable's type (as produced by C{epytext.parse}).
        @type type: C{xml.dom.minidom.Element}
        @rtype: C{None}
        """
        self._type = type
        
    def set_descr(self, descr):
        """
        Set this variable's description.
        
        @type descr: C{xml.dom.minidom.Element}
        @param descr: The DOM representation of an epytext description
            of the variable's type (as produced by C{epytext.parse}).
        @rtype: C{None}
        """
        self._descr = descr
        
    def set_value(self, value):
        """
        Set this variable's value.
        
        @param value: The new value.
        @type value: C{string} or C{None}
        @rtype: C{None}
        """
        self._value = value
        
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
        @type descr: C{xml.dom.minidom.Element}
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
        @rtype: C{xml.dom.minidom.Element}
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

        - X{descr}: A description of the object
        - X{authors}: A list of the object's authors
        - X{version}: The object's version
        - X{seealsos}: A list of the object's see-also links
        - X{sortorder}: The object's sort order, as defined by its
          C{__epydoc_sort__} variable.

    @ivar _uid: The object's unique identifier
    @type _uid: L{UID}
    
    @ivar _descr: The object's description, encoded as epytext.
    @type _descr: C{Element}

    @ivar _authors: Author(s) of the object
    @type _authors: C{list} of C{Element}
    @ivar _version: Version of the object
    @type _version: C{Element}
    @ivar _seealsos: See also entries
    @type _seealsos: C{list} of C{Element}
    """
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
        self._uid = UID(obj)

        # Initialize fields.
        self._authors = []
        self._version = None
        self._seealsos = []
        self._descr = None

        # If there's an __epydoc_sort__ attribute, keep it.
        if hasattr(obj, '__epydoc_sort__'):
            self._sortorder = obj.__epydoc_sort__
        elif hasattr(obj, '__all__'):
            self._sortorder = obj.__all__
        else:
            self._sortorder = None

        # If there's a doc string, parse it.
        docstring = _getdoc(obj)
        if docstring:
            self._documented = 1
            self.__parse_docstring(docstring, verbosity)
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
        @returntype: C{Element}
        """
        return self._descr
    
    def authors(self):
        """
        @return: A list of the authors of the object documented by
            this C{ObjDoc}.
        @returntype: C{list} of C{Element}
        """
        return self._authors
    
    def version(self):
        """
        @return: The version of the object documented by this
            C{ObjDoc}.
        @returntype: C{Element}
        """
        return self._version
    
    def seealsos(self):
        """
        @return: A list of objects related to the object documented by 
            this C{ObjDoc}.
        @returntype: C{list} of C{Element}
        """
        return self._seealsos

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
        else:
            warnings.append('Unknown tag: '+tag)
    
    #////////////////////////////
    #// Private
    #////////////////////////////

    def __parse_docstring(self, docstring, verbosity):
        # Parse the documentation, and store any errors or warnings.
        parse_errors = []
        parse_warnings = []
        field_warnings=[]
        pdoc = epytext.parse(docstring, parse_errors, parse_warnings)

        # If there were any errors, handle them by simply treating
        # the docstring as a single literal block.
        if parse_errors:
            pdoc = epytext.parse_as_literal(docstring)

        # Extract and process any fields
        if pdoc.childNodes and pdoc.childNodes[-1].tagName == 'fieldlist':
            fields = pdoc.childNodes[-1].childNodes
            pdoc.removeChild(pdoc.childNodes[-1])
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

        # Supress warnings/errors, if requested
        if verbosity <= -1: parse_warnings = []
        if verbosity <= -2: field_warnings = []
        if verbosity <= -3: parse_errors = []
        
        # Print the errors and warnings.
        if (parse_warnings or parse_errors or field_warnings):
            if parse_errors:
                print "WARNING: Treating", self._uid, "docstring as literal"
            print '='*70
            print 'In '+`self.uid()`+' docstring:'
            print '-'*70
            for warning in parse_warnings:
                print warning.as_warning()
            for error in parse_errors:
                print error.as_error()
            for warning in field_warnings:
                print warning
            print
        
        # Save the remaining docstring as the description..
        if pdoc.hasChildNodes():
            self._descr = pdoc
        else:
            self._descr = None
        
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
        variables = {}
        self._imported_classes = []
        self._imported_functions = []
        for (field, val) in mod.__dict__.items():
            vuid = UID(val)
            # Don't do anything for introspection specials.
            if field in ('__builtins__', '__doc__',
                         '__file__', '__path__', '__name__'):
                continue
            # Don't do anything if it doesn't have a full-path UID.
            if not vuid.found_fullname(): continue
            # Don't do anything for modules.
            if vuid.is_module(): continue

            # Add the field to the appropriate place.
            if vuid.is_function() or vuid.is_builtin_function():
                if vuid.module() == self._uid:
                    self._functions.append(Link(field, vuid))
                else:
                    self._imported_functions.append(Link(field, vuid))
            elif vuid.is_class():
                if vuid.module() == self._uid:
                    self._classes.append(Link(field, vuid))
                else:
                    self._imported_classes.append(Link(field, vuid))
            else:
                value = UID(val)
                if not value.found_fullname():
                    try: value = `val`
                    except: value = None
                if self._tmp_type.has_key(field):
                    typ = self._tmp_type[field]
                    variables[field] = Var(field, None, typ, value)
                    del self._tmp_type[field]
                else:
                    variables[field] = Var(field, None, _type(val), value)

        # Add descriptions and types to variables
        for (name, descr) in self._tmp_var.items():
            var = variables.setdefault(name, Var(name))
            var.set_descr(descr)
            if self._tmp_type.has_key(name):
                var.set_type(self._tmp_type[name])
                del self._tmp_type[name]
        self._variables = variables.values()

        # Make sure we used all the type fields.
        if self._tmp_type != {}:
            for key in self._tmp_type.keys():
                print ('Warning: @type for unknown parameter: %s in %s' %
                       (key, self._uid))
        del self._tmp_var
        del self._tmp_type

    def _process_field(self, tag, arg, descr, warnings):
        if tag in ('variable', 'var'):
            if arg == None:
                warnings.append(tag+' expected an argument')
                arg = ''
            if self._tmp_var.has_key(arg):
                warnings.append('Redefinition of variable')
            self._tmp_var[arg] = descr
        elif tag == 'type':
            if arg == None:
                warnings.append(tag+' expected an argument')
                arg = ''
            if self._tmp_type.has_key(arg):
                warnings.append('Redefinition of variable '+
                                'type: '+arg)
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
        self._modules.append(Link(name, UID(module)))

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
        cvariables = {}
        self._methods = []

        try: items = cls.__dict__.items()
        except AttributeError: items = []
        for (field, val) in items:
            vuid = UID(val)
            # Don't do anything for introspection specials.
            if field in ('__doc__', '__module__'):
                continue
            # Don't do anything if it doesn't have a full-path UID.
            if not vuid.found_fullname(): continue
            # Don't do anything for modules.
            if vuid.is_module(): continue

            # Add the field to the appropriate place.
            # Note that, since we got it via __dict__, it'll be a
            # Function, not a Method.
            if vuid.is_function():
                method = new.instancemethod(val, None, cls)
                self._methods.append(Link(field, UID(method)))
            elif vuid.is_routine():
                self._methods.append(Link(field, vuid))
            else:
                value = UID(val)
                if not value.found_fullname():
                    try: value = `val`
                    except: value = None
                if self._tmp_type.has_key(field):
                    typ = self._tmp_type[field]
                    cvariables[field] = Var(field, None, typ, value)
                    del self._tmp_type[field]
                else:
                    cvariables[field] = Var(field, None, _type(val), value)

        # Add descriptions and types to class variables
        for (name, descr) in self._tmp_cvar.items():
            var = cvariables.setdefault(name, Var(name))
            var.set_descr(descr)
            if self._tmp_type.has_key(name):
                var.set_type(self._tmp_type[name])
                del self._tmp_type[name]
        self._cvariables = cvariables.values()

        # Construct instance variables.
        self._ivariables = []
        for (name, descr) in self._tmp_ivar.items():
            if self._tmp_type.has_key(name):
                self._ivariables.append(Var(name, descr, self._tmp_type[name]))
                del self._tmp_type[name]
            else:
                self._ivariables.append(Var(name, descr))

        # Make sure we used all the type fields.
        if self._tmp_type:
            for key in self._tmp_type.keys():
                print ('Warning: @type for unknown parameter: %s in %s' %
                       (key, self._uid))
        del self._tmp_ivar
        del self._tmp_type

        # Add links to base classes.
        try: bases = cls.__bases__
        except AttributeError: bases = []
        self._bases = [Link(base.__name__, UID(base)) for base in bases]

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

    def _process_field(self, tag, arg, descr, warnings):
        if tag in ('cvariable', 'cvar'):
            if arg == None:
                warnings.append(tag+' expected an argument')
                arg = ''
            if self._tmp_cvar.has_key(arg):
                warnings.append('Redefinition of variable')
            self._tmp_cvar[arg] = descr
        elif tag in ('ivariable', 'ivar'):
            if arg == None:
                warnings.append(tag+' expected an argument')
                arg = ''
            if self._tmp_ivar.has_key(arg):
                warnings.append('Redefinition of variable')
            self._tmp_ivar[arg] = descr
        elif tag == 'type':
            if arg == None:
                warnings.append(tag+' expected an argument')
                arg = ''
            if self._tmp_type.has_key(arg):
                warnings.append('Redefinition of variable'+\
                                  'type: '+`arg`)#+' ('+descr+')')
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
            vuid = UID(val)
            if vuid is None: continue
            if not vuid.is_routine(): continue
            if self._methodbyname.has_key(field): continue
            self._methodbyname[field] = 1
            if vuid.is_function():
                method = new.instancemethod(val, None, base)
                self._methods.append(Link(field, UID(method)))
            else:
                self._methods.append(Link(field, UID(val)))

        for nextbase in base.__bases__:
            self._inherit_methods(nextbase)
            
            # Don't do anything for introspection specials.
            if field in ('__builtins__', '__doc__',
                         '__file__', '__path__', '__name__'):
                continue
            # Don't do anything if it doesn't have a full-path UID.
            if not vuid.found_fullname(): continue
            # Don't do anything for modules.
            if vuid.is_module(): continue

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
        self._subclasses.append(Link(cls.__name__, UID(cls)))

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
        self._return = Var('return')

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
                        self._vararg_param = Var('...')
                        return
                    (start, mid, end) = m2.groups()
                    mid = re.sub(r'((,|^)\s*[\w\-\.]+)', r'\1=...', mid)
                    params = start+mid+end

                params = re.sub(r'=...=' , r'=', params)
                for name in params.split(','):
                    name = name.strip()
                    if '=' in name: (name, default) = name.split('=',1)
                    else: default = None
                    if name == '...':
                        self._vararg_param = Var('...', value=default)
                    elif name.startswith('**'):
                        self._kwarg_param = Var(name[1:], value=default)
                    elif name.startswith('*'):
                        self._vararg_param = Var(name[1:], value=default)
                    else:
                        self._params.append(Var(name.strip(), value=default))
            # Extract the return type from the signature
            if rtype:
                self._return.set_type(epytext.parse(rtype))

            # Remove the signature from the description.
            text = self._descr.childNodes[0].childNodes[0]
            text.data = FuncDoc._SIGNATURE_RE.sub('', text.data, 1)
        else:
            self._vararg_param = Var('...')

        # What do we do with documented parameters?
        ## If they specified parameters, use them. ??
        ## What about ordering??
        #if self._tmp_param or self._tmp_type:
        #    vars = {}
        #    for (name, descr) in self._tmp_param.items():
        #        vars[name] = Var(name, descr)
        #    for (name, type_descr) in self._tmp_type.items():
        #        if not vars.has_key(name): vars[name] = Var(name)
        #        vars[name].set_type(type_descr)
        #    self._params = 

    def _init_signature(self, func):
        # Get the function's signature
        (args, vararg, kwarg, defaults) = inspect.getargspec(func)

        # Construct argument/return Variables.
        self._params = self._params_to_vars(args, defaults)
        if vararg: self._vararg_param = Var(vararg)
        else: self._vararg_param = None
        if kwarg: self._kwarg_param = Var(kwarg)
        else: self._kwarg_param = None
        self._return = Var('return')

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
            for key in self._tmp_type.keys():
                print ('Warning: @param for unknown parameter: %s in %s' %
                       (key, self._uid))
        if self._tmp_type != {}:
            for key in self._tmp_type.keys():
                print ('Warning: @type for unknown parameter: %s in %s' %
                       (key, self._uid))
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
                vars.append(Var(params[i]))
                if defaultindex >= 0:
                    try: vars[-1].set_value(`defaults[defaultindex]`)
                    except: vars[-1].set_value('...')
            elif defaultindex >= 0:
                vars.append(self._params_to_vars(params[i],
                                                 defaults[defaultindex]))
            else:
                vars.append(self._params_to_vars(params[i], []))
        return vars
    
    def _find_override(self, cls):
        name = self.uid().shortname()
        for base in cls.__bases__:
            if base.__dict__.has_key(name):
                func = base.__dict__[name]
                fuid = UID(func)
                if fuid.is_function():
                    method = new.instancemethod(func, None, base)
                    self._overrides = UID(method)
                elif fuid.is_routine():
                    self._overrides = fuid
                break
            else:
                self._find_override(base)

    def _process_field(self, tag, arg, descr, warnings):
        # return, rtype, arg, type, raise
        if tag in ('return', 'returns'):
            if arg != None:
                warnings.append(tag+' did not expect an argument')
            if self._tmp_param.has_key('return'):
                warnings.append('Redefinition of return value')
            self._tmp_param['return'] = descr
        elif tag in ('returntype', 'rtype'):
            if arg != None:
                warnings.append(tag+' did not expect an argument')
            if self._tmp_type.has_key('return'):
                warnings.append('Redefinition of return value type')
            self._tmp_type['return'] = descr
        elif tag in ('param', 'parameter', 'arg', 'argument'):
            if arg == None:
                warnings.append(tag+' expected an argument')
                arg = ''
            if self._tmp_param.has_key(arg):
                warnings.append('Redefinition of parameter '+`arg`)
            self._tmp_param[arg] = descr
        elif tag == 'type':
            if arg == None:
                warnings.append(tag+' expected an argument')
                arg = ''
            if self._tmp_type.has_key(arg):
                warnings.append('Redefinition of variable '+\
                                  'type: '+`arg`)
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
        objID = UID(obj)
            
        #print 'Constructing docs for:', objID
        if self.data.has_key(objID): return
        
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
                baseID=UID(base)
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
        objID = UID(obj)
        if self.data.has_key(objID): return

        # Add ourselves.
        self.add_one(obj)

        # Recurse to any related objects.
        if objID.is_module():
            for val in obj.__dict__.values():
                valID = UID(val)

                # Skip any imported values.
                if valID.is_class() or valID.is_function():
                    if UID(val).module() != objID: continue

                if valID.is_class():
                    self.add(val)
                elif valID.is_routine():
                    self.add(val)
        elif objID.is_class():
            try: values = obj.__dict__.values()
            except AttributeError: values = []
            for val in values:
                valID = UID(val)
                    
                if valID.is_function():
                    self.add(new.instancemethod(val, None, obj))
                elif valID.is_routine():
                    self.add(val)
                elif valID.is_class():
                    self.add(val)
                    
            if self._document_bases:
                # Make sure all bases are added.
                for base in self.data[objID].bases():
                    self.add(base.target().object())

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
#                                     in cls.object().__bases__])

        if isinstance(key, UID):
            return self.data[key]
        else:
            return self.data[UID(key)]

    def __repr__(self):
        return '<Documentation: '+`len(self.data)`+' objects>'
