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
implemented with the L{UID} class.  It is important that each object
have a single unique identifier, because one object may have more than
one name.  UIDs should be always created using the L{make_uid}
function; do not create UIDs directly.  The L{Link} class uses UIDs to
implement crossreferencing between C{ObjDoc}s.

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
from epydoc.imports import import_module

__epydoc_sort__ = ['make_uid', 'UID', 'Link']

##################################################
## Table of Contents
##################################################
## - UID Base Class
## - UID Implementation Classes
##    - ObjectUID
##    - VariableUID
## - UID construction (make_uid)
## - Links
## - Inspection Helpers
## - UID Lookup (findUID)

##################################################
## Unique Identifier Base Class
##################################################

class UID:
    """
    A globally unique identifier.

    UID is an abstract base class.  The base class defines
    C{shortname}, C{is_private}, C{__str__}, and C{__repr__}; all
    other methods must be defined by derived classes.

    @ivar __name: This UID's globally unique name.
    @type __name: C{string}

    @cvariable _ids: A dictionary mapping from names to Python
        identifiers (as returned by C{id}).  This dictionary is used
        to ensure that all UIDs are given globally unique names.
    @type _ids: C{dictionary} from C{string} to C{int}
    """
    def __init__(self):
        raise NotImplementedError("UID is an abstract base class")

    #//////////////////////////////////////////////////
    # UID Name & Value
    #//////////////////////////////////////////////////
    def name(self):
        """
        @rtype: C{string}
        @return: The globally unique name for this identifier.  This
            name consists of several pieces, joined by periods, which
            indicate where the object is defined.  For example, the
            UID for this class has the name C{'epydoc.uid.UID'}, since
            it is named C{UID}, and defined in the C{uid} module of
            the C{epydoc} package.
            
        """
        raise NotImplementedError()

    def shortname(self):
        """
        @rtype: C{string}
        @return: The short name for this UID.  A UID's short name is
            the last piece of its globally unique name, as returned by
            L{name}.  This is typically the name that was used when
            definining the object.  For example, the UID for this
            class has the name C{'UID'}.
        """
        return self.name().split('.')[-1]

    def value(self):
        """
        @return: The value of the object or variable specified by this
            UID.
        @rtype: any
        """
        raise NotImplementedError()
    
    #//////////////////////////////////////////////////
    # Object type
    #//////////////////////////////////////////////////
    # Note: these types are *not* mutually exclusive.
    
    def is_module(self):
        """
        @return: True if this is the UID for a module or a package.
        @rtype: C{boolean}
        """
        raise NotImplementedError()

    def is_package(self):
        """
        @return: True if this is the UID for a package.
        @rtype: C{boolean}
        """
        raise NotImplementedError()

    def is_class(self):
        """
        @return: True if this is the UID for a class or a type.
        @rtype: C{boolean}
        """
        raise NotImplementedError()

    def is_function(self):
        """
        @return: True if this is the UID for a function.
        @rtype: C{boolean}
        """
        raise NotImplementedError()

    def is_builtin_function(self):
        """
        @return: True if this is the UID for a builtin function.
        @rtype: C{boolean}
        """
        raise NotImplementedError()
    
    def is_method(self):
        """
        @return: True if this is the UID for a method.
        @rtype: C{boolean}
        """
        raise NotImplementedError()

    def is_builtin_method(self):
        """
        @return: True if this is the UID for a builtin method.
        @rtype: C{boolean}
        """
        raise NotImplementedError()

    def is_routine(self):
        """
        @return: True if this is the UID for a function, a method, a
            builtin function, or a builtin method.
        @rtype: C{boolean}
        """
        raise NotImplementedError()
    
    def is_variable(self):
        """
        @return: True if this is the UID for a variable.
        @rtype: C{boolean}
        """
        raise NotImplementedError()

    def is_private(self):
        """
        @return: True if this is a private object, or if any of its
            ancestors are private objects.
              - An object whose parent is a module that defines
                the C{__all__} variable is private if and only if it is
                not contained in C{__all__}.  If C{__all__} is not a
                list, or if any error occurs while accessing
                C{__all__}, then it is ignored.
              - All other objects are private if and only if their
                (short) name begins with a single underscore, but
                does not end with an underscore.
        @rtype: C{boolean}
        """
        if not hasattr(self, '_private'):
            # Note: the order of these checks is significant.
            shortname = self.shortname()

            # First, check if the parent is private.
            parent = self.parent()
            if parent and parent.is_private():
                self._private = 1
                return 1
            
            # Next, check the __all__ variable.
            if (parent and parent.is_module() and
                hasattr(parent._obj, '__all__')):
                try:
                    self._private = (shortname not in parent._obj.__all__)
                    return self._private
                except: pass

            # Finally, check the short name.
            self._private = (shortname[:1] == '_' and
                             shortname[-1:] != '_')

        return self._private

    #//////////////////////////////////////////////////
    # Ancestors & Descendants
    #//////////////////////////////////////////////////
    def cls(self):
        """
        @return: The UID of the class that contains the object
            identified by this UID; or C{None} if the object
            identified by this UID is not part of a class.
        @rtype: L{UID} or C{None}
        """
        raise NotImplementedError()
        
    def module(self):
        """
        @return: The UID of the module that contains the object
            identified by this UID; or C{None} if the object
            identified by this UID is a module or a package.
        @rtype: L{UID}
        """
        raise NotImplementedError()

    def package(self):
        """
        @return: The UID of the package that contains the object
            identified by this UID; or C{None} if the object
            identified by this UID is not part of a package.
        @rtype: L{UID}
        """
        raise NotImplementedError()

    def parent(self):
        """
        @return: The UID of the object that contains the object
            identified by this UID; or C{None} if the object
            identified by this UID is not contained by any other
            object.  For methods, class variables, and instance
            variables, the parent is the containing class; for
            functions and classes, it is the containing module; and
            for modules, it is the containing package.
        """
        raise NotImplementedError()

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
        raise NotImplementedError()

    #//////////////////////////////////////////////////
    # Misc
    #//////////////////////////////////////////////////
    def __str__(self):
        """
        @rtype: C{string}
        @return: The globally unique name for this identifier.
        @see: L{name}
        """
        return self.name()

    def __repr__(self):
        """
        @rtype: C{string}
        @return: A string representation of this UID.  String
            representations of UIDs have the form::
                <UID: epydoc.uid.UID>
        """
        return '<UID: %s>' % self.name()

    def __cmp__(self, other):
        """
        Compare C{self} and C{other}, based on their globally unique
        names.
          - If they have the same name, then return 0.
          - If C{self}'s name preceeds C{other}'s name alphabetically,
            return -1.
          - If C{self}'s name follows C{other}'s name alphabetically,
            return +1.
        @rtype: C{int}
        @see: C{name}
        """
        if not isinstance(other, ObjectUID): return -1
        return cmp(self.name(), other.name())

    def __hash__(self): raise NotImplementedError()
    def __eq__(self, other): raise NotImplementedError()

