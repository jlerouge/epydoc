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

@see: C{epydoc.objdoc}
"""

import inspect, sys, os.path
from types import ModuleType as _ModuleType
from types import ClassType as _ClassType
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
            self._name = (_find_function_module(obj).__name__+'.'+
                          obj.__name__)
                          
        elif type(obj) == _MethodType:
            self._name = (obj.im_class.__module__+'.'+
                          obj.im_class.__name__+'.'+
                          obj.__name__)

        else:
            # Last resort: use object's internal id.
            try:
                self._name = obj.__name__+'-'+`id(obj)`
            except:
                self._name = 'unknown-'+`id(obj)`

    def name(self): return self._name
    def shortname(self): return self._name.split('.')[-1]
    def pathname(self): return os.path.join(*self._name.split('.'))
    def object(self): return self._obj
    def __repr__(self): return self._name
    def __hash__(self): return hash(self._name)
    def __cmp__(self, other):
        if not isinstance(other, UID): return -1
        return cmp(self._name, other._name)

    def descendant_of(self, ancestor):
        """
        Return true if self is a X{descendant} of other.
        """
        descendant = self
        
        if descendant.is_method():
            if ancestor.is_class():
                if descendant.cls() == ancestor: return 1
                else: return 0
            else: descendant = descendant.cls()

        if descendant.is_class() or descendant.is_function():
            if ancestor.is_module():
                if descendant.module() == ancestor: return 1
                else: return 0
            else: descendant = descendant.module()

        if not ancestor.is_package(): return 0

        while descendant is not None and descendant.is_module():
            if descendant.package() == ancestor: return 1
            else: descendant = descendant.package()

        return 0

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
            return UID(_find_function_module(self._obj))
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

    def is_function(self):
        return type(self._obj) in (_FunctionType,)

    def is_class(self):
        return type(self._obj) == _ClassType

    def is_method(self):
        return type(self._obj) == _MethodType

    def is_module(self):
        return type(self._obj) == _ModuleType

    def is_package(self):
        "Return true if this is the UID for a package"
        return (type(self._obj) == _ModuleType and
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

def _find_function_module(func):
    """
    @return: the module that defines the given function.
    """
    if not inspect.isfunction(func):
        raise TypeError("Expected a function")
    for module in sys.modules.values():
        if module == None: continue
        if func.func_globals == module.__dict__:
            return module
    raise ValueError("Couldn't the find module for this function")

