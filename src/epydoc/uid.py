#
# objdoc: epydoc crossreferencing
# Edward Loper
#
# Created [01/30/01 05:18 PM]
# $Id$
#

"""
Unique identifiers and crossreference links for Python objects.  Each
Python object is identified by a globally unique identifier,
implemented with the C{UID} class.  It is important that each object
have a single unique identifier, because one object may have more than
one name.  These C{UID}s are used the C{Link} class to implement
crossreferencing between C{ObjDoc}s.

@see: L{epydoc.objdoc}
"""

import inspect, sys, os.path, new, re, types
from types import ModuleType as _ModuleType
from types import ClassType as _ClassType
from types import TypeType as _TypeType
from types import FunctionType as _FunctionType
from types import BuiltinFunctionType as _BuiltinFunctionType
from types import BuiltinMethodType as _BuiltinMethodType
from types import MethodType as _MethodType
from types import StringType as _StringType

__all__ = ['UID', 'Link']

class UID:
    """
    A globally unique identifier used to refer to a Python object.
    UIDs are used by ObjDoc objects for the purpose of
    cross-referencing.  It is important that each object have one
    unique identifier, because one object may have more than one name.
    The UIDs are constructed directly from the objects that they point
    to, so they are guaranteed to be consistant.

    @ivar _id: The Python identifier for the object
    @type _id: C{int}
    @ivar _name: The dotted name for the object
    @type _name: C{string}
    @ivar _obj: The object
    @type _obj: any
    """
    def __init__(self, obj):
        """
        Create a globally unique identifier for C{obj}.

        @param obj: The object for which a unique identifier should be
            created.
        @type obj: any
        """
        
        # Special case: create a UID from just a name.
        if type(obj) is _StringType:
            self._obj = self._typ = self._id = None
            self._name = obj
            return
        
        self._id = id(obj)
        self._obj = obj
        
        if type(obj) is _ModuleType:
            self._name = obj.__name__
            
        elif type(obj) is _ClassType:
            self._name = '%s.%s' % (obj.__module__, obj.__name__)

        elif type(obj) is _FunctionType:
            self._name = '%s.%s' % (_find_function_module(obj).__name__,
                                    obj.__name__)
                          
        elif type(obj) is _MethodType:
            self._name = '%s.%s.%s' % (obj.im_class.__module__,
                                       obj.im_class.__name__,
                                       obj.__name__)

        elif isinstance(obj, _TypeType) and hasattr(obj, '__module__'):
            self._name = '%s.%s' % (obj.__module__, obj.__name__)
            
        else:
            # Last resort: use object's internal id.
            try:
                self._name = obj.__name__+'-'+`id(obj)`
            except:
                self._name = 'unknown-'+`id(obj)`

    def name(self):
        """
        @return: The complete name of this C{UID}.  This is typically
            a fully qualified dotted name, such as
            C{epydoc.epytext.UID}; but if the dotted name of an object
            cannot be found, a name will be constructed based on the
            object's Python identifier.            
        @rtype: C{string}
        """
        return self._name
    
    def shortname(self):
        """
        @return: The "short name" for this C{UID}.  This is typically
            the last part of the fully qualified dotted name, such as
            C{UID}; but if the dotted name of an object cannot be
            found, a name will be constructed based on the object's
            Python identifier.
        @rtype: C{string}
        """
        return self._name.split('.')[-1]
    
    def object(self):
        """
        @return: The object identified by this C{UID}; or C{None} if
            that object is not available.
        @rtype: any
        """
        return self._obj
    
    def __repr__(self): return self._name
    def __hash__(self): return hash(self._name)
    def __cmp__(self, other):
        if not isinstance(other, UID): return -1
        return cmp(self._name, other._name)

    def descendant_of(self, ancestor):
        """
        @return: True if the object identified by this UID is a
            descendant of C{ancestor}.  M{d} is a descendant of M{a}
            if M{d}=M{a}; or if M{d} is a descendent of an object
            contained by M{a}.
        @rtype: C{boolean}
        @param ancestor: The UID of the potential ancestor.
        @type ancestor: L{UID}
        """
        descendant = self
        
        if descendant.is_method():
            if ancestor.is_class():
                if descendant.cls() is ancestor: return 1
                else: return 0
            else: descendant = descendant.cls()

        if descendant.is_class() or descendant.is_function():
            if ancestor.is_module():
                if descendant.module() is ancestor: return 1
                else: return 0
            else: descendant = descendant.module()

        if not ancestor.is_package(): return 0

        while descendant is not None and descendant.is_module():
            if descendant.package() is ancestor: return 1
            else: descendant = descendant.package()

        return 0

    def cls(self):
        """
        @return: The UID of the class that contains the object
            identified by this UID.
        @rtype: L{UID}
        """
        if type(self._obj) is _MethodType: 
            return UID(self._obj.im_class)
        else:
            raise TypeError()
        
    def module(self):
        """
        @return: The UID of the module that contains the object
            identified by this UID.
        @rtype: L{UID}
        """
        if type(self._obj) is _MethodType:
            return UID(sys.modules[self._obj.im_class.__module__])
        elif type(self._obj) is _ClassType:
            return UID(sys.modules[self._obj.__module__])
        elif (isinstance(self._obj, _TypeType) and
              hasattr(self._obj, '__module__')):
            return UID(sys.modules[self._obj.__module__])
        elif type(self._obj) is _FunctionType:
            return UID(_find_function_module(self._obj))
        else:
            raise TypeError()

    def package(self):
        """
        @return: The UID of the package that contains the object
            identified by this UID.
        @rtype: L{UID}
        """
        if type(self._obj) is _ModuleType:
            dot = self._name.rfind('.')
            if dot < 0: return None
            return UID(sys.modules[self._name[:dot]])
        elif type(self._obj) in (_MethodType, _ClassType):
            return self.module().package()
        elif (isinstance(self._obj, _TypeType) and
              hasattr(self._obj, '__module__')):
            return self.module().package()
        else:
            raise TypeError()

    def is_function(self):
        """
        @return: True if this is the UID for a function.
        @rtype: C{boolean}
        """
        return type(self._obj) is _FunctionType

    def is_builtin_function(self):
        """
        @return: True if this is the UID for a builtin function.
        @rtype: C{boolean}
        """
        return type(self._obj) is _BuiltinFunctionType
    
    def is_builtin_method(self):
        """
        @return: True if this is the UID for a builtin method.
        @rtype: C{boolean}
        """
        return type(self._obj) is _BuiltinMethodType
    
    def is_class(self):
        """
        @return: True if this is the UID for a class.
        @rtype: C{boolean}
        """
        return ((type(self._obj) is _ClassType) or
                (isinstance(self._obj, _TypeType) and
                 hasattr(self._obj, '__module__')))

    def is_method(self):
        """
        @return: True if this is the UID for a method.
        @rtype: C{boolean}
        """
        return type(self._obj) is _MethodType

    def is_module(self):
        """
        @return: True if this is the UID for a module.
        @rtype: C{boolean}
        """
        return type(self._obj) is _ModuleType

    def is_package(self):
        """
        @return: True if this is the UID for a package.
        @rtype: C{boolean}
        """
        return (type(self._obj) is _ModuleType and
                hasattr(self._obj, '__path__'))

