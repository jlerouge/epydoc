#
# epydoc.py
#
# A python documentation Module
# Edward Loper
#
# Created [01/30/01 05:18 PM]
# $Id$
#
# Compatable with Python 2.0 and up.
# Requires inspect.py (which is standard for Python 2.1 and up)
#

# To do:
#    - overriding/doc inheritance
#    - inheritance source pseudo-ClassDocs?
#    - clean up
#    - fix package link (when there's 1 package)

"""
Convert Python docstring comments into HTML pages.

Epydoc processes documentation strings in two phases:

1. Create a collection of Documentation objects, encoding the
   documentation of the objects to be documented.
2. Convert these Documentation objects into an output
   representation, such as HTML.

ObjDoc's point to each other with C{Link}s.
"""

##################################################
## Constants
##################################################

WARN_MISSING = 0
WARN_SKIPPING = 0

##################################################
## Imports
##################################################

import re, inspect, UserDict, epytext, sys, os.path
import string, xml, new
from xml.dom.minidom import Text as _Text
from types import ModuleType as _ModuleType
from types import ClassType as _ClassType
from types import FunctionType as _FunctionType
from types import BuiltinFunctionType as _BuiltinFunctionType
from types import BuiltinMethodType as _BuiltinMethodType
from types import MethodType as _MethodType
from types import StringType as _StringType

##################################################
## Cross-Referencing
##################################################
#
# We cross-reference between documentation by using the UID of the
# referenced object.  

class Link:
    """
    A cross-reference link between documentation.  A link consists of
    a name and a target.  The target is a unique identifier,
    identifying the object whose documentation is pointed to.  The
    name specifies how the link should appear in the source document.
    Usually, the name is just the (short) name of the target.
    However, it doesn't have to be.  For example, consider the
    following code:

        >>> def f(x): pass
        >>> g = f

    Links to g and f will have the same target (whose short name will
    be C{'f'}), but links to them will use different names (C{'f'} and
    C{'g'}, respectively).

    @ivar _target: The UID of the Python object pointed to by this
        Link. 
    @type _target: C{UID}
    @ivar _name: The name by which should be used to indicate this
        link in source documents.
    @type _name: C{string}
    """
    def __init__(self, name, target):
        """
        @type name: C{string}
        @type target: Python object or string
        """
        self._name = name
        self._target = UID(target)

    def __repr__(self):
        return self._name+'->'+`self._target`
        
    def name(self): return self._name
    def target(self): return self._target

def find_function_module(func):
    if not inspect.isfunction(func):
        raise TypeError("Expected a function")
    for module in sys.modules.values():
        if module == None: continue
        if func.func_globals == module.__dict__:
            return module
    raise ValueError("Couldn't the find module for this function")

class UID:
    """
    A unique identifier used to refer to a Python object.  UIDs are
    used by ObjDoc objects for the purpose of
    cross-referencing.  It is important that each object have one
    unique identifier, because one object may have more than one name.
    The UIDs are constructed directly from the objects that they point
    to, so they are guaranteed to be consistant.

    @ivar _id: The Python identifier for the object
    @type _id: C{int}
    @ivar _name: The dotted name for the object
    @type _name: C{string}
    @ivar _obj: The object
    @type _obj: (any)
    """
    def __init__(self, obj):
        if type(obj) == _StringType:
            self._obj = self._typ = self._id = None
            self._name = obj
            raise ValueError(obj)
            return
        
        self._id = id(obj)
        self._obj = obj
        
        if type(obj) == _ModuleType:
            self._name = obj.__name__
            
        elif type(obj) == _ClassType:
            self._name = (obj.__module__+'.'+obj.__name__)
                          
        elif type(obj) == _FunctionType:
            self._name = (find_function_module(obj).__name__+'.'+
                          obj.__name__)
                          
        elif type(obj) == _MethodType:
            self._name = (obj.im_class.__module__+'.'+
                          obj.im_class.__name__+'.'+
                          obj.__name__)

        else:
            try:
                self._name = obj.__name__+'-'+`id(obj)`
            except:
                print 'unknown', obj, dir(obj), type(obj)
                self._name = 'unknown-'+`id(obj)`

        if self._name == 'epytext.__repr__':
            raise ValueError()

    def name(self): return self._name
    def shortname(self): return self._name.split('.')[-1]
    def pathname(self): return os.path.join(*self._name.split('.'))
    def object(self): return self._obj
    def __repr__(self): return self._name
    def __cmp__(self, other): return cmp(self._name, other._name)
    def __hash__(self): return hash(self._name)

    def cls(self):
        if type(self._obj) == _MethodType: 
            return UID(self._obj.im_class)
        else:
            raise TypeError()
        
    def module(self):
        if type(self._obj) == _MethodType:
            return UID(sys.modules[self._obj.im_class.__module__])
        elif type(self._obj) == _ClassType:
            return UID(sys.modules[self._obj.__module__])
        elif type(self._obj) in (_FunctionType,):
            return UID(find_function_module(self._obj))
        else:
            raise TypeError()

    def package(self):
        if type(self._obj) == _ModuleType:
            dot = self._name.rfind('.')
            if dot < 0: return None
            return UID(sys.modules[self._name[:dot]])
        elif type(self._obj) in (_MethodType, _ClassType):
            return self.module().package()
        else:
            raise TypeError()

    def is_method(self):
        return type(self._obj) == _MethodType

    def is_package(self):
        "Return true if this is the UID for a package"
        return (type(self._obj) == _ModuleType and
                hasattr(self._obj, '__path__'))

##################################################
## ObjDoc
##################################################

#////////////////////////////////////////////////////////
#// Var and Param
#////////////////////////////////////////////////////////

class Var:
    """
    The documentation for an individual variable.  This consists of
    the variable's name, its description, and its type.  Variables are 
    used by ModuleDoc (variables) and ClassDoc (ivariables and
    cvariables); and functions (params, vararg, kwarg, retval).
    """
    def __init__(self, name, descr=None, type=None, default=None):
        self._name = name
        self._type = type
        self._descr = descr
        self._default = default
    def type(self): return self._type
    def descr(self): return self._descr
    def name(self): return self._name
    def default(self): return self._default
    def set_type(self, type): self._type = type
    def set_descr(self, descr):
        self._descr = descr
    def set_default(self, default): self._default = default
    def __repr__(self):
        if self._type:
            return '<Variable '+self._name+': '+`self._type`+'>'
        else:
            return '<Variable '+self._name+'>'

class Raise:
    """
    The documentation for the raising of an exception.
    """
    def __init__(self, name, descr):
        self._name = name
        self._descr = descr
    def name(self): return self._name
    def descr(self): return self._descr
        
