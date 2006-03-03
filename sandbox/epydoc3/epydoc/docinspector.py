# epydoc -- Inspection
#
# Copyright (C) 2005 Edward Loper
# Author: Edward Loper <edloper@loper.org>
# URL: <http://epydoc.sf.net>
#
# $Id$

"""
Extract API documentation about python objects by directly inspecting
their values.

L{DocInspector} is a processing class that examines Python objects via
inspection, and uses the information it finds to create L{APIDoc}
objects containing the API documentation for those objects.

C{DocInspector} can be subclassed to extend the set of object types
that it supports.
"""
__docformat__ = 'epytext en'

######################################################################
## Imports
######################################################################

import inspect, re, sys, os.path
# API documentation encoding:
from epydoc.apidoc import *
# Type comparisons:
from types import *
# Set datatype:
from sets import Set
# Error reporting:
from epydoc import log
# Helper functions:
from epydoc.util import is_package_dir, decode_with_backslashreplace

class DocInspector:
    """
    An API documentation extractor based on inspecting python values.
    C{DocInspector} examines Python objects via inspection, and uses
    the information it finds to create L{APIDoc} objects containing
    the API documentation for those objects.  The main interface to
    the C{DocInspector} class is the L{inspect} method, which takes a
    Python value, and returns an L{APIDoc} that describes it.

    Currently, C{DocInspector} can extract documentation information
    from the following object types:

      - modules
      - classes
      - functions
      - methods
      - class methods
      - static methods
      - builtin routines
      - properties

    Subclassing
    ===========
    C{DocInspector} can be subclassed, to extend the set of object
    types that it supports.  C{DocInspector} can be extended in
    several different ways:

      - A subclass can override one of the existing inspection methods
        to modify the behavior for a currently supported object type.

      - A subclass can add support for a new type by adding a new
        inspection method; and extending L{inspector_method()} to
        return that method for values of the new type.
    """
    def __init__(self):
        """
        Create a new C{DocInspector}.
        """
        self._valuedoc_cache = {}
        """A cache containing the API documentation for values that
        we've already seen.  This cache is implemented as a dictionary
        that maps a value's pyid to its L{ValueDoc}.

        Note that if we encounter a value but decide not to inspect it
        (because it's imported from another module), then
        C{_valuedoc_cache} will contain an entry for the value, but
        the value will not be listed in L{_inspected_values}."""

        self._inspected_values = {}
        """A record which values we've inspected, encoded as a
        dictionary from pyid to C{bool}."""

    #////////////////////////////////////////////////////////////
    # Inspection Entry Points
    #////////////////////////////////////////////////////////////

    def inspect(self, value=None, name=None, filename=None, context=None):
        """
        Generate the API documentation for a specified object by
        inspecting Python values, and return it as a L{ValueDoc}.  The
        object to generate documentation for may be specified using
        the C{value} parameter, the C{filename} parameter, I{or} the
        C{name} parameter.  (It is an error to specify more than one
        of these three parameters, or to not specify any of them.)

        @param value: The python object that should be documented.
        @param filename: The name of the file that contains the python
            source code for a package, module, or script.  If
            C{filename} is specified, then C{inspect} will return a
            C{ModuleDoc} describing its contents.
        @param name: The fully-qualified python dotted name of any
            value (including packages, modules, classes, and
            functions).  C{DocParser} will automatically figure out
            which module(s) it needs to import in order to find the
            documentation for the specified object.
        @param context: The API documentation for the class of module
            that contains C{value} (if available).
        """
        if value is None and name is not None and filename is None:
            value = get_value_from_name(DottedName(name))
        elif value is None and name is None and filename is not None:
            value = get_value_from_filename(filename, context)
        elif name is None and filename is None:
            # it's ok if value is None -- that's a value, after all.
            pass 
        else:
            raise ValueError("Expected exactly one of the following "
                             "arguments: value, name, filename")
        
        pyid = id(value)

        # If we've already inspected this value, then simply return
        # its ValueDoc from our cache.
        if pyid in self._inspected_values:
            return self._valuedoc_cache[pyid]

        # Get the ValueDoc for this value.  (Creating a new one if
        # necessary.)
        val_doc = self._get_valuedoc(value)

        # Inspect the value, and return the completed ValueDoc.
        self._inspected_values[pyid] = True
        inspector_method = self.inspector_method(value, context)
        inspector_method(value, val_doc)

        # Set canonical name, if it was given
        if val_doc.canonical_name == UNKNOWN and name is not None:
            val_doc.canonical_name = name

        # If we were given a filename, but didn't manage to get a
        # canonical name, then the module defined by the given file
        # must be shadowed by a variable in its parent package(s).
        # E.g., this happens with `curses.wrapper`.  Add a "'" to
        # the end of the name to distinguish it from the variable.
        if val_doc.canonical_name == UNKNOWN and filename is not None:
            shadowed_name = DottedName(value.__name__)
            log.warn("Module %s is shadowed by a variable with "
                     "the same name." % shadowed_name)
            val_doc.canonical_name = DottedName(str(shadowed_name)+"'")

        return val_doc

    def _get_valuedoc(self, value):
        """
        If a C{ValueDoc} for the given value exists in the valuedoc
        cache, then return it; otherwise, create a new C{ValueDoc},
        add it to the cache, and return it.  When possible, the new
        C{ValueDoc}'s C{pyval}, C{repr}, and C{canonical_name}
        attributes will be set appropriately.
        """
        pyid = id(value)
        val_doc = self._valuedoc_cache.get(pyid)
        if val_doc is None:
            val_doc = self._valuedoc_cache[pyid] = ValueDoc()
            val_doc.pyval = value
            try:
                val_doc.canonical_name = self.get_canonical_name(value)
            except ValueError:
                val_doc.canonical_name = UNKNOWN
            try:
                val_doc.repr = '%r' % value
                if isinstance(val_doc.repr, str):
                    val_doc.repr = decode_with_backslashreplace(val_doc.repr)
            except: pass
        return val_doc

    #////////////////////////////////////////////////////////////
    # Inspection Dispatch Table
    #////////////////////////////////////////////////////////////

    # This can be overriden by subclasses.
    def inspector_method(self, value, context):
        """
        @return: A routine that should be used to inspect the given
        value.  This routine should accept two parameters, a value and
        a L{ValueDoc}; and should udpate the C{ValueDoc} with API
        documentation information about the value.  Typically, the
        routine will modify the C{ValueDoc}'s class using the
        L{specialize_to()<APIDoc.specialize_to>} method.
        
        @param context: The API documentation for the class of module
            that contains C{value} (if available).  Currently, this is
            just used to decide whether a function object should be
            treated as an instance method or not.
        @rtype: C{routine}
        """
        if inspect.ismodule(value):
            return self.inspect_module
        
        elif inspect.isclass(value):
            return self.inspect_class
        
        elif isinstance(value, classmethod):
            return self.inspect_classmethod
        
        elif isinstance(value, staticmethod):
            return self.inspect_staticmethod
        
        elif inspect.isroutine(value):
            return self.inspect_routine
        
        elif isinstance(value, property):
            return self.inspect_property
        
        else:
            return self.inspect_value

    #////////////////////////////////////////////////////////////
    # Module Inspection
    #////////////////////////////////////////////////////////////

    #: A list of module variables that should not be included in a
    #: module's API documentation.
    UNDOCUMENTED_MODULE_VARS = (
        '__builtins__', '__doc__', '__all__', '__file__', '__path__',
        '__name__', '__extra_epydoc_fields__', '__docformat__')

    def inspect_module(self, module, module_doc):
        """
        Add API documentation information about the module C{module}
        to C{module_doc}.
        """
        module_doc.specialize_to(ModuleDoc)
        
        # Record the module's docstring & docformat.
        if hasattr(module, '__doc__'):
            module_doc.docstring = self.get_docstring(module)
        if hasattr(module, '__docformat__'):
            module_doc.docformat = unicode(module.__docformat__)
                                      
        # Record the module's __all__ attribute (public names).
        if hasattr(module, '__all__'):
            try:
                public_names = Set([str(name) for name in module.__all__])
                for name, var_doc in module_doc.variables.items():
                    if name in public_names:
                        var_doc.is_public = True
                        if not isinstance(var_doc, ModuleDoc):
                            var_doc.is_imported = False
                    else:
                        var_doc.is_public = False
            except: pass

        # Record the module's filename
        if hasattr(module, '__file__'):
            try: module_doc.filename = unicode(module.__file__)
            except: pass

        # If the module has a __path__, then it's (probably) a
        # package; so set is_package=True and record its __path__.
        if hasattr(module, '__path__'):
            module_doc.is_package = True
            try: module_doc.path = [unicode(p) for p in module.__path__]
            except: pass
        else:
            module_doc.is_package = False

        # Make sure we have a name for the package.
        dotted_name = module_doc.canonical_name
        if dotted_name is UNKNOWN:
            dotted_name = DottedName(module.__name__)
            
        # Record the module's parent package, if it has one.
        if len(dotted_name) > 1:
            package_name = str(dotted_name.container())
            package = sys.modules.get(package_name)
            if package is not None:
                module_doc.package = self.inspect(package)
        else:
            module_doc.package = None

        # Initialize the submodules property
        module_doc.submodules = []

        # Add the module to its parent package's submodules list.
        if module_doc.package not in (None, UNKNOWN):
            module_doc.package.submodules.append(module_doc)

        # Record the module's variables.
        module_doc.variables = {}
        for child_name in dir(module):
            if child_name in self.UNDOCUMENTED_MODULE_VARS: continue
            child = getattr(module, child_name)

            # Create a VariableDoc for the child, and inspect its
            # value if it's defined in this module.
            container = self.get_containing_module(child)
            if container != None and container == module_doc.canonical_name:
                # Local variable.
                child_val_doc = self.inspect(child, context=module_doc)
                child_var_doc = VariableDoc(name=child_name,
                                            value=child_val_doc,
                                            is_imported=False,
                                            container=module_doc)
            elif container is None or module_doc.canonical_name is UNKNOWN:
                # Possibly imported variable.
                child_val_doc = self.inspect(child, context=module_doc)
                child_var_doc = VariableDoc(name=child_name,
                                            value=child_val_doc,
                                            container=module_doc)
            else:
                # Imported variable.
                child_val_doc = self._get_valuedoc(child)
                child_var_doc = VariableDoc(name=child_name,
                                            value=child_val_doc,
                                            is_imported=True,
                                            container=module_doc)

            module_doc.variables[child_name] = child_var_doc

    #////////////////////////////////////////////////////////////
    # Class Inspection
    #////////////////////////////////////////////////////////////

    #: A list of class variables that should not be included in a
    #: class's API documentation.
    UNDOCUMENTED_CLASS_VARS = (
        '__doc__', '__module__', '__dict__', '__weakref__')

    def inspect_class(self, cls, class_doc):
        """
        Add API documentation information about the class C{cls}
        to C{class_doc}.
        """
        class_doc.specialize_to(ClassDoc)
        
        # Record the class's docstring.
        class_doc.docstring = self.get_docstring(cls)

        # Record the class's __all__ attribute (public names).
        if hasattr(cls, '__all__'):
            try:
                public_names = [str(name) for name in cls.__all__]
                class_doc.public_names = public_names
            except: pass

        # Start a list of subclasses.
        class_doc.subclasses = []

        # Record the class's base classes; and add the class to its
        # base class's subclass lists.
        if hasattr(cls, '__bases__'):
            class_doc.bases = []
            for base in cls.__bases__:
                basedoc = self.inspect(base)
                class_doc.bases.append(basedoc)
                basedoc.subclasses.append(class_doc)

        # Record the class's local variables.
        class_doc.variables = {}
        private_prefix = '_%s__' % cls.__name__
        if hasattr(cls, '__dict__'):
            for child_name, child in cls.__dict__.items():
                if child_name.startswith(private_prefix):
                    child_name = child_name[len(private_prefix)-2:]
                if child_name in self.UNDOCUMENTED_CLASS_VARS: continue
                #try: child = getattr(cls, child_name)
                #except: continue
                val_doc = self.inspect(child, context=class_doc)
                var_doc = VariableDoc(name=child_name, value=val_doc,
                                      container=class_doc)
                class_doc.variables[child_name] = var_doc

    #////////////////////////////////////////////////////////////
    # Routine Inspection
    #////////////////////////////////////////////////////////////

    def inspect_classmethod(self, cm, routinedoc):
        """Add API documentation information about the class method
        C{cm} to C{routinedoc} (specializing it to
        C{ClassMethodDoc})."""
        # Extract the underlying function from the class method.
        self.inspect_routine(cm.__get__(0).im_func, routinedoc)
        routinedoc.specialize_to(ClassMethodDoc)

    def inspect_staticmethod(self, sm, routinedoc):
        """Add API documentation information about the static method
        C{sm} to C{routinedoc} (specializing it to
        C{StaticMethodDoc})."""
        # Extract the underlying function from the static method.
        self.inspect_routine(sm.__get__(0), routinedoc)
        routinedoc.specialize_to(StaticMethodDoc)

    def inspect_routine(self, func, routinedoc):
        """Add API documentation information about the function
        C{func} to C{routinedoc} (specializing it to C{RoutineDoc})."""
        routinedoc.specialize_to(RoutineDoc)

        # Record the function's docstring.
        routinedoc.docstring = self.get_docstring(func)

        # If it's a (bound) instance method, then extract its func.
        if isinstance(func, MethodType):
            func = func.im_func
        
        # Record the function's signature.
        if isinstance(func, FunctionType):
            (args, vararg, kwarg, defaults) = inspect.getargspec(func)

            # Add the arguments.
            routinedoc.posargs = args
            routinedoc.vararg = vararg
            routinedoc.kwarg = kwarg

            # Set default values for positional arguments.
            routinedoc.posarg_defaults = [None]*len(args)
            if defaults is not None:
                offset = len(args)-len(defaults)
                for i in range(len(defaults)):
                    default_val = self.inspect(defaults[i])
                    routinedoc.posarg_defaults[i+offset] = default_val

        else:
            # [XX] I should probably use UNKNOWN here??
            routinedoc.posargs = ['...']
            routinedoc.posarg_defaults = [None]
            routinedoc.kwarg = None
            routinedoc.vararg = None

    def inspect_builtin(self, func, func_doc):
        """Add API documentation information about the builtin
        function C{func} to C{func_doc} (specializing it to
        C{RoutineDoc})."""
        func_doc.specialize_to(RoutineDoc)
        
        # Record the builtin's docstring.
        func_doc.docstring = self.get_docstring(func)

        # Use a generic signature; this will hopefully get overridden
        # by the docstring parser.
        # [XX] I should probably use UNKNOWN here??
        func_doc.posargs = ['...']
        func_doc.posarg_defaults = [None]
        func_doc.kwarg = None
        func_doc.vararg = None

    #////////////////////////////////////////////////////////////
    # Property Inspection
    #////////////////////////////////////////////////////////////

    def inspect_property(self, prop, prop_doc):
        """Add API documentation information about the property
        C{prop} to C{prop_doc} (specializing it to C{PropertyDoc})."""
        prop_doc.specialize_to(PropertyDoc)
        
        # Record the property's docstring.
        prop_doc.docstring = self.get_docstring(prop)

        # Record the property's access functions.
        prop_doc.fget = self.inspect(prop.fget)
        prop_doc.fset = self.inspect(prop.fset)
        prop_doc.fdel = self.inspect(prop.fdel)

    #////////////////////////////////////////////////////////////
    # Value Inspection
    #////////////////////////////////////////////////////////////

    def inspect_value(self, val, val_doc):
        # It's just a generic value; nothing else to do.
        pass

    #////////////////////////////////////////////////////////////
    # Helper functions
    #////////////////////////////////////////////////////////////

    def get_docstring(self, value):
        """
        Return the docstring for the given value; or C{None} if it
        does not have a docstring.
        @rtype: C{unicode}
        """
        docstring = getattr(value, '__doc__', None)
        if docstring is None:
            return None
        elif isinstance(docstring, unicode):
            return docstring
        elif isinstance(docstring, str):
            try: return unicode(docstring, 'ascii')
            except UnicodeDecodeError:
                if hasattr(value, '__name__'): name = value.__name__
                else: name = `value`
                log.warn("%s's docstring is not a unicode string, but it "
                         "contains non-ascii data -- treating it as "
                         "latin-1." % name)
                # Assume it's latin-1.
                return unicode(docstring, 'latin-1')
            return None
        else:
            if hasattr(value, '__name__'): name = value.__name__
            else: name = `value`
            log.warn("%s's docstring is not a string -- ignoring it." % name)
            return None

    def get_canonical_name(self, value):
        """
        @return: the canonical name for C{value}, or C{UNKNOWN} if no
        canonical name can be found.  Currently, C{get_canonical_name}
        can find canonical names for: modules; functions; non-nested
        classes; methods of non-nested classes; and some class methods
        of non-nested classes.
        
        @rtype: L{DottedName} or C{None}
        """
        if not hasattr(value, '__name__'): return UNKNOWN

        # Get the name via inspection.
        if isinstance(value, ModuleType):
            dotted_name = DottedName(value.__name__)
        elif isinstance(value, (ClassType, TypeType)):
            if value.__module__ == '__builtin__':
                dotted_name = DottedName(value.__name__)
            else:
                dotted_name = DottedName(value.__module__, value.__name__)
        elif (inspect.ismethod(value) and value.im_self is not None and
              value.im_class is ClassType and
              not value.__name__.startswith('<')): # class method.
            class_name = self.get_canonical_name(value.im_self)
            if class_name is None: return UNKNOWN
            dotted_name = DottedName(class_name, value.__name__)
        elif (inspect.ismethod(value) and
              not value.__name__.startswith('<')):
            class_name = self.get_canonical_name(value.im_class)
            if class_name is None: return UNKNOWN
            dotted_name = DottedName(class_name, value.__name__)
        elif (isinstance(value, FunctionType) and
              not value.__name__.startswith('<')):
            module_name = self._find_function_module(value)
            if module_name is None: return UNKNOWN
            dotted_name = DottedName(module_name, value.__name__)
        else:
            return UNKNOWN

        # Verify the name.  E.g., if it's a nested class, then we
        # won't be able to find it with the name we constructed.
        if len(dotted_name) == 1 and dotted_name[0] in __builtins__:
            return dotted_name
        named_value = sys.modules.get(dotted_name[0])
        if named_value is None: return UNKNOWN
        for identifier in dotted_name[1:]:
            try: named_value = getattr(named_value, identifier)
            except: return UNKNOWN
        if value is named_value:
            return dotted_name
        else:
            return UNKNOWN

    def get_containing_module(self, value):
        """
        Return the name of the module containing the given value, or
        C{None} if the module name can't be determined.
        @rtype: L{DottedName}
        """
        if inspect.ismodule(value):
            return DottedName(value.__name__)
        elif inspect.isclass(value):
            return DottedName(value.__module__)
        elif (inspect.ismethod(value) and value.im_self is not None and
              value.im_class is ClassType): # class method.
            return DottedName(value.im_self.__module__)
        elif inspect.ismethod(value):
            return DottedName(value.im_class.__module__)
        elif inspect.isfunction(value):
            return DottedName(self._find_function_module(value))
        else:
            return None

    def _find_function_module(self, func):
        """
        @return: The module that defines the given function.
        @rtype: C{module}
        @param func: The function whose module should be found.
        @type func: C{function}
        """
        if hasattr(func, '__module__'):
            return func.__module__
        try:
            module = inspect.getmodule(func)
            if module: return module.__name__
        except: pass
    
        # This fallback shouldn't usually be needed.  But it is needed in
        # a couple special cases (including using epydoc to document
        # itself).  In particular, if a module gets loaded twice, using
        # two different names for the same file, then this helps.
        for module in sys.modules.values():
            if (module.hasattr('__dict__') and
                func.func_globals is module.__dict__):
                return module.__name__
        return None





