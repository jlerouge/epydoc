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

import inspect, re, sys, os.path, imp
# API documentation encoding:
from epydoc.apidoc import *
# Type comparisons:
from types import *
# Set datatype:
from sets import Set
# Error reporting:
from epydoc import log
# Helper functions:
from epydoc.util import *
# Builtin values
import __builtin__

######################################################################
## Caches
######################################################################

_valuedoc_cache = {}
"""A cache containing the API documentation for values that we've
already seen.  This cache is implemented as a dictionary that maps a
value's pyid to its L{ValueDoc}.

Note that if we encounter a value but decide not to inspect it
(because it's imported from another module), then C{_valuedoc_cache}
will contain an entry for the value, but the value will not be listed
in L{_inspected_values}."""

_inspected_values = {}
"""A record which values we've inspected, encoded as a dictionary from
pyid to C{bool}."""

######################################################################
## Inspection
######################################################################

# [xx] old:
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

def inspect_docs(value=None, name=None, filename=None, context=None,
                 is_script=False):
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
        if is_script:
            value = get_value_from_scriptname(filename)
        else:
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
    if pyid in _inspected_values:
        return _valuedoc_cache[pyid]

    # Inspect the value.
    _inspected_values[pyid] = True
    inspector = _get_inspector(value)
    val_doc = inspector(value)

    # Add it to the cache (or merge it if we've seen this value but
    # not inspected it before).
    if pyid in _valuedoc_cache:
        val_doc.merge_and_overwrite(_valuedoc_cache[pyid])
    else:
        _valuedoc_cache[pyid] = val_doc

    # Set canonical name, if it was given
    if val_doc.canonical_name == UNKNOWN and name is not None:
        val_doc.canonical_name = DottedName(name)

    # If we were given a filename, but didn't manage to get a
    # canonical name, then the module defined by the given file
    # must be shadowed by a variable in its parent package(s).
    # E.g., this happens with `curses.wrapper`.  Add a "'" to
    # the end of the name to distinguish it from the variable.
    if is_script and filename is not None:
        val_doc.canonical_name = DottedName(munge_script_name(str(filename)))
        
    if val_doc.canonical_name == UNKNOWN and filename is not None:
        shadowed_name = DottedName(value.__name__)
        log.warning("Module %s is shadowed by a variable with "
                    "the same name." % shadowed_name)
        val_doc.canonical_name = DottedName(str(shadowed_name)+"'")

    return val_doc

#////////////////////////////////////////////////////////////
# Module Inspection
#////////////////////////////////////////////////////////////

#: A list of module variables that should not be included in a
#: module's API documentation.
UNDOCUMENTED_MODULE_VARS = (
    '__builtins__', '__doc__', '__all__', '__file__', '__path__',
    '__name__', '__extra_epydoc_fields__', '__docformat__')

def inspect_module(module):
    """
    Add API documentation information about the module C{module}
    to C{module_doc}.
    """
    # Create the ModuleDoc
    module_doc = ModuleDoc(pyval=module, repr=value_repr(module),
                           canonical_name = get_canonical_name(module))
    
    # Record the module's docstring & docformat.
    if hasattr(module, '__doc__'):
        module_doc.docstring = get_docstring(module)
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
            module_doc.package = inspect_docs(package)
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
        if child_name in UNDOCUMENTED_MODULE_VARS: continue
        child = getattr(module, child_name)

        # Create a VariableDoc for the child, and inspect its
        # value if it's defined in this module.
        container = get_containing_module(child)
        if container != None and container == module_doc.canonical_name:
            # Local variable.
            child_val_doc = inspect_docs(child, context=module_doc)
            child_var_doc = VariableDoc(name=child_name,
                                        value=child_val_doc,
                                        is_imported=False,
                                        container=module_doc)
        elif container is None or module_doc.canonical_name is UNKNOWN:
            # Possibly imported variable.
            child_val_doc = inspect_docs(child, context=module_doc)
            child_var_doc = VariableDoc(name=child_name,
                                        value=child_val_doc,
                                        container=module_doc)
        else:
            # Imported variable.
            child_val_doc = _get_valuedoc(child)
            child_var_doc = VariableDoc(name=child_name,
                                        value=child_val_doc,
                                        is_imported=True,
                                        container=module_doc)

        module_doc.variables[child_name] = child_var_doc

    return module_doc

def _get_valuedoc(value):
    """
    If a C{ValueDoc} for the given value exists in the valuedoc
    cache, then return it; otherwise, create a new C{ValueDoc},
    add it to the cache, and return it.  When possible, the new
    C{ValueDoc}'s C{pyval}, C{repr}, and C{canonical_name}
    attributes will be set appropriately.
    """
    pyid = id(value)
    val_doc = _valuedoc_cache.get(pyid)
    if val_doc is None:
        val_doc = _valuedoc_cache[pyid] = inspect_other(value)
    return val_doc