##################################################
## UID Implementation Classes
##################################################

class ObjectUID(UID):
    """
    A globally unique identifier used to refer to a Python object.

    @ivar _id: The python identifier of the object (or of its
        underlying function for methods).  This is used for hashing.
    """
    def __init__(self, object):
        self._obj = object
        if type(object) is _MethodType: self._id = id(object.im_func)
        else: self._id = id(object)

    # The value of an ObjectUID is the object that was used to
    # construct the UID.
    def value(self): return self._obj

    def id(self):
        """
        @return: the Python internal identifier for this UID's object.
        @rtype: C{int}
        """
        return self._id

    # The following methods figure out the object type by examining
    # self._obj.  Docstrings are defined in UID.
    def is_module(self): return type(self._obj) is _ModuleType
    def is_function(self): return type(self._obj) is _FunctionType
    def is_method(self): return type(self._obj) is _MethodType
    def is_package(self): return (type(self._obj) is _ModuleType and
                                  hasattr(self._obj, '__path__'))
    def is_class(self): return ((type(self._obj) is _ClassType) or
                                isinstance(self._obj, _TypeType))
    def is_routine(self):
        return type(self._obj) in (_FunctionType, _BuiltinFunctionType,
                                   _MethodType, _BuiltinMethodType)
    def is_builtin_function(self): 
        return (type(self._obj) is _BuiltinFunctionType and
                self._obj.__self__ is None)
    def is_builtin_method(self):
        return (type(self._obj) is _BuiltinMethodType and
                self._obj.__self__ is not None)
    def is_variable(self): return 0

    def name(self):
        if not hasattr(self, '_name'):
            typ = type(self._obj)
            if typ is _ModuleType:
                if self.package():
                    shortname = self._obj.__name__.split('.')[-1]
                    self._name = '%s.%s' % (self.package(), shortname)
                else:
                    self._name = self._obj.__name__
            elif typ is _ClassType or typ is _FunctionType:
                self._name = '%s.%s' % (self.module(), self._obj.__name__)
            elif typ is _MethodType or (typ is _BuiltinMethodType and
                                        self._obj.__self__ is not None):
                self._name = '%s.%s' % (self.cls(), self._obj.__name__)
            elif typ is _TypeType and hasattr(self._obj, '__module__'):
                self._name = '%s.%s' % (self.module(), self._obj.__name__)
            elif (typ is _TypeType or (typ is _BuiltinFunctionType and
                                       self._obj.__self__ is None)):
                module = self.module()
                if module is None:
                    self._name = '__unknown__.%s' % self._obj.__name__
                else:
                    name = _find_name_in(self._obj, self.module()._obj)
                    self._name = '%s.%s' % (self.module(), name)
            else:
                raise ValueError("Can't find name for %r" % self._obj)
        return self._name
        
    def cls(self):
        if not hasattr(self, '_cls'):
            obj = self._obj
            if type(obj) is _MethodType:
                self._cls = ObjectUID(obj.im_class)
            elif (type(obj) is _BuiltinMethodType and
                  obj.__self__ is not None):
                self._cls = ObjectUID(type(obj.__self__))
            else:
                self._cls = None
        return self._cls

    def module(self):
        if not hasattr(self, '_module'):
            obj = self._obj
            typ = type(obj)

            try:
                if typ is _ModuleType:
                    return None
                if typ is _ClassType:
                    self._module = ObjectUID(import_module(obj.__module__))
                elif typ is _FunctionType:
                    self._module = ObjectUID(_find_function_module(obj))
                elif typ is _MethodType:
                    module = import_module(obj.im_class.__module__)
                    self._module = ObjectUID(module)
                elif typ is _BuiltinFunctionType and obj.__self__ is None:
                    module = _find_builtin_obj_module(obj)
                    if module is None: self._module = None
                    else: self._module = ObjectUID(module)
                elif typ is _BuiltinMethodType and obj.__self__ is not None:
                    cls = type(obj.__self__)
                    module = _find_builtin_obj_module(cls)
                    if module is None: self._module = None
                    else: self._module = ObjectUID(module)
                elif typ is _TypeType and hasattr(obj, '__module__'):
                    self._module = ObjectUID(import_module(obj.__module__))
                    if (self._module is not None and
                        obj not in self._module.value().__dict__.values()):
                        # The __module__ attribute lied; try finding it ourselves.
                        module = _find_builtin_obj_module(obj)
                        if module is not None: self._module = ObjectUID(module)
                elif typ is _TypeType:
                    module = _find_builtin_obj_module(obj)
                    if module is None: self._module = None
                    else: self._module = ObjectUID(module)
                else:
                    raise ValueError("Cant find module for %r" % self._obj)
            except ImportError, e:
                if sys.stderr.softspace: print >>sys.stderr
                print  >>sys.stderr, '\n  Warning: %s' % e
                self._module = None
        return self._module

    def package(self):
        if not hasattr(self, '_pkg'):
            # Find the module.
            if type(self._obj) is _ModuleType: mname = self._obj.__name__
            elif self.module() is not None:
                mname = self.module()._obj.__name__
            else:
                self._pkg = None
                return None

            # Look up the package.
            dot = mname.rfind('.')
            if dot < 0: self._pkg = None
            else:
                try:
                    self._pkg = ObjectUID(import_module(mname[:dot]))
                except ImportError, e:
                    if sys.stderr.softspace: print >>sys.stderr
                    print  >>sys.stderr, '\n  Warning: %s' % e
                    self._pkg = None
                                  
        return self._pkg

    def parent(self):
        return self.cls() or self.module() or self.package()

    def descendant_of(self, ancestor):
        if self == ancestor: return 1
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
    def __hash__(self):
        # This should be fast, since it's used for hashing; so use the
        # Python internal id.
        return self._id

    def __eq__(self, other):
        # This should be fast, since it's used for hashing; so use the
        # Python internal id.
        return isinstance(other, ObjectUID) and self._id == other._id