#////////////////////////////////////////////////////////////
# Import support
#////////////////////////////////////////////////////////////

def get_value_from_filename(filename, context=None):
    # Normalize the filename.
    filename = os.path.normpath(os.path.abspath(filename))

    # Divide the filename into a base directory and a name.  (For
    # packages, use the package's parent directory as the base, and
    # the directory name as its name).
    basedir = os.path.split(filename)[0]
    name = os.path.splitext(os.path.split(filename)[1])[0]
    if name == '__init__':
        basedir, name = os.path.split(basedir)
    name = DottedName(name)

    # If the context wasn't provided, then check if the file is in a
    # package directory.  If so, then update basedir & name to contain
    # the topmost package's directory and the fully qualified name for
    # this file.  (This update assume the default value of __path__
    # for the parent packages; if the parent packages override their
    # __path__s, then this can cause us not to find the value.)
    if context is None:
        while is_package_dir(basedir):
            basedir, pkg_name = os.path.split(basedir)
            name = DottedName(pkg_name, name)
            
    # If a parent package was specified, then find the directory of
    # the topmost package, and the fully qualified name for this file.
    if context is not None:
        # Combine the name.
        name = DottedName(context.canonical_name, name)
        # Find the directory of the base package.
        while context not in (None, UNKNOWN):
            pkg_dir = os.path.split(context.filename)[0]
            basedir = os.path.split(pkg_dir)[0]
            context = context.package

    # Import the module.  (basedir is the directory of the module's
    # topmost package, or its own directory if it's not in a package;
    # and name is the fully qualified dotted name for the module.)
    old_sys_path = sys.path[:]
    try:
        sys.path.insert(0, basedir)
        # This will make sure that we get the module itself, even
        # if it is shadowed by a variable.  (E.g., curses.wrapper):
        _import(str(name))
        if str(name) in sys.modules:
            return sys.modules[str(name)]
        else:
            # Use this as a fallback -- it *shouldn't* ever be needed.
            return get_value_from_name(name)
    finally:
        sys.path = old_sys_path