#////////////////////////////////////////////////////////////
# Class Inspection
#////////////////////////////////////////////////////////////

#: A list of class variables that should not be included in a
#: class's API documentation.
UNDOCUMENTED_CLASS_VARS = (
    '__doc__', '__module__', '__dict__', '__weakref__')

def inspect_class(cls):
    """
    Add API documentation information about the class C{cls}
    to C{class_doc}.
    """
    # Create the ClassDoc.
    class_doc = ClassDoc(pyval=cls, repr=value_repr(cls),
                         canonical_name = get_canonical_name(cls))
    
    # Record the class's docstring.
    class_doc.docstring = get_docstring(cls)

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
            basedoc = inspect_docs(base)
            class_doc.bases.append(basedoc)
            basedoc.subclasses.append(class_doc)

    # Record the class's local variables.
    class_doc.variables = {}
    private_prefix = '_%s__' % cls.__name__
    if hasattr(cls, '__dict__'):
        for child_name, child in cls.__dict__.items():
            if child_name.startswith(private_prefix):
                child_name = child_name[len(private_prefix)-2:]
            if child_name in UNDOCUMENTED_CLASS_VARS: continue
            #try: child = getattr(cls, child_name)
            #except: continue
            val_doc = inspect_docs(child, context=class_doc)
            var_doc = VariableDoc(name=child_name, value=val_doc,
                                  container=class_doc)
            class_doc.variables[child_name] = var_doc

    return class_doc

#////////////////////////////////////////////////////////////
# Routine Inspection
#////////////////////////////////////////////////////////////

def inspect_routine(routine):
    """Add API documentation information about the function
    C{routine} to C{routine_doc} (specializing it to C{Routine_doc})."""
    # Create the RoutineDoc.
    routine_doc = RoutineDoc(pyval=routine, repr=value_repr(routine),
                             canonical_name = get_canonical_name(routine))

    # Extract the underying function
    if isinstance(routine, MethodType):
        func = routine.im_func
    elif isinstance(routine, staticmethod):
        func = routine.__get__(0)
    elif isinstance(routine, classmethod):
        func = routine.__get__(0).im_func
    else:
        func = routine

    # Record the function's docstring.
    routine_doc.docstring = get_docstring(func)

    # Record the function's signature.
    if isinstance(func, FunctionType):
        (args, vararg, kwarg, defaults) = inspect.getargspec(func)

        # Add the arguments.
        routine_doc.posargs = args
        routine_doc.vararg = vararg
        routine_doc.kwarg = kwarg

        # Set default values for positional arguments.
        routine_doc.posarg_defaults = [None]*len(args)
        if defaults is not None:
            offset = len(args)-len(defaults)
            for i in range(len(defaults)):
                default_val = inspect_docs(defaults[i])
                routine_doc.posarg_defaults[i+offset] = default_val

        # If it's a bound method, then strip off the first argument.
        if isinstance(routine, MethodType) and routine.im_self is not None:
            routine_doc.posargs = routine_doc.posargs[1:]
            routine_doc.posarg_defaults = routine_doc.posarg_defaults[1:]

    else:
        # [XX] I should probably use UNKNOWN here??
        routine_doc.posargs = ['...']
        routine_doc.posarg_defaults = [None]
        routine_doc.kwarg = None
        routine_doc.vararg = None

    # Change type, if appropriate.
    if isinstance(routine, staticmethod):
        routine_doc.specialize_to(StaticMethodDoc)
    if isinstance(routine, classmethod):
        routine_doc.specialize_to(ClassMethodDoc)
        
    return routine_doc

#////////////////////////////////////////////////////////////
# Property Inspection
#////////////////////////////////////////////////////////////

def inspect_property(prop):
    """Add API documentation information about the property
    C{prop} to C{prop_doc} (specializing it to C{PropertyDoc})."""
    # Create the PropertyDoc
    prop_doc = PropertyDoc(pyval=prop, repr=value_repr(prop),
                           canonical_name = get_canonical_name(prop))
    
    # Record the property's docstring.
    prop_doc.docstring = get_docstring(prop)

    # Record the property's access functions.
    prop_doc.fget = inspect_docs(prop.fget)
    prop_doc.fset = inspect_docs(prop.fset)
    prop_doc.fdel = inspect_docs(prop.fdel)

    return prop_doc

#////////////////////////////////////////////////////////////
# Generic Value Inspection
#////////////////////////////////////////////////////////////

def inspect_other(val):
    """
    Create and return a C{ValueDoc} for the given value.
    """
    return ValueDoc(pyval=val, repr=value_repr(val),
                    canonical_name = get_canonical_name(val))

#////////////////////////////////////////////////////////////
# Helper functions
#////////////////////////////////////////////////////////////