class VariableUID(UID):
    """
    A globally unique identifier used to refer to a variable, relative
    to a Python object.

    This is used for variables.  I guess it could also be used for
    parameters to functions..  
    """
    def __init__(self, value, base_uid, shortname):
        """
        @param base_uid: The base ...
        @param shortname: The name...
        """
        self._base = base_uid
        self._shortname = shortname
        self._value = value

    def value(self): return self._value

    # The following methods are used to check the type of the UID.
    # Docstrings are defined in UID.
    def is_variable(self): return 1
    def is_module(self): return 0
    def is_function(self): return 0
    def is_method(self): return 0
    def is_package(self): return 0
    def is_class(self): return 0
    def is_builtin_function(self): return 0
    def is_builtin_method(self): return 0
    def is_routine(self): return 0

    # Return the UID's full name and short name.
    def name(self): return '%s.%s' % (self._base.name(), self._shortname)
    def shortname(self): return self._shortname

    # The following methods report about the ancestors of the UID, 
    # mainly by delegating to the base UID.
    def cls(self):
        if self._base.is_class(): return self._base
        else: return self._base.cls()
    def module(self):
        if self._base.is_module(): return self._base
        else: return self._base.module()
    def package(self):
        return self._base.package()
    def parent(self):
        return self._base

    def descendant_of(self, ancestor):
        if self == ancestor: return 1
        return self._base.descendant_of(ancestor)
        
    def __hash__(self):
        return hash( (self._base, self._shortname) )

    def __eq__(self, other):
        return (isinstance(other, VariableUID) and
                self._shortname == other._shortname and
                self._base == other._base)