def get_value_from_name(name):
    """
    Given a name, return the corresponding value.
    """
    name = DottedName(name)

    # Import the module containing `name`.
    for i in range(len(name)):
        module = _import('.'.join(name[:i+1]))
        if (hasattr(module, name[i]) and
            not isinstance(getattr(module, name[i]), ModuleType)):
            break

    # Look up `name` in the module
    val = module
    for i, identifier in enumerate(name[1:]):
        try: val = getattr(val, identifier)
        except AttributeError:
            exc_msg = ('Could not import %s:\nNo variable named %s in %s' %
                       (name, identifier, '.'.join(name[:1+i])))
            raise ImportError(exc_msg)
    return val
            
def _import(name):
    """
    Run the given callable in a 'sandboxed' environment.
    Currently, this includes saving and restoring the contents of
    sys and __builtins__; and supressing stdin, stdout, and stderr.
    """
    # Note that we just do a shallow copy of sys.  In particular,
    # any changes made to sys.modules will be kept.  But we do
    # explicitly store sys.path.
    old_sys = sys.__dict__.copy()
    old_sys_path = sys.path[:]
    if type(__builtins__) == types.DictionaryType:
        old_builtins = __builtins__.copy()
    else:
        old_builtins = __builtins__.__dict__.copy()

    # Supress input and output.  (These get restored when we restore
    # sys to old_sys).  
    sys.stdin = sys.stdout = sys.stderr = _dev_null
    sys.__stdin__ = sys.__stdout__ = sys.__stderr__ = _dev_null

    # Remove any command-line arguments
    sys.argv = ['(imported)']

    try:
        try:
            return __import__(name)
        except KeyboardInterrupt:
            raise # don't capture keyboard interrupts!
        except Exception, e:
            estr = e.__class__.__name__
            if ('%s'%e): estr += ' -- %s' % e
            raise ImportError('Could not import %s:\n%s' % (name, estr))
        except SystemExit, e:
            estr = e.__class__.__name__
            if ('%s'%e): estr += ' (%s)' % e
            raise ImportError('Could not import %s:\n%s' % (name, estr))
        except:
            raise ImportError('Could not import %s' % name)
    finally:
        # Restore the important values that we saved.
        if type(__builtins__) == types.DictionaryType:
            __builtins__.clear()
            __builtins__.update(old_builtins)
        else:
            __builtins__.__dict__.clear()
            __builtins__.__dict__.update(old_builtins)
        sys.__dict__.clear()
        sys.__dict__.update(old_sys)
        sys.path = old_sys_path
        