class Link:
    """
    A cross-reference link between documentation.  A link consists of
    a name and a target.  The target is a C{UID},
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
    @type _target: L{UID}
    @ivar _name: The name by which should be used to indicate this
        link in source documents.
    @type _name: C{string}
    """
    def __init__(self, name, target):
        """
        Create a new cross-reference link, with the given name and 
        target.
        
        @param name: A string specifying how the link should appear in
            the source document.
        @type name: C{string}
        @param target: The object that is pointed to by the new
            C{Link}. 
        @type target: L{UID}
        """
        self._name = name
        if isinstance(target, UID): self._target = target
        else: self._target = UID(target)

    def __repr__(self):
        """
        @return: A string representation of this C{Link}.
        @rtype: C{string}
        """
        return self._name+'->'+`self._target`
        
    def name(self):
        """
        @return: This link's name.  This string specifies how the link
            should appear in the source document.
        @rtype: C{string}
        """
        return self._name
    
    def target(self):
        """
        @return: This link's target.  This UID specifies what object
            is pointed to by this link.
        @rtype: L{UID}
        """
        return self._target

    def __cmp__(self, other):
        if not isinstance(other, Link): return -1
        return cmp(self._target, other._target)

def _find_function_module(func):
    """
    @return: The module that defines the given function.
    @rtype: C{module}
    @param func: The function whose module should be found.
    @type func: C{function}
    """
    if not inspect.isfunction(func):
        raise TypeError("Expected a function")
    if inspect.getmodule(func):
        return inspect.getmodule(func)

    # This fallback shouldn't usually be needed.  But it is needed in
    # a couple special cases (including using epydoc to document
    # itself).  In particular, if a module gets loaded twice, using
    # two different names for the same file, then this helps.
    for module in sys.modules.values():
        if module is None: continue
        if func.func_globals is module.__dict__:
            return module
    raise ValueError("Couldn't the find module for the function %s" %
                     func.func_name)