#////////////////////////////////////////////////////////
#// Base ObjDoc Class
#////////////////////////////////////////////////////////
class ObjDoc:
    """
    A base class for objects encoding the documentation of Python
    objects.

    @ivar _uid:
    @type _uid: The object's unique identifier
    
    @ivar _descr: The object's description
    @type _descr: epytext

    @ivar _authors: Author(s) of the object
    @ivar _version: Version(s) of the object
    @ivar _seealsos: See also entries
    """
    def __init__(self, obj):
        """
        @type obj: any
        """
        self._uid = UID(obj)

        # Initialize fields.
        self._authors = []
        self._version = None
        self._seealsos = []
        self._descr = None

        # If there's a doc string, parse it.
        if hasattr(obj, '__doc__') and obj.__doc__ != None:
            self._documented = 1
            self.__parse_docstring(inspect.getdoc(obj))
        else:
            self._documented = 0
    
    #////////////////////////////
    #// Accessors
    #////////////////////////////

    def documented(self):
        return self._documented
            
    def uid(self):
        return self._uid

    def descr(self):
        """
        @return: a description of the object documented by this
            C{ObjDoc}.
        @returntype: C{Element}
        """
        return self._descr
    
    def authors(self):
        """
        @return: a list of the authors of the object documented by
            this C{ObjDoc}.
        @returntype: C{list} of C{Element}
        """
        return self._authors
    
    def version(self):
        """
        @return: the version of the object documented by this
            C{ObjDoc}.
        @returntype: C{Element}
        """
        return self._version
    
    def seealsos(self):
        """
        @return: a list of objects related to the object documented by 
            this C{ObjDoc}
        @returntype: C{list} of C{Element}
        """
        return self._seealsos

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
        elif tag == 'see':
            if arg != None:
                warnings.append(tag+' did not expect an argument')
            self._seealsos.append(descr)
        else:
            warnings.append('Unknown tag: '+tag)
    
    #////////////////////////////
    #// Private
    #////////////////////////////

    def __parse_docstring(self, docstring):
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
            if epytext.to_html(pdoc) == '':
                print 'WARNING: DIDN"T CATCH'
                print pdoc.toxml()
                raise ValueError()
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
    
        - classes: A list of any classes contained in the
          module/package 
        - functions: A list of any functions contained in the
          module/package
        - variables: A list of any variables contained in the
          module/package
        - modules: A list of any modules contained in the
          package (packages only)

    For more information on the standard documentation fields, see
    L{ObjDoc}.

    @type _classes: C{list} of C{Link}
    @ivar _classes: A list of any classes contained in the
        module/package. 
    
    @type _functions: C{list} of C{Link}
    @ivar _functions: A list of any functions contained in the
        module/package.

    @type _variables: C{list} of C{Var}
    @ivar _variables: A list of any variables defined by this
        module/package. 
    
    @type _modules: C{list} of C{Link}
    @ivar _modules: A list of any modules conained in the package
        (package only).
    """
    def __init__(self, mod):
        # Initilize the module from its docstring.
        self._tmp_var = {}
        self._tmp_type = {}
        ObjDoc.__init__(self, mod)

        # If mod is a package, then it will contain a __path__
        if mod.__dict__.has_key('__path__'): self._modules = []
        else: self._modules = None

        # Handle functions, classes, and variables.
        self._classes = []
        self._functions = []
        self._variables = []
        for (field, val) in mod.__dict__.items():
            if field in ('__builtins__', '__doc__',
                         '__file__', '__path__', '__name__'):
                continue

            # Don't do anything for modules.
            if type(val) == _ModuleType: continue

            if type(val) in (_FunctionType, _ClassType):
                try:
                    if UID(val).module() != self._uid:
                        if WARN_SKIPPING:
                            print 'Skipping imported value', val
                        continue
                except:
                    print 'ouch', val
                    continue
                

            # Add the field to the appropriate place.
            if type(val) in (_FunctionType, _BuiltinFunctionType):
                self._functions.append(Link(field, val))
            elif type(val) == _ClassType:
                self._classes.append(Link(field, val))

        # Add descriptions and types to variables
        self._variables = []
        for (name, descr) in self._tmp_var.items():
            var = Var(name, descr)
            self._variables.append(var)
            if self._tmp_type.has_key(name):
                var.set_type(self._tmp_type[name])
                del self._tmp_type[name]
        if self._tmp_type != {}:
            raise SyntaxError('Type for unknown var')
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
                warnings.append('Redefinition of variable'+
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
        
    def functions(self): return self._functions
    def classes(self): return self._classes
    def variables(self): return self._variables
    def package(self): return self._uid.package()

    def ispackage(self): return self._modules != None
    def ismodule(self): return self._modules == None
    def modules(self):
        if self._modules == None:
            raise TypeError('This ModuleDoc does not '+
                            'document a package.')
        return self._modules
    def add_module(self, module):
        if self._modules == None:
            raise TypeError('This ModuleDoc does not '+
                            'document a package.')
        name = (module.__name__.split('.'))[-1]
        self._modules.append(Link(name, module))

class ClassDoc(ObjDoc):
    """
    The documentation for a class.  This documentation consists of
    standard documentation fields (descr, author, etc.)  and the
    following class-specific fields:
    
        - bases: A list of the class's base classes
        - children: A list of the class's known child classes
        - methods: A list of the methods defined by the class
        - ivariables: A list of the instance variables defined by the
          class
        - cvariables: A list of the class variables defined by the
          class
        - module: The module that defines the class

    For more information on the standard documentation fields, see
    L{ObjDoc}.

    With classes comes inheritance.
       - Inheritance of methods (link to method)
       - Inheritance of method docs for overridden methods
       - Inheritance of cvars
       - Inheritance of ivars

    The first we can do pretty easily; the others are more
    troublesome.  For inheritance of method docs, we can decide
    *which* method we're inheriting from, by checking whether things
    have docstrings..  So we can have a link to it somehow.  For ivars 
    and cvars, we really need to have processed the parent
    docs.. hrm.  
    
    @type _methods: C{list} of C{Link}
    @ivar _methods: A list of any methods contained in this class. 

    @type _ivariables: C{list} of C{Var}
    @ivar _ivariables: A list of any instance variables defined by this 
        class.
    
    @type _cvariables: C{list} of C{Var}
    @ivar _cvariables: A list of any class variables defined by this 
        class.

    @type _bases: C{list} of C{Link}
    @ivar _bases: A list of the identifiers of this class's bases.
    """
    def __init__(self, cls):
        # Initilize the module from its docstring.
        self._tmp_ivar = {}
        self._tmp_cvar = {}
        self._tmp_type = {}
        ObjDoc.__init__(self, cls)

        # Handle methods & class variables
        self._cvariables = []
        self._methods = []

        for (field, val) in cls.__dict__.items():
            if field in ('__doc__', '__module__'):
                continue
            
            # Don't do anything for modules.
            if type(val) == _ModuleType: continue

            # Add the field to the appropriate place.
            # Note that, since we got it via __dict__, it'll be a
            # Function, not a Method.
            if type(val) is _FunctionType:
                method = new.instancemethod(val, None, cls)
                self._methods.append(Link(field, method))
            elif type(val) is _BuiltinMethodType:
                self._methods.append(Link(field, val))
                
        # Add descriptions and types to class variables
        self._cvariables = []
        for (name, descr) in self._tmp_cvar.items():
            if self._tmp_type.has_key(name):
                self._cvariables.append(Var(name, descr, self._tmp_type[name]))
                del self._tmp_type[name]
            else:
                self._cvariables.append(Var(name, descr))

        # Construct instance variables.
        self._ivariables = []
        for (name, descr) in self._tmp_ivar.items():
            if self._tmp_type.has_key(name):
                self._ivariables.append(Var(name, descr, self._tmp_type[name]))
                del self._tmp_type[name]
            else:
                self._ivariables.append(Var(name, descr))
        if self._tmp_type != {}:
            #raise SyntaxError('Type for unknown var')
            for key in self._tmp_type.keys():
                print 'Type for unknown var '+key+' in '+`self._uid`
        del self._tmp_ivar
        del self._tmp_type

        # Add links to base classes.
        self._bases = []
        for base in cls.__bases__:
            self._bases.append(Link(base.__name__, base))

        # Initialize child class list.  (Child classes get added
        # externally with add_child())
        self._children = []

        # How do I want to handle inheritance?
        self._methodbyname = {}
        for m in self._methods:
            self._methodbyname[m.target().shortname()] = 1
        for base in cls.__bases__:
            self._inherit(base)
        
        # Inherited values (added externally with inherit())
        self._inh_methods = []
        self._inh_cvariables = []
        self._inh_ivariables = []

    def _inherit(self, base):
        for (field, val) in base.__dict__.items():
            if type(val) not in (_FunctionType, _BuiltinMethodType):
                continue
            if self._methodbyname.has_key(field):
                continue
            self._methodbyname[field] = 1
            if type(val) is _FunctionType:
                method = new.instancemethod(val, None, base)
                self._methods.append(Link(field, method))
            elif type(val) is _BuiltinMethodType:
                self._methods.append(Link(field, val))

        for nextbase in base.__bases__:
            self._inherit(nextbase)
            
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
            not self._children):
            return str[:-2]+'>'
        if self._bases:
            str += `len(self._bases)`+' base classes; '
        if self._methods:
            str += `len(self._methods)`+' methods; '
        if self._cvariables:
            str += `len(self._cvariables)`+' class variabless; '
        if self._ivariables:
            str += `len(self._ivariables)`+' instance variables; '
        if self._children:
            str += `len(self._children)`+' child classes; '
        return str[:-2]+')>'

    # This never gets called right now!
#     def inherit(self, basedoc):
#         methods = [m.name() for m
#                    in self._methods + self._inh_methods] 
#         cvars = [cv.name() for cv
#                  in self._cvariables + self._inh_cvariabels]
#         ivars = [iv.name() for iv
#                  in self._ivariables + self._inh_ivariables]
        
#         for method in basedoc.methods():
#             if method.name() not in methods:
#                 self._inh_methods.append(method)

#         for cvar in basedoc.cvariables():
#             if cvar.name() not in cvars:
#                 self._inh_cvariables.append(cvar)

#         for ivar in basedoc.ivariables():
#             if ivar.name() not in ivars:
#                 self._inh_ivariables.append(ivar)

    #////////////////////////////
    #// Accessors
    #////////////////////////////

    def inherited_methods(self): return self._inh_methods
    def inherited_cvariables(self): return self._inh_cvariables 
    def inherited_ivariables(self): return self._inh_ivariables

    def overrides(self, method):
        return self._overrides.get(method, [])
    
    def methods(self):
        return self._methods
    def cvariables(self): return self._cvariables
    def ivariables(self): return self._ivariables

    def bases(self): return self._bases
    def children(self): return self._children
    def add_child(self, cls):
        self._children.append(Link(cls.__name__, cls))

class FuncDoc(ObjDoc):
    """
    Add 'overrides'??

    @type _params: C{list} of C{Var}
    @ivar _params: A list of this function's normal parameters.
    @type _vararg_param: C{Var}
    @ivar _vararg_param: This function's vararg parameter, or C{None}
        if it has none.
    @type _kwarg_param: C{Var}
    @ivar _kwarg_param: This function's keyword parameter, or C{None}
        if it has none.
    @type _return: C{Var}
    @ivar _return: This function's return value.
    @type _raises: C{list} of C{Raise}
    @ivar _raises: The exceptions that may be raised by this
        function. 
    """
    def _params_to_vars(self, params, defaults):
        vars = []
        if defaults == None: defaults = []
        for i in range(len(params)):
            defaultindex = i-(len(params)-len(defaults))
            if type(params[i]) == _StringType:
                vars.append(Var(params[i]))
                if defaultindex >= 0:
                    vars[-1].set_default(`defaults[defaultindex]`)
            elif defaultindex >= 0:
                vars.extend(self._params_to_vars(params[i],
                                                 defaults[defaultindex]))
            else:
                vars.extend(self._params_to_vars(params[i], []))
        return vars
    
    def __init__(self, func):
        # Initilize the module from its docstring.
        self._tmp_param = {}
        self._tmp_type = {}
        self._raises = []
        ObjDoc.__init__(self, func)

        # If we're a method, extract the underlying function.
        cls = None
        if type(func) in (_MethodType, _BuiltinMethodType):
            cls = func.im_class
            func = func.im_func

        # Get the function's signature
        (args, vararg, kwarg, defaults) = inspect.getargspec(func)

        # Construct argument/return Variables.
        self._params = self._params_to_vars(args, defaults)
        if vararg: self._vararg_param = Var(vararg)
        else: self._vararg_param = None
        if kwarg: self._kwarg_param = Var(kwarg)
        else: self._kwarg_param = None
        self._return = Var('return')

        # Add descriptions/types to argument/return Variables.
        vars = self._params[:]
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
            print 'Descr for unknown vars:',
            print self._tmp_param.keys(),
            print 'in', `self._uid`
            #raise SyntaxError('Descr for unknown parameter')
        if self._tmp_type != {}:
            print 'Type for unknown vars:',
            print self._tmp_type.keys(),
            print 'in', `self._uid`
            #raise SyntaxError('Type for unknown parameter')
        del self._tmp_param
        del self._tmp_type

        # If we're a method, figure out what we override.
        self._overrides = None
        if cls: self._find_override(cls)

#         # If we got a return description, but no overview, create an
#         # overview based on the return description.
#         if (self._descr is None) and (self._return.descr() is not None):
#             self._descr = self._return.descr()
#             self._return.set_descr(None)
#             children = self._descr.childNodes
#             while (len(children) > 0):
#                 if children[0].tagName == 'para':
#                     para = children[0]
#                     if para.hasChildNodes():
#                         para.insertBefore(_Text('Return '),
#                                           para.childNodes[0])
#                     else:
#                         para.appendChild(_Text('Return '))
#                     break
#                 if children[0].tagName in ('epytext', 'section',
#                                            'ulist', 'olist'):
#                     children = children[0].childNodes
#                 else:
#                     children = children[1:]

    def _find_override(self, cls):
        name = self.uid().shortname()
        for base in cls.__bases__:
            if base.__dict__.has_key(name):
                func = base.__dict__[name]
                if type(func) == _FunctionType:
                    method = new.instancemethod(func, None, base)
                    self._overrides = UID(method)
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
                warnings.append('Redefinition of parameter')
            self._tmp_param[arg] = descr
        elif tag == 'type':
            if arg == None:
                warnings.append(tag+' expected an argument')
                arg = ''
            if self._tmp_type.has_key(arg):
                warnings.append('Redefinition of variable '+\
                                  'type: '+arg+' ('+descr+')')
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

    def parameters(self): return self._params
    def vararg(self): return self._vararg_param
    def kwarg(self): return self._kwarg_param
    def returns(self): return self._return
    def raises(self): return self._raises
    def overrides(self): return self._overrides

#class MethodDoc(FuncDoc):
#    def __init__(self, method):
#        FuncDoc.__init__(self, method)
#    def __repr__(self):
#        FuncDoc.__repr__(self)
#    def parameters(self): FuncDoc.parameters(self)
#    def vararg(self): FuncDoc.vararg(self)
#    def kwarg(self): FuncDoc.kwarg(self)
#    def returns(self): FuncDoc.returns(self)
#    def raises(self): FuncDoc.raises(self)
    
##################################################
## Documentation Management
##################################################

import UserDict
class Documentation(UserDict.UserDict):
    def __init__(self):
        self.data = {} # UID -> ObjDoc
        self._class_children = {} # UID -> list of UID
        self._package_children = {} # UID -> list of UID

    def inherit(): pass

    def add_one(self, obj):
        objID = UID(obj)
            
        #print 'Constructing docs for:', objID
        if self.data.has_key(objID): return
        
        if type(obj) == _ModuleType:
            self.data[objID] = ModuleDoc(obj)
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
            
        elif type(obj) == _ClassType:
            self.data[objID] = ClassDoc(obj)
            for child in self._class_children.get(objID, []):
                self.data[objID].add_child(child)
                #child.inherit(self.data[objID])
            for base in obj.__bases__:
                baseID=UID(base)
                if self.data.has_key(baseID):
                    self.data[baseID].add_child(obj)
                    #self.data[objID].inherit(self.data[baseID])
                if self._class_children.has_key(baseID):
                    self._class_children[baseID].append(obj)
                else:
                    self._class_children[baseID] = [obj]
                    
        elif type(obj) in (_MethodType, _FunctionType):
            self.data[objID] = FuncDoc(obj)

    def add(self, obj):
        objID = UID(obj)
        if self.data.has_key(objID): return

        # Add ourselves.
        self.add_one(obj)

        # Recurse to any related objects.
        if type(obj) == _ModuleType:
            for val in obj.__dict__.values():

                # Skip any imported values.
                if type(val) in (_FunctionType, _ClassType):
                    if UID(val).module() != objID:
                        if WARN_SKIPPING:
                            print 'Skipping imported value', val
                        continue

                if type(val) == _ClassType:
                    self.add(val)
                elif type(val) in (_FunctionType, _BuiltinFunctionType):
                    self.add(val)
        elif type(obj) == _ClassType:
            for val in obj.__dict__.values():
                if type(val) is _FunctionType:
                    self.add(new.instancemethod(val, None, obj))
                elif type(val) is _BuiltinMethodType:
                    self.add(val)

    def __getitem__(self, key):
        if isinstance(key, UID):
            return self.data[key]
        else:
            return self.data[UID(key)]

    def __repr__(self):
        return '<Documentation: '+`len(self.data)`+' objects>'

##################################################
## Utility functions for conversion
##################################################

def _is_private(str):
    str = string.split(str, '.')[-1]
    return (str and str[0]=='_' and str[-1]!='_')

def _cmp_name(uid1, uid2):
    """## Order by names.
    __init__ < anything.
    public < private.
    otherwise, sorted alphabetically by name.
    """
    x = uid1.name()
    y = uid2.name()
    if (y == '__init__'): return 1
    if (x == '__init__'): return -1
    if x == y: return 0
    if _is_private(x) and not _is_private(y): return 1
    if _is_private(y) and not _is_private(x): return -1
    return cmp(x, y)

##################################################
## Documentation Completeness Checking
##################################################

class DocChecker:
    # Types
    MODULE = 1
    CLASS  = 2
    FUNC   = 4
    VAR    = 8
    IVAR   = 16
    CVAR   = 32
    PARAM  = 64
    RETURN = 128
    ALL_T  = 1+2+4+8+16+32+64+128

    # Checks
    TYPE = 256
    SEE = 512
    AUTHOR = 1024
    VERSION = 2048
    DESCR_LAZY = 4096
    DESCR_STRICT = 8192
    DESCR = DESCR_LAZY + DESCR_STRICT
    ALL_C = 256+512+1024+2048+4096+8192

    ALL = ALL_T + ALL_C

    def __init__(self, docmap):
        docs = []
        self._docs = docmap.values()
        self._docmap = docmap
        """
        self._docmap = docmap
        for (uid, doc) in docmap.items():
            if isinstance(doc, ModuleDoc) or isinstance(doc, ClassDoc):
                docs.append(uid)
        self._docs = []
        self._add(docs)
        """
        f = lambda d1,d2:cmp(`d1.uid()`, `d2.uid()`)
        self._docs.sort(f)
        self._checks = 0

    def check(self, checks = None):
        if checks == None:
            self.check(DocChecker.MODULE | DocChecker.CLASS |
                       DocChecker.FUNC | DocChecker.DESCR_LAZY)
            self.check(DocChecker.PARAM | DocChecker.VAR |
                       DocChecker.IVAR | DocChecker.CVAR |
                       DocChecker.RETURN | DocChecker.DESCR |
                       DocChecker.TYPE)
            return

        self._checks = checks
        for doc in self._docs:
            if isinstance(doc, ModuleDoc):
                self._check_module(doc)
            elif isinstance(doc, ClassDoc):
                self._check_class(doc)
            elif isinstance(doc, FuncDoc):
                self._check_func(doc)
            else:
                raise AssertionError(doc)

    def _check_basic(self, doc):
        if (self._checks & DocChecker.DESCR) and (not doc.descr()):
            if ((self._checks & DocChecker.DESCR_STRICT) or
                (not isinstance(doc, FuncDoc)) or
                (not doc.returns().descr())):
                print 'Warning -- No descr    ', doc.uid()
        if (self._checks & DocChecker.SEE):
            for (elt, descr) in doc.seealsos():
                if not self._docmap.has_key(elt):
                    print 'Warning -- Broken see-also ', doc.uid(), elt
        if (self._checks & DocChecker.AUTHOR) and (not doc.authors()):
            print 'Warning -- No authors  ', doc.uid()
        if (self._checks & DocChecker.VERSION) and (not doc.version()):
            print 'Warning -- No version  ', doc.uid()
            
    def _check_module(self, doc):
        if self._checks & DocChecker.MODULE:
            self._check_basic(doc)
        if self._checks & DocChecker.VAR:
            for v in doc.variables():
                self._check_var(v, `doc.uid()`)
        
    def _check_class(self, doc):
        if self._checks & DocChecker.CLASS:
            self._check_basic(doc)
        if self._checks & DocChecker.IVAR:
            for v in doc.ivariables():
                self._check_var(v, `doc.uid()`)
        if self._checks & DocChecker.CVAR:
            for v in doc.cvariables():
                self._check_var(v, `doc.uid()`)

    def _check_var(self, var, name):
        if var == None: return
        if (self._checks & DocChecker.DESCR) and (not var.descr()):
            print 'Warning -- No descr    ', name+'.'+var.name()
        if (self._checks & DocChecker.TYPE) and (not var.type()):
            print 'Warning -- No type     ', name+'.'+var.name()
            
    def _documented_ancestor(self, doc):
        if isinstance(doc, FuncDoc):
            while (not doc.documented() and
                   doc.overrides() and
                   self._docmap.has_key(doc.overrides())):
                doc = self._docmap[doc.overrides()]
        return doc
            
    def _check_func(self, doc):
        doc = self._documented_ancestor(doc)
        if self._checks & DocChecker.FUNC:
            if ((`doc.uid()`.split('.'))[-1] not in
                ('__hash__',)):
                self._check_basic(doc)
        if (self._checks & DocChecker.RETURN):
            if ((`doc.uid()`.split('.'))[-1] not in
                ('__init__', '__hash__')):
                self._check_var(doc.returns(), `doc.uid()`)
        if (self._checks & DocChecker.PARAM):
            if doc.uid().is_method():
                for v in doc.parameters()[1:]:
                    self._check_var(v, `doc.uid()`)
            else:
                for v in doc.parameters():
                    self._check_var(v, `doc.uid()`)
            self._check_var(doc.vararg(), `doc.uid()`)
            self._check_var(doc.kwarg(), `doc.uid()`)

##################################################
## Documentation -> HTML Conversion
##################################################

class HTML_Doc:
    """
    Documentation=>HTML converter.

    @cvar _SPECIAL_METHODS: A dictionary providing names for special
        methods, such as C{__init__} and C{__add__}.
    @type _SPECIAL_METHODS: C{dictionary} from C{string} to C{string}
    """
    
    def __init__(self, docmap, pkg_name='', show_private=1):
        """
        Construct a new HTML outputter, using the given
        C{Documentation} object.
        
        @param docmap: The documentationw to output.
        @type docmap: Documentation
        @param pkg_name: The name of the package.  This is used in the 
            header.
        @type pkg_name: C{string}
        @param show_private: Whether to show private fields (fields
            starting with a single '_').
        @type show_private: boolean
        """
        self._docmap = docmap
        self._show_private = show_private
        self._pkg_name = pkg_name

        # Try to find a unique module/package for this set of docs.
        # This is used by the navbar.
        self._module = None
        self._package = None
        for (uid, doc) in self._docmap.items():
            if not isinstance(doc, ModuleDoc): continue
            if self._module is None: self._module = uid
            else: self._module = "multiple"
            if doc.ispackage():
                if self._package is None: self._package = uid
                else: self._package = "multiple"

    def write(self, directory, verbose=1):
        """## Write the documentation to the given directory."""
        if directory in ('', None): directory = './'
        if directory[-1] != '/': directory = directory + '/'

        str = self._tree_to_html()
        open(directory+'tree.html', 'w').write(str)

        str = self._index_to_html()
        open(directory+'term_index.html', 'w').write(str)
    
        for (n, d) in self._docmap.items():
            if isinstance(d, ModuleDoc):
                if verbose==1:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                elif verbose>1: print 'Writing docs for module: ', n
                str = self._module_to_html(n)
                open(directory+`n`+'.html', 'w').write(str)
            elif isinstance(d, ClassDoc):
                if verbose==1:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                elif verbose>1: print 'Writing docs for class:  ', n
                str = self._class_to_html(n)
                open(directory+`n`+'.html', 'w').write(str)
        
    ##--------------------------
    ## INTERNALS
    ##--------------------------

    _SPECIAL_METHODS = {'__init__': 'Constructor',
                        '__del__': 'Destructor',
                        '__add__': 'Addition operator',
                        '__sub__': 'Subtraction operator',
                        '__and__': 'And operator',
                        '__or__': 'Or operator',
                        '__repr__': 'Representation operator',
                        '__call__': 'Call operator',
                        '__getattr__': 'Qualification operator',
                        '__getitem__': 'Indexing operator',
                        '__setitem__': 'Index assignment operator',
                        '__delitem__': 'Index deletion operator',
                        '__delslice__': 'Slice deletion operator',
                        '__setslice__': 'Slice assignment operator',
                        '__getslice__': 'Slicling operator',
                        '__len__': 'Length operator',
                        '__cmp__': 'Comparison operator',
                        '__eq__': 'Equality operator',
                        '__in__': 'Containership operator',
                        '__gt__': 'Greater-than operator',
                        '__lt__': 'Less-than operator',
                        '__ge__': 'Greater-than-or-equals operator',
                        '__le__': 'Less-than-or-equals operator',
                        '__radd__': 'Right-side addition operator',
                        '__hash__': 'Hashing function',
                        '__contains__': 'In operator',
                        '__str__': 'Informal representation operator'
                        }

    def _sort(self, docs):
        """
        Sort a list of C{ObjDoc}s.
        """
        docs = list(docs)
        docs.sort(lambda x,y: _cmp_name(x, y))
        if not self._show_private:
            docs = filter(lambda x:not _is_private(x.name()), docs)
        return docs

    def _header(self, name):
        'Return an HTML header with the given name.'
        if isinstance(name, UID):
            print 'Warning: use name, not uid'
            name = name.name()
        return '<HTML>\n<HEAD>\n<TITLE>' + name + \
               "</TITLE>\n</HEAD>\n<BODY bgcolor='white' "+\
               "text='black' link='blue' "+\
               "vlink='#204080' alink='#204080'>"
               
    def _footer(self):
        'Return an HTML footer'
        import time
        date = time.asctime(time.localtime(time.time()))
        return '<FONT SIZE=-2>'+\
               'Generated by Epydoc on '+date+'.<BR>\n'+\
               'Epydoc is currently under development.  For '+\
               'information on the status of Epydoc, contact '+\
               '<A HREF="mailto:ed@loper.org">ed@loper.org</A>.'+\
               '</FONT>\n\n</BODY>\n</HTML>\n'
    
    def _seealso(self, seealso):
        'Convert a SEEALSO node to HTML'
        #!!!!!!!!!!!!!!!!!!!!!!!!!!!! NO SEEALSO YET
        return ''
        if not seealso: return ''
        str = '<DL><DT><B>See also:</B>\n  <DD>'
        for see in seealso:
            if self._docmap.has_key(see[0]):
                str += self._uid_to_href(see[0], see[1]) + ', '
            else:
                str += see[1] + ', '
        return str[:-2] + '</DD>\n</DT></DL>\n\n'

    def _summary(self, doc):
        'Convert an descr to an HTML summary'
        descr = doc.descr()

        # Try to find a documented ancestor.
        if isinstance(doc, FuncDoc):
            while (not doc.documented() and
                   doc.overrides() and
                   self._docmap.has_key(doc.overrides())):
                doc = self._docmap[doc.overrides()]

        if descr != None:
            str = epytext.to_html(epytext.summary(descr)).strip()
            if str == '': str = '&nbsp;'
            return str
        elif (isinstance(doc, FuncDoc) and
              doc.returns().descr() is not None):
            summary = epytext.summary(doc.returns().descr())
            return ('Return '+epytext.to_html(summary).strip())
        else:
            return '&nbsp;'

    def _href_target(self, uid):
        return `uid`+'.html'

    def _link_to_href(self, link):
        return self._uid_to_href(link.target(), link.name())
    #return ('<a href=' + self._href_target(link.target()) +
    #            '>' + link.name() + '</a>')

    def _uid_to_href(self, uid, label=None):
        'Add an HREF to a uid, when appropriate.'
        if label==None: label = `uid`
        if self._docmap.has_key(uid):
            str = ('<a href=' + self._href_target(uid) +
                   '>' + label + '</a>')
            if not isinstance(self._docmap[uid], ModuleDoc):
                str = '<CODE>'+str+'</CODE>'
        else:
            str = label
        return str

    def _descr(self, descr):
        ## PHASE THIS OUT EVENTUALLY???
        'Convert a description Node to HTML'
        if descr == None: return ''
        str = epytext.to_html(descr)
        open = '<B><I><CENTER><FONT SIZE='
        close = '</FONT></CENTER></I></B>'
        str = re.sub('<H1>', open+'"+2">', str)
        str = re.sub('<H2>', open+'"+1">', str)
        str = re.sub('<H3>', open+'"+0">', str)
        str = re.sub('</H\d>', close, str)
        return str

    #def _descr(self, descr):
    #    return re.sub('</?P>', '', self._descr(descr))
    
    def _heading(self, doc, descr):
        'Return a heading for the given Class or Module'
        uid = doc.uid()
        shortname = uid.name()
        if isinstance(doc, ClassDoc):
            modname = doc.module().name()
            str = '<H2><FONT SIZE="-1">\n'+modname+'</FONT></BR>\n' + \
                  'Class ' + shortname+'</H2>\n\n'
            if doc.bases:
                str += '<PRE>\n' + self._base_tree(uid) + \
                      '</PRE><p>\n\n'
            children = doc.children()
            if children:
                str += '<DL><DT><B>Known Subclasses:</B>\n<DD>'
                for cls in children:
                    str += '    '+self._link_to_href(cls) + ',\n'
                str = str[:-2] + '</DD></DT></DL>\n\n'
            if descr:
                str += '<HR>\n' + self._descr(descr) +\
                      '\n\n'
            return str + '<HR>\n\n'
        elif isinstance(doc, ModuleDoc): pass
        else: raise AssertionError('Unexpected arg to _heading')

    def _find_tree_width(self, uid):
        width = 2
        if self._docmap.has_key(uid):
            for base in self._docmap[uid].bases():
                width = max(width, len(base.name())+4)
                width = max(width, self._find_tree_width(base.target())+4)

        return width
        
    def _base_tree(self, uid, width=None, postfix=''):
        """
        Return an HTML picture showing a class's base tree,
        with multiple inheritance.

        Draw a right-justified picture..
        """
        if not self._docmap.has_key(uid): return ''
        if width == None:
            width = self._find_tree_width(uid)
        
        bases = self._docmap[uid].bases()
        
        if postfix == '':
            str = ' '*(width-2) + '<B>'+`uid`+'</B>\n'
        else: str = ''
        for i in range(len(bases)-1, -1, -1):
            base = bases[i]
            str = (' '*(width-4-len(base.name())) +
                   self._link_to_href(base)+' --+'+postfix+'\n' + 
                   ' '*(width-4) +
                   '   |'+postfix+'\n' +
                   str)
            (t,w) = (base.target(), width)
            if i < len(bases)-1:
                str = (self._base_tree(t, w-4, '   |'+postfix)+str)
            else:
                str = (self._base_tree(t, w-4, '    '+postfix)+str)
        return str
                
    def _base_tree_old(self, uid, prefix='  '):
        """
        Return an HTML picture showing a class's base tree,
        with multiple inheritance.
        """
        if not self._docmap.has_key(uid): return ''
        
        bases = self._docmap[uid].bases()
        if prefix == '  ': str = '  +-- <B>'+`uid`+'</B>\n'
        else: str = ''
        for i in range(len(bases)):
            base = bases[i]
            str = (prefix + '+--' + self._link_to_href(base) + '\n' +
                   prefix + '|  \n' + str)
            if i < (len(bases)-1):
                str = self._base_tree_old(base.target(), prefix+'|  ') + str
            else:
                str = self._base_tree_old(base.target(), prefix+'   ') + str
        return str

    def _class_tree_item(self, uid=None, depth=0):
        if uid is not None:
            doc = self._docmap.get(uid, None)
            str = ' '*depth + '<LI> <B>' + self._uid_to_href(uid)+'</B>'
            if doc and doc.descr():
                str += ': <I>' + self._summary(doc) + '</I>'
            str += '\n'
            if doc and doc.children():
                str += ' '*depth + '  <UL>\n'
                children = [l.target() for l in doc.children()]
                children.sort()
                for child in children:
                    str += self._class_tree_item(child, depth+4)
                str += ' '*depth + '  </UL>\n'
        return str

    def _class_tree(self):
        str = '<UL>\n'
        docs = self._docmap.items()
        docs.sort()
        for (uid, doc) in docs:
            if not isinstance(doc, ClassDoc): continue
            hasbase = 0
            for base in doc.bases():
                if self._docmap.has_key(base.target()):
                    hasbase = 1
            if not hasbase:
                str += self._class_tree_item(uid)
        return str +'</UL>\n'

    def _module_tree_item(self, uid=None, depth=0):
        if uid is not None:
            doc = self._docmap.get(uid, None)
            name = `uid`.split('.')[-1]
            str = ' '*depth + '<LI> <B>'
            str += self._uid_to_href(uid, name)+'</B>'
            if doc and doc.descr():
                str += ': <I>' + self._summary(doc) + '</I>'
            str += '\n'
            if doc and doc.ispackage() and doc.modules():
                str += ' '*depth + '  <UL>\n'
                modules = [l.target() for l in doc.modules()]
                modules.sort()
                for module in modules:
                    str += self._module_tree_item(module, depth+4)
                str += ' '*depth + '  </UL>\n'
        return str

    def _module_tree(self):
        str = '<UL>\n'
        docs = self._docmap.items()
        docs.sort()
        for (uid, doc) in docs:
            if not isinstance(doc, ModuleDoc): continue
            if not doc.package():
                str += self._module_tree_item(uid)
        return str +'</UL>\n'

    def _start_of(self, heading):
        return '\n<!-- =========== START OF '+string.upper(heading)+\
               ' =========== -->\n'
    
    def _table_header(self, heading):
        'Return a header for an HTML table'
        return self._start_of(heading)+\
               '<TABLE BORDER="1" CELLPADDING="3" ' +\
               'CELLSPACING="0" WIDTH="100%" BGCOLOR="white">\n' +\
               '<TR BGCOLOR="#70b0f0">\n'+\
               '<TD COLSPAN=2><FONT SIZE="+2">\n<B>' + heading + \
               '</B></FONT></TD></TR>\n'
    
    def _class_summary(self, classes, heading='Class Summary'):
        'Return a summary of the classes in a module'
        classes = self._sort(classes)
        if len(classes) == 0: return ''
        str = self._table_header(heading)

        for link in classes:
            cname = link.name()
            cls = link.target()
            if not self._docmap.has_key(cls): continue
            cdoc = self._docmap[cls]
            csum = self._summary(cdoc)
            str += '<TR><TD WIDTH="15%">\n'+\
                  '  <B><I>'+self._link_to_href(link)+\
                  '</I></B></TD>\n  <TD>' + csum + '</TD></TR>\n'
        return str + '</TABLE><p>\n\n'

    def _func_details(self, functions, cls,
                      heading='Function Details'):
        """## Return a detailed description of the functions in a
        class or module."""
        functions = self._sort(functions)
        if len(functions) == 0: return ''
        str = self._table_header(heading)+'</TABLE>'

        for link in functions:
            fname = link.name()
            func = link.target()
            if not self._docmap.has_key(func):
                if WARN_MISSING:
                    print 'WARNING: MISSING', func
                continue
            
            fdoc = self._docmap[func]

            rval = fdoc.returns()
            if rval.type():
                rtype = epytext.to_html(rval.type())
            else: rtype = '&nbsp;'
            
            pstr = '('
            for param in fdoc.parameters():
                pstr += param.name()
                if param.default():
                    default = param.default()
                    if len(default) > 60:
                        default = default[:57]+'...'
                    pstr += '='+default
                pstr += ', '
            if fdoc.vararg():
                pstr += '*'+fdoc.vararg().name()+', '
            if fdoc.kwarg():
                pstr += '**'+fdoc.kwarg().name()+', '
            if pstr == '(': pstr = '()'
            else: pstr = pstr[:-2]+')'
            
            str += '<A NAME="'+fname+'">\n'
            if HTML_Doc._SPECIAL_METHODS.has_key(fname):
                str += '<H3><I>'+\
                      HTML_Doc._SPECIAL_METHODS[fname]+'</I></H3>\n'
            else:
                str += '<H3>'+fname+'</H3>\n'
            str += '<CODE><B>' +fname + pstr + '</B></CODE><p>\n'
            str += '<DL>\n'

            foverrides = fdoc.overrides()

            # Try to find a documented ancestor.
            inheritdoc = 0
            while (not fdoc.documented() and
                   fdoc.overrides() and
                   self._docmap.has_key(fdoc.overrides())):
                fdoc = self._docmap[fdoc.overrides()]
                inheritdoc = 1
                
            fdescr=fdoc.descr()
            fparam = fdoc.parameters()[:]
            if fdoc.vararg(): fparam.append(fdoc.vararg())
            if fdoc.kwarg(): fparam.append(fdoc.kwarg())
            freturn = fdoc.returns()
            fraises = fdoc.raises()
            
            # Don't list parameters that don't have any extra info.
            f = lambda p:p.descr() or p.type()
            fparam = filter(f, fparam)

            # Description
            if fdescr:
                str += '  <DT><DD>'+epytext.to_html(fdescr)+'</DD></DT>\n'
                str += '  <P></P>\n'
            str += '  <DT><DD>\n'

            # Parameters
            if fparam:
                str += '    <DL><DT><B>Parameters:</B>\n'
                for param in fparam:
                    pname = param.name()
                    str += '      <DD><CODE><B>' + pname +'</B></CODE>'
                    if param.descr():
                        str += ' - ' + epytext.to_html(param.descr())
                    if param.type():
                        str += ' </BR>\n        <I>'+('&nbsp;'*10)+\
                              '(type=' + \
                              epytext.to_html(param.type()) +\
                              ')</I>'
                    str += '</DD>\n'
                str += '    </DT></DL>\n'

            # Returns
            if freturn.descr() or freturn.type():
                str += '    <DL><DT><B>Returns:</B>\n      <DD>'
                if freturn.descr():
                    str += epytext.to_html(freturn.descr())
                    if freturn.type():
                        str += ' </BR>' + '<I>'+('&nbsp;'*10)+\
                              '(type=' + \
                              epytext.to_html(freturn.type()) +\
                              ')</I>'
                elif freturn.type():
                    str += epytext.to_html(freturn.type())
                str += '</DD>\n    </DT></DL>\n'

            # Raises
            if fraises:
                str += '    <DL><DT><B>Raises:</B>\n'
                for fraise in fraises:
                    str += '      '
                    str += '<DD><CODE><B>'+fraise.name()+'</B></CODE> - '
                    str += epytext.to_html(fraise.descr())+'</DD>\n'
                str += '    </DT></DL>\n'

            # Overrides
            if foverrides:
                cls = foverrides.cls()
                str += '    <DL><DT><B>Overrides:</B>\n'
                if self._docmap.has_key(cls):
                    str += ('      <DD><CODE><a href=' +
                            self._href_target(cls) + '#' +
                            foverrides.shortname() +
                            '>' + `foverrides` + '</a></CODE>')
                else:
                    str += '      <DD><CODE>'+`func`+'</CODE>'
                if inheritdoc:
                    str += ' <I>(inherited documentation)</I>\n'
                str += '</DD>\n    </DT></DL>\n'
                
            str += '  </DD>\n</DT></DL><hr>\n\n'
        return str

    def _var_details(self, variables, heading='Variable Details'):
        """## Return a detailed description of the variables in a
        class or module."""
        variables = self._sort(variables)
        if len(variables) == 0: return ''
        str = self._table_header(heading)+'</TABLE>'

        numvars = 0
        for var in variables:
            # Don't bother if we don't know anything about it.
            if not (var.descr() or var.type()): continue
            numvars += 1
            
            vname = var.name()

            str += '<A NAME="'+vname+'">\n'
            str += '<H3>'+vname+'</H3>\n'
            str += '<DL>\n'

            if var.descr():
                str += '  <DD>'+\
                      epytext.to_html(var.descr())+'<p>\n'
                
            if var.type():
                str += '  <DL><DT><B>Type:</B>\n' +\
                      '<CODE>'+epytext.to_html(var.type())+\
                      '</CODE>'+'</DL>\n'
                      

            #if var.overrides():
            #    str += '  <DL><DT><B>Overrides:</B>\n'
            #    for target in var.overrides():
            #        str += '    <DD>' + \
                  #        self._link_to_href(target.data[0]) + '\n'
            #    str += '  </DL>\n'
            
            str += '</DL><hr>\n'

        # If we didn't get any variables, don't print anything.
        if numvars == 0: return ''
        return str

    def _func_summary(self, functions, heading='Function Summary'):
        'Return a summary of the functions in a class or module'
        functions = self._sort(functions)
        if len(functions) == 0: return ''
        str = self._table_header(heading)
        
        for link in functions:
            func = link.target()
            fname = link.name()
            if not self._docmap.has_key(func):
                if WARN_MISSING:
                    print 'WARNING: MISSING', func
                continue
            
            fdoc = self._docmap[func]
            rval = fdoc.returns()
            if rval.type():
                rtype = epytext.to_html(rval.type())
            else: rtype = '&nbsp;'

            pstr = '('
            for param in fdoc.parameters():
                pstr += param.name()+', '
            if fdoc.vararg():
                pstr += '*'+fdoc.vararg().name()+', '
            if fdoc.kwarg():
                pstr += '**'+fdoc.kwarg().name()+', '
            if pstr == '(': pstr = '()'
            else: pstr = pstr[:-2]+')'

            descrstr = self._summary(fdoc)
            if descrstr != '&nbsp;':
                fsum = '</BR>'+descrstr
            else: fsum = ''
            str += '<TR><TD ALIGN="right" VALIGN="top" '+\
                  'WIDTH="15%"><FONT SIZE="-1">'+\
                  rtype+'</FONT></TD>\n'+\
                  '  <TD><CODE><B><A href="#'+fname+'">'+\
                  fname+'</A>'+\
                  '</B>'+pstr+'</CODE>\n  '+\
                  fsum+'</TD></TR>\n'
        return str + '</TABLE><p>\n\n'
    
    def _var_summary(self, variables, heading='Variable Summary'):
        'Return a summary of the variables in a class or module'
        variables = self._sort(variables)
        if len(variables) == 0: return ''
        str = self._table_header(heading)

        for var in variables:
            vname = var.name()
            if var.type(): vtype = epytext.to_html(var.type())
            else: vtype = '&nbsp;'
            if var.descr():
                vsum = '</BR>'+self._summary(var)
            else: vsum = ''
            str += '<TR><TD ALIGN="right" VALIGN="top" '+\
                  'WIDTH="15%"><FONT SIZE="-1">'+vtype+'</TD>\n'+\
                  '  <TD><CODE><B><A href="#'+vname+'">'+vname+\
                  '</A>'+'</B></CODE>\n  ' + vsum+'</TD></TR>\n'
        return str + '</TABLE><p>\n\n'

    def _module_list(self, modules):
        if len(modules) == 0: return ''
        str = '<H3>Modules</H3>\n<UL>\n'
        for link in modules:
            str += self._module_tree_item(link.target())
            #str += '  <LI><A HREF="'+`link.target()`+'.html">'
            #str += link.name() + '</A>\n'
        return str + '</UL>\n'

    def _navbar(self, where, uid=None):
        """
        @param where: What page the navbar is being displayed on..
        """
        str = self._start_of('Navbar') + \
              '<TABLE BORDER="0" WIDTH="100%" '+\
              'CELLPADDING="0" BGCOLOR="WHITE" CELLSPACING="0">\n'+\
              '<TR>\n<TD COLSPAN=2 BGCOLOR="#a0c0ff">\n'+\
              '<TABLE BORDER="0" CELLPADDING="0" CELLSPACING="1">\n'+\
              '  <TR ALIGN="center" VALIGN="top">\n'
        
        # Go to Package
        if self._package is None: pass
        elif where in ('class', 'module'):
            pkg = uid.package()
            if pkg is not None:
                str += '  <TD>&nbsp;&nbsp;&nbsp;<B><FONT SIZE="+1">'+\
                      '<A HREF="'+`pkg`+'.html">'+\
                      'Package</A>'+\
                      '</FONT></B>&nbsp;&nbsp;&nbsp;</TD>\n'
            else:
                str += '  <TD>&nbsp;&nbsp;&nbsp;'+\
                      '<B><FONT SIZE="+1">Package' +\
                      '</FONT></B>&nbsp;&nbsp;&nbsp;</TD>\n'
        elif where=='package':
            str += '  <TD BGCOLOR="#70b0f0">&nbsp;&nbsp;&nbsp;'+\
                  '<B><FONT SIZE="+1">Package' +\
                  '</FONT></B>&nbsp;&nbsp;&nbsp;</TD>\n'
        elif isinstance(self._package, UID):
            str += '  <TD>&nbsp;&nbsp;&nbsp;<B><FONT SIZE="+1">'+\
                   '<A HREF="'+`self._package`+'.html">'+\
                   'Package</A>'+\
                   '</FONT></B>&nbsp;&nbsp;&nbsp;</TD>\n'
        elif 'multiple' == self._package:
            str += '  <TD>&nbsp;&nbsp;&nbsp;'+\
                  '<B><FONT SIZE="+1">Package' +\
                  '</FONT></B>&nbsp;&nbsp;&nbsp;</TD></B>\n'
            
        
        # Go to Module
        if self._module is None: pass
        elif where=='class':
            str += '  <TD>&nbsp;&nbsp;&nbsp;<B><FONT SIZE="+1">'+\
                  '<A HREF="'+`uid.module()`+'.html">'+\
                  'Module</A>'+\
                  '</FONT></B>&nbsp;&nbsp;&nbsp;</TD>\n'
        elif where=='module':
            str += '  <TD BGCOLOR="#70b0f0">&nbsp;&nbsp;&nbsp;'+\
                  '<B><FONT SIZE="+1">Module' +\
                  '</FONT></B>&nbsp;&nbsp;&nbsp;</TD>\n'
        elif isinstance(self._module, UID):
            str += '  <TD>&nbsp;&nbsp;&nbsp;<B><FONT SIZE="+1">'+\
                  '<A HREF="'+`self._module`+'.html">'+\
                  'Module</A>'+\
                  '</FONT></B>&nbsp;&nbsp;&nbsp;</TD>\n'
        elif 'multiple' == self._module:
            str += '  <TD>&nbsp;&nbsp;&nbsp;'+\
                  '<B><FONT SIZE="+1">Module' +\
                  '</FONT></B>&nbsp;&nbsp;&nbsp;</TD></B>\n'
        
        # Go to Class
        if where == 'class':
            str += '  <TD BGCOLOR="#70b0f0">&nbsp;&nbsp;&nbsp;'+\
                  '<B><FONT SIZE="+1">Class' +\
                  '</FONT></B>&nbsp;&nbsp;&nbsp;</TD>\n'
        else:
            str += '  <TD>&nbsp;&nbsp;&nbsp;<B><FONT SIZE="+1">Class' +\
                   '</FONT></B>&nbsp;&nbsp;&nbsp;</TD>\n'

        # Go to Tree
        if where == 'tree':
            str += '  <TD BGCOLOR="#70b0f0">&nbsp;&nbsp;&nbsp;'+\
                   '<B><FONT SIZE="+1">Trees'+\
                   '</FONT></B>&nbsp;&nbsp;&nbsp;</TD>\n'
        else:
            str += '  <TD>&nbsp;&nbsp;&nbsp;<B><FONT SIZE="+1">'+\
                   '<A HREF="tree.html">Trees</A>'+\
                   '</FONT></B>&nbsp;&nbsp;&nbsp;</TD>\n'

        # Go to Index
        if where == 'index':
            str += '  <TD BGCOLOR="#70b0f0">&nbsp;&nbsp;&nbsp;'+\
                   '<B><FONT SIZE="+1">Index'+\
                   '</FONT></B>&nbsp;&nbsp;&nbsp;</TD>\n'
        else:
            str += '  <TD>&nbsp;&nbsp;&nbsp;<B><FONT SIZE="+1">'+\
                   '<A HREF="term_index.html">Index</A>'+\
                   '</FONT></B>&nbsp;&nbsp;&nbsp;</TD>\n'

        # Go to Help
        str += '  <TD>&nbsp;&nbsp;&nbsp;<B><FONT SIZE="+1">'+\
               '<A HREF="help.html">Help</A>'+\
               '</FONT></B>&nbsp;&nbsp;&nbsp;</TD>\n'

        str += '  </TR>\n</TABLE>\n</TD>\n'
        str += '<TD ALIGN="right" VALIGN="top" ROWSPAN=3>'+\
               '<B>'+self._pkg_name+'</B>\n'+\
               '</TD>\n</TR>\n</TABLE>\n'
        return str

    def _module_to_html(self, uid):
        'Return an HTML page for a Module'
        doc = self._docmap[uid]
        descr = doc.descr()
        if uid.is_package(): moduletype = 'package'
        else: moduletype = 'module'
        
        str = self._header(`uid`)
        str += self._navbar(moduletype, uid)+'<HR>'

        if moduletype == 'package':
            str += self._start_of('Package Description')
            str += '<H2>Package '+uid.name()+'</H2>\n\n'
        else:
            str += self._start_of('Module Description')
            str += '<H2>Module '+uid.name()+'</H2>\n\n'

        if descr:
            str += self._descr(descr) + '<HR>\n'
        if doc.seealsos():
            str += self._seealso(doc.seealsos())

        if doc.ispackage():
            str += self._module_list(doc.modules())
        
        str += self._class_summary(doc.classes())
        str += self._func_summary(doc.functions())
        str += self._var_summary(doc.variables())

        str += self._func_details(doc.functions(), None)
        str += self._var_details(doc.variables())
        
        str += self._navbar(moduletype, uid)+'<HR>'
        return str + self._footer()

    def _class_to_html(self, uid):
        'Return an HTML page for a Class'
        doc = self._docmap[uid]
        modname = doc.uid().module().name()
        descr = doc.descr()
        
        # Name & summary
        str = self._header(`uid`)
        str += self._navbar('class', uid)+'<HR>'
        str += self._start_of('Class Description')
        
        str += '<H2><FONT SIZE="-1">\n'+modname+'</FONT></BR>\n' + \
               'Class ' + `uid`+'</H2>\n\n'
        if doc.bases():
            str += '<PRE>\n' + self._base_tree(uid) + \
                   '</PRE><p>\n\n'
        children = doc.children()
        if children:
            str += '<DL><DT><B>Known Subclasses:</B>\n<DD>'
            for cls in children:
                str += '    '+self._link_to_href(cls) + ',\n'
            str = str[:-2] + '</DD></DT></DL>\n\n'
        if descr:
            str += '<HR>\n' + self._descr(descr) +\
                   '\n\n'
        str += '<HR>\n\n'

        str += self._seealso(doc.seealsos())

        str += self._func_summary(doc.methods(),\
                                       'Method Summary')
        str += self._var_summary(doc.ivariables(),\
                                      'Instance Variable Summary')
        str += self._var_summary(doc.cvariables(),\
                                      'Class Variable Summary')
        
        str += self._func_details(doc.methods(), doc, \
                                       'Method Details')
        str += self._var_details(doc.ivariables(), \
                                      'Instance Variable Details')
        str += self._var_details(doc.cvariables(), \
                                      'Class Variable Details')
        
        str += self._navbar('class', uid)+'<HR>\n'
        return str + self._footer()

    def _tree_to_html(self):
        str = self._header('Class Hierarchy')
        str += self._navbar('tree') + '<HR>'
        str += self._start_of('Class Hierarchy')
        str += '<H2>Module Hierarchy</H2>\n'
        str += self._module_tree()
        str += '<H2>Class Hierarchy</H2>\n'
        str += self._class_tree()
        str += '<HR>\n' + self._navbar('tree') + '<HR>\n'
        str += self._footer()
        return str

    def get_index_items(self, tree, base, dict=None):
        if dict == None: dict = {}
    
        if isinstance(tree, _Text): return dict
        elif tree.tagName != 'index':
            for child in tree.childNodes:
                self.get_index_items(child, base, dict)
        else:
            children = [epytext.to_html(c) for c in tree.childNodes]
            key = ''.join(children).lower().strip()
            if dict.has_key(key):
                dict[key].append(base)
            else:
                dict[key] = [base]
        return dict

    def _extract_index(self):
        """
        @return: A dictionary mapping from terms to lists of source
            documents. 
        """
        index = {}
        for (uid, doc) in self._docmap.items():
            base = `uid`
            descr = doc.descr()
            if descr:
                self.get_index_items(descr, base, index)
        return index

    def _index_to_html(self):
        str = self._header('Index')
        str += self._navbar('index') + '<HR>\n'
        str += self._start_of('Index')

        str += self._table_header('Index')
        index = self._extract_index().items()
        index.sort()
        for (term, sources) in index:
            str += '  <TR><TD>'+term+'</TD>\n    <TD>'
            sources.sort()
            for source in sources:
                target = source+'.html#'+epytext.index_to_anchor(term)
                str += '<I><A href="' + target + '">'
                str += source + '</A></I>, '
            str = str[:-2] + '</TR></TD>\n'
        str += '</TABLE>\n'
        
        str += '<HR>\n' + self._navbar('index') + '<HR>\n'
        str += self._footer()
        return str

### TEST STUFF ###
#class A(pydoc.FuncDoc, pydoc.Node):
#    x=1
#class B(A):
#    y=1
#class C(pydoc.Node, A, B):
#    z=1
#    def __init__(self): z=2
    
def make_pydocs():
    print 'Building documentation...'
    import epydoc, epytext, foo, foo.bar
    reload(epydoc)
    reload(epytext)
    reload(foo.bar)
    reload(foo)
    d=Documentation()
    d.add(epytext)
    d.add(foo.bar)
    d.add(foo)
    d.add(epydoc)
    print 'Writing documentation...'
    htmld = HTML_Doc(d, "Epydoc")
    htmld.write('html')
    print

if __name__ == '__main__':
    make_pydocs()