def inspect_docstring_lineno(api_doc):
    """
    Try to determine the line number on which the given item's
    docstring begins.  Return the line number, or C{None} if the line
    number can't be determined.  The line number of the first line in
    the file is 1.
    """
    if api_doc.docstring_lineno is not UNKNOWN:
        return api_doc.docstring_lineno
    if isinstance(api_doc, ValueDoc) and api_doc.pyval != UNKNOWN:
        try:
            lines, lineno = inspect.findsource(api_doc.pyval)
            if not isinstance(api_doc, ModuleDoc): lineno += 1
            for lineno in range(lineno, len(lines)):
                if lines[lineno].split('#', 1)[0].strip():
                    api_doc.docstring_lineno = lineno + 1
                    return lineno + 1
        except IOError: pass
        except TypeError: pass
    return None

class _DevNull:
    """
    A "file-like" object that discards anything that is written and
    always reports end-of-file when read.  C{_DevNull} is used by
    L{_import()} to discard output when importing modules; and to
    ensure that stdin appears closed.
    """
    def __init__(self):
        self.closed = 1
        self.mode = 'r+'
        self.softspace = 0
        self.name='</dev/null>'
    def close(self): pass
    def flush(self): pass
    def read(self, size=0): return ''
    def readline(self, size=0): return ''
    def readlines(self, sizehint=0): return []
    def seek(self, offset, whence=0): pass
    def tell(self): return 0L
    def truncate(self, size=0): pass
    def write(self, str): pass
    def writelines(self, sequence): pass
    xreadlines = readlines
_dev_null = _DevNull()
    




    
# [xx]
0 # hm..  otherwise the following gets treated as a docstring!  ouch!
"""
######################################################################
## Zope Extension...
######################################################################
class ZopeInspector(Inspector):
    VALUEDOC_CLASSES = Inspector.VALUEDOC_CLASSES.copy()
    VALUEDOC_CLASSES.update({
        'module': ZopeModuleDoc,
        'class': ZopeClassDoc,
        'interface': ZopeInterfaceDoc,
        'attribute': ZopeAttributeDoc,
        })
    
    def add_module_child(self, child, child_name, module_doc):
        if isinstance(child, zope.interfaces.Interface):
            module_doc.add_zope_interface(child_name)
        else:
            Inspector.add_module_child(self, child, child_name, module_doc)

    def add_class_child(self, child, child_name, class_doc):
        if isinstance(child, zope.interfaces.Interface):
            class_doc.add_zope_interface(child_name)
        else:
            Inspector.add_class_child(self, child, child_name, class_doc)

    def inspect_zope_interface(self, interface, interfacename):
        pass # etc...
"""        