def _is_variable_in(name, container, docmap):
    """
    @return: True if C{name} is a variable documented by
        C{container} in C{docmap}.
    @rtype: C{boolean}
    @param name: The name to check.
    @type name: C{string}
    @param container: The UID of the object which might contain a
        variable named C{name}.
    @type container: L{UID}
    @param docmap: A documentation map containing the documentation
        for the object identified by C{container}.
    @type docmap: L{objdoc.DocMap}
    """
    if docmap is None or not docmap.has_key(container): return 0
    container_doc = docmap.get(container)
    if container.is_module():
        for var in container_doc.variables():
            if var.name() == name: return 1
    elif container.is_class():
        for var in container_doc.ivariables():
            if var.name() == name: return 1
        for var in container_doc.cvariables(): 
            if var.name() == name: return 1
    return 0

def _makeuid(obj):
    """
    @return: A UID constructed from C{obj}, if C{obj} is a module,
        class, function, or method.  Otherwise, return C{None}.
    @rtype: L{UID} or C{None}
    @param obj: The object whose UID should be returned.
    @type obj: any
    """
    if type(obj) in (_FunctionType, _BuiltinFunctionType,
                      _MethodType, _BuiltinMethodType,
                     _ClassType, _ModuleType):
        return UID(obj)
    elif isinstance(obj, _TypeType) and hasattr(obj, '__module__'):
        return UID(obj)
    else:
        return None

def _namedModule(name):
    """
    @return: The module with the given fully qualified name.  
    @rtype: C{module}
    @raise ImportError: If there is no module with the given name. 
    """
    return __import__(name, None, None, 1)

def _namedObject(name):
    """Get a fully named module-global object.
    """
    classSplit = name.split('.')
    module = _namedModule('.'.join(classSplit[:-1]))
    return getattr(module, classSplit[-1])

def findUID(name, container, docmap=None):
    """
    Attempt to find the UID for the object that can be accessed with
    the name C{name} from the module C{module}.

    @param name: The name used to identify the object.
    @type name: C{string}
    @param container: The UID of the class or module containing the
        object.
    @type container: L{UID}
    @param docmap: A documentation map, which is used to check if
        C{name} is the name of a module variable, class variable,
        or instance variable.
    @type docmap: L{objdoc.DocMap}
    @return: The UID for the object that can be accessed with the name
        C{name} from the module C{module}; or C{None} if no object was
        found.
    @rtype: L{UID} or C{None}
    """
    if container is None: return None
    if not (container.is_module() or container.is_class()):
        raise ValueError('Bad container %r' % container)

    # Is it the short name for a member of the containing class?
    if container.is_class():
        if _is_variable_in(name, container, docmap):
            return UID('%s.%s' % (container, name))
        elif container.object().__dict__.has_key(name):
            cls = container.object()
            obj = cls.__dict__[name]
            if type(obj) is _FunctionType:
                return UID(new.instancemethod(obj, None, cls))
            else:
                return _makeuid(obj)
        else:
            container = container.module()

    module = container.object()
    components = name.split('.')

    # Is it a variable in the containing module?
    if _is_variable_in(name, container, docmap):
        return UID('%s.%s' % (container, name))

    # Is it an object in the containing module?
    try:
        obj = module
        for component in components:
            obj = obj.__dict__[component]
        return _makeuid(obj)
    except KeyError: pass

    # Is it a module name?  The module name may be relative to the
    # containing module, or any of its ancestors.
    modcomponents = container.name().split('.')
    for i in range(len(modcomponents)-1, -1, -1):
        try:
            modname = '.'.join(modcomponents[:i]+[name])
            return(_makeuid(_namedModule(modname)))
        except: pass
        
    # Is it an object in a module?  The module part of the name may be
    # relative to the containing module, or any of its ancestors.
    modcomponents = container.name().split('.')
    for i in range(len(modcomponents)-1, -1, -1):
        for j in range(len(components)-1, 0, -1):
            try:
                modname = '.'.join(modcomponents[:i]+components[:j])
                objname = '.'.join(components[j:])
                mod = _namedModule(modname)
                if _is_variable_in(name, UID(mod), docmap):
                    return UID('%s.%s' % (container, name))
                obj = _namedObject(modname + '.' + objname)
                return _makeuid(obj)
            except: pass

    # We couldn't find it; return None.
    return None