def get_docstring(value):
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
            log.warning("%s's docstring is not a unicode string, but it "
                        "contains non-ascii data -- treating it as "
                        "latin-1." % name)
            # Assume it's latin-1.
            return unicode(docstring, 'latin-1')
        return None
    elif value is BuiltinMethodType:
        # Don't issue a warning for this special case.
        return None
    else:
        if hasattr(value, '__name__'): name = value.__name__
        else: name = `value`
        log.warning("%s's docstring is not a string -- ignoring it." %
                    name)
        return None

def get_canonical_name(value):
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
        class_name = get_canonical_name(value.im_self)
        if class_name is None: return UNKNOWN
        dotted_name = DottedName(class_name, value.__name__)
    elif (inspect.ismethod(value) and
          not value.__name__.startswith('<')):
        class_name = get_canonical_name(value.im_class)
        if class_name is None: return UNKNOWN
        dotted_name = DottedName(class_name, value.__name__)
    elif (isinstance(value, FunctionType) and
          not value.__name__.startswith('<')):
        module_name = _find_function_module(value)
        if module_name is None: return UNKNOWN
        dotted_name = DottedName(module_name, value.__name__)
    else:
        return UNKNOWN

    return verify_name(value, dotted_name)

def verify_name(value, dotted_name):
    """
    Verify the name.  E.g., if it's a nested class, then we won't be
    able to find it with the name we constructed.
    """
    if dotted_name == UNKNOWN: return UNKNOWN
    if len(dotted_name) == 1 and hasattr(__builtin__, dotted_name[0]):
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

def value_repr(value):
    try:
        s = '%r' % value
        if isinstance(s, str):
            s = decode_with_backslashreplace(s)
        return s
    except:
        return UNKNOWN

def get_containing_module(value):
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
    elif inspect.isroutine(value):
        return DottedName(_find_function_module(value))
    else:
        return None

def _find_function_module(func):
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
# Inspection Dispatch Table
#////////////////////////////////////////////////////////////

_inspector_registry = []
def register_inspector(applicability_test, inspector, priority=10):
    """
    Register an inspector function.
    
    @param priority: The priority of this inspector, which determines
    the order in which inspectors are tried -- inspectors with lower
    numbers are tried first.  The standard inspectors have priorities
    ranging from 20 to 30.  The default priority (10) will place new
    inspectors before standard inspectors.
    """
    _inspector_registry.append( (priority, applicability_test, inspector) )
    _inspector_registry.sort()
    
def _get_inspector(value):
    for (priority, applicability_test, inspector) in _inspector_registry:
        if applicability_test(value):
            return inspector
    else:
        return inspect_other

# Register the standard inspector functions.
def is_classmethod(v): return isinstance(v, classmethod)
def is_staticmethod(v): return isinstance(v, staticmethod)
def is_property(v): return isinstance(v, property)
register_inspector(inspect.ismodule, inspect_module, priority=20)
register_inspector(inspect.isclass, inspect_class, priority=24)
register_inspector(inspect.isroutine, inspect_routine, priority=28)
register_inspector(is_property, inspect_property, priority=30)

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

def get_value_from_scriptname(filename):
    name = munge_script_name(filename)
    return _import(name, filename)

def get_value_from_name(name, globs=None):
    """
    Given a name, return the corresponding value.
    
    @param globals: A namespace to check for the value, if there is no
        module containing the named value.  Defaults to __builtin__.
    """
    name = DottedName(name)

    # Import the topmost module/package.  If we fail, then check if
    # the requested name refers to a builtin.
    try:
        module = _import(name[0])
    except ImportError:
        if globs is None: globs = __builtin__.__dict__
        if name[0] in globs:
            try: return _lookup(globs[name[0]], name[1:])
            except: raise
        else:
            raise

    # Find the requested value in the module/package or its submodules.
    for i in range(1, len(name)):
        try: return _lookup(module, name[i:])
        except ImportError: pass
        module = _import('.'.join(name[:i+1]))
        module = _lookup(module, name[1:i+1])
    return module

def _lookup(module, name):
    val = module
    for i, identifier in enumerate(name):
        try: val = getattr(val, identifier)
        except AttributeError:
            exc_msg = ('Could not import %s:\nNo variable named %s in %s' %
                       (name, identifier, '.'.join(name[:1+i])))
            raise ImportError(exc_msg)
    return val
            
def _import(name, filename=None):
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
    old_builtins = __builtin__.__dict__.copy()

    # Supress input and output.  (These get restored when we restore
    # sys to old_sys).  
    sys.stdin = sys.stdout = sys.stderr = _dev_null
    sys.__stdin__ = sys.__stdout__ = sys.__stderr__ = _dev_null

    # Remove any command-line arguments
    sys.argv = ['(imported)']

    try:
        try:
            if filename is None:
                return __import__(name)
            else:
                # For importing scripts:
                return imp.load_source(name, filename)
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
        __builtin__.__dict__.clear()
        __builtin__.__dict__.update(old_builtins)
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