##################################################
## UID Construction
##################################################

_object_uids = {}
_variable_uids = {}
_name_to_uid = {}
def make_uid(object, base_uid=None, shortname=None):
    """
    Create a globally unique identifier for the given object.
    """
    if type(object) in (_ModuleType, _ClassType, _TypeType,
                        _BuiltinFunctionType, _BuiltinMethodType,
                        _FunctionType, _MethodType):
        # If we've already seen this object, return its UID.
        if type(object) is _MethodType: key = id(object.im_func)
        else: key = id(object)
        try: return _object_uids[key]
        except: pass

        # We haven't seen this object before; create a new UID.
        uid = ObjectUID(object)
        _object_uids[key] = uid

        # Make sure there's no naming conflict.
        if _name_to_uid.has_key(uid.name()):
            if sys.stderr.softspace: print >>sys.stderr
            print >>sys.stderr, ('Warning: UID conflict '+
                                 'detected: %s' % uid)
        _name_to_uid[uid.name()] = uid

        # Return the UID.
        return uid

    elif base_uid is not None and shortname is not None:
        # If we've already seen this variable, return its UID
        key = (base_uid.id(), shortname)
        try: return _variable_uids[key]
        except: pass
        
        # We haven't seen this variable before; create a new UID.
        uid = VariableUID(object, base_uid, shortname)
        _variable_uids[key] = uid
            
        # Make sure there's no naming conflict.
        if _name_to_uid.has_key(uid.name()):
            if sys.stderr.softspace: print >>sys.stderr
            print >>sys.stderr, ('Warning: UID conflict '+
                                 'detected: %s' % uid)
        _name_to_uid[uid.name()] = uid
        return uid 
    else:
        raise TypeError('Cannot create a UID for a '+
                        type(object).__name__+
                        ' without a base UID.')

def reset_uid_cache():
    """
    Reset the internal cache of UIDs for objects.
    @rtype: C{None}
    """
    global _object_uids, _variable_uids, _name_to_uid
    _object_uids = {}
    _variable_uids = {}
    _name_to_uid = {}

##################################################
## Links
##################################################

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
        if not isinstance(target, UID): raise TypeError()
        self._target = target

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

##################################################
## Inspection Helper Functions
##################################################

