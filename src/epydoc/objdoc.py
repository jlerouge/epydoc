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
created and managed by the C{Documentation} class, which acts like a
dictionary from Python objects to C{ObjDoc}s.

Textual documentation entries (e.g., module descriptions, method
descriptions, variable types, see-also entries) are encoded as DOM
C{Elements}, using the DTD described in the C{epytext} module.

Each Python object is identified by a globally unique identifier,
implemented with the C{UID} class.  These identifiers are also used by
the C{Link} class to implement crossreferencing between C{ObjDoc}s.
"""

##################################################
## Constants
##################################################

WARN_SKIPPING = 0

##################################################
## Imports
##################################################

import inspect, UserDict, epytext, string, new
from xml.dom.minidom import Text as _Text
from types import ModuleType as _ModuleType
from types import ClassType as _ClassType
from types import FunctionType as _FunctionType
from types import BuiltinFunctionType as _BuiltinFunctionType
from types import BuiltinMethodType as _BuiltinMethodType
from types import MethodType as _MethodType
from types import StringType as _StringType

from epydoc.uid import UID, Link

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
    A base class for encoding the information about a Python object
    that is necessary to create its documentation.

    @ivar _uid: The object's unique identifier
    @type _uid: C{UID}
    
    @ivar _descr: The object's description, encoded as epytext.
    @type _descr: DOM C{Element}

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
        """
        @return: true if the object documented by this C{ObjDoc} has a
            docstring.
        @rtype: C{bool}
        """
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

#////////////////////////////////////////////////////////
#// ClassDoc
#////////////////////////////////////////////////////////
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

#////////////////////////////////////////////////////////
#// FuncDoc
#////////////////////////////////////////////////////////
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