_find_builtin_obj_module_cache = {}
def _find_builtin_obj_module(obj, show_warnings=1):
    """
    @return: The module that defines the given builtin object.
    @rtype: C{module}
    @param obj: The object whose module should be found.
    @type obj: C{builtin object}
    """
    global _find_builtin_obj_module_cache
    if _find_builtin_obj_module_cache.has_key(id(obj)):
        return _find_builtin_obj_module_cache[id(obj)]
    so_modules = []
    builtin_modules = []
    py_modules = []
    for module in sys.modules.values():
        # Skip it if there's no module, if we've already seen it, or
        # if it's __main__.
        if module is None: continue
        if module in so_modules: continue
        if module in builtin_modules: continue
        if module in py_modules: continue
        if module.__name__ == '__main__': continue
        
        for val in module.__dict__.values():
            if val is obj:
                if (module.__name__ in sys.builtin_module_names or
                    not hasattr(module, '__file__')):
                    builtin_modules.append(module)
                elif module.__file__[-3:] == '.so':
                    so_modules.append(module)
                else:
                    py_modules.append(module)
                break # Stop looking in this module.

    # If it's in a .so module, use that.
    if so_modules:
        if len(so_modules) > 1:
            if show_warnings:
                if sys.stderr.softspace: print >>sys.stderr
                print >>sys.stderr, ('Warning: '+`obj`+
                                 ' appears in multiple .so modules')
        module = so_modules[0]

    # Otherwise, check the builtin modules.
    elif builtin_modules:
        if len(builtin_modules) > 1:
            print builtin_modules
            if show_warnings:
                if sys.stderr.softspace: print >>sys.stderr
                print >>sys.stderr, ('Warning: '+`obj`+
                                 ' appears in multiple builtin modules')
        module = builtin_modules[0]

    # Give precedence to the "types" module over other py modules
    elif types in py_modules:
        module = types
        
    # Otherwise, check the python modules.
    elif py_modules:
        if len(py_modules) > 1:
            if show_warnings:
                if sys.stderr.softspace: print >>sys.stderr
                print >>sys.stderr, ('Warning: '+`obj`+
                                 ' appears in multiple .py modules')
        module = py_modules[0]
    else:
        if show_warnings:
            if sys.stderr.softspace: print >>sys.stderr
            print >>sys.stderr, ('Warning: could not find a '+
                                 'module for %r' % obj)
        module = None
    _find_builtin_obj_module_cache[id(obj)] = module
    return module

def _find_name_in(obj, module):
    for (key, val) in module.__dict__.items():
        if val is obj: return key

def _find_function_module(func):
    """
    @return: The module that defines the given function.
    @rtype: C{module}
    @param func: The function whose module should be found.
    @type func: C{function}
    """
    if not inspect.isfunction(func):
        raise TypeError("Expected a function")
    try:
        if inspect.getmodule(func):
            return inspect.getmodule(func)
    except: pass

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

##################################################
## UID Lookup
##################################################
# Clean this up a lot!

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
    if name == '': return None
    if container is None: return None
    if not (container.is_module() or container.is_class()):
        raise ValueError('Bad container %r' % container)

    # Is it the short name for a member of the containing class?
    if container.is_class():
        if _is_variable_in(name, container, docmap):
            val = None # it may not be a real object
            return make_uid(val, container, name)
        elif container.value().__dict__.has_key(name):
            cls = container.value()
            obj = cls.__dict__[name]
            if type(obj) is _FunctionType:
                return make_uid(new.instancemethod(obj, None, cls),
                                container, name)
            else:
                return make_uid(obj, container, name)
        else:
            container = container.module()

    module = container.value()
    components = name.split('.')

    # Is it a variable in the containing module?
    if _is_variable_in(name, container, docmap):
        val = None # it may not be a real object
        return make_uid(val, container, name)

    # Is it an object in the containing module?
    try:
        obj = module
        for component in components:
            obj_parent = obj
            obj_name = component
            try: obj = obj.__dict__[component]
            except: raise KeyError()
        try: return make_uid(obj, make_uid(obj_parent), obj_name)
        except: pass
    except KeyError: pass

    # Is it a module name?  The module name may be relative to the
    # containing module, or any of its ancestors.
    modcomponents = container.name().split('.')
    for i in range(len(modcomponents)-1, -1, -1):
        try:
            modname = '.'.join(modcomponents[:i]+[name])
            return(make_uid(import_module(modname)))
        except: pass
        
    # Is it an object in a module?  The module part of the name may be
    # relative to the containing module, or any of its ancestors.
    modcomponents = container.name().split('.')
    for i in range(len(modcomponents)-1, -1, -1):
        for j in range(len(components)-1, 0, -1):
            try:
                modname = '.'.join(modcomponents[:i]+components[:j])
                objname = '.'.join(components[j:])
                mod = import_module(modname)
                if _is_variable_in(name, make_uid(mod), docmap):
                    val = None # it may not be a real object
                    return make_uid(val, container, name)
                obj = getattr(import_module(modname), objname)
                return make_uid(obj, make_uid(mod), objname)
            except: pass

    # We couldn't find it; return None.
    return None

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
            if var.uid().shortname() == name: return 1
    elif container.is_class():
        for var in container_doc.ivariables():
            if var.uid().shortname() == name: return 1
        for var in container_doc.cvariables(): 
            if var.uid().shortname() == name: return 1
    return 0

