import inspect, re, sys
from apidoc import *
#import apidoc; reload(apidoc); from apidoc import *
from types import *

class DocInspector:
    """
        >>> inspector = Inspector(docmap)
        >>> for module in modules:
        ...     inspector.inspect(module)
        >>> inspector.finalize_names()

    Subclassing
    ===========
        - Override make_valuedoc.
        - Override inspect_value.

    @group Subclassing Hooks: L{valuedoc_class}, L{inspector_method}
    """
    def __init__(self):
        """
        Create a new C{Inspector}
        """
        self._inspected_values = {}
        """The set of values that we have inspected or started
        inspecting, encoded as a dictionary from pyid to bool."""
        
        self._current_module = None # [XX] ??
        """What module are we currently inspecting?  Used to avoid
        following inspection links out of the current module."""

        self._valuedoc_cache = {}
        """A cache of the API documentation for values that we've
        already seen.  This cache is implemented as a dictionary that
        maps a value's pyid to its L{ValueDoc}."""

    #////////////////////////////////////////////////////////////
    # Inspection Entry Points
    #////////////////////////////////////////////////////////////

    def inspect(self, value, context=None):
        """
        @return: API documentation information for the given value.
        @rtype: L{ValueDoc}
        """
        pyid = self.uid(value)

        # If we've already inspected this value, then simply return
        # its ValueDoc from our cache.
        if self._inspected_values.get(pyid):
            return self._valuedoc_cache[pyid]

        # If we have already seen this value, the get its ValueDoc
        # from our cache.  Otherwise, create a new ValueDoc for it
        # (and add it to the cache).
        valuedoc = self.get_valuedoc(value, context)

        # Get the value's canonical name (if it has one).
        dotted_name = self.get_canonical_name(value)
        if dotted_name is not None:
            valuedoc.dotted_name = dotted_name

        # Record the fact that we're inspecting this value.
        self._inspected_values[pyid] = 1

        # Inspect the value, and return the completed ValueDoc.
        inspector_method = self.inspector_method(value, context)
        inspector_method(value, valuedoc)
        return valuedoc

    def get_valuedoc(self, value, context=None):
        pyid = self.uid(value)
        valuedoc = self._valuedoc_cache.get(pyid)
        if valuedoc is None:
            valuedoc_class = self.valuedoc_class(value, context)
            valuedoc = valuedoc_class()
            valuedoc.value = value
            self._valuedoc_cache[pyid] = valuedoc
        return valuedoc

    # This can be overriden by subclasses.
    def valuedoc_class(self, value, context=None):
        """
        @return: The L{ValueDoc} subclass that should be used to
        encode the given value.  The subclass must define a
        constructor that takes no arguments.
                 
        @rtype:  C{class}
        """
        if inspect.ismodule(value):
            return ModuleDoc
        elif inspect.isclass(value):
            return ClassDoc
        elif isinstance(context, ClassDoc) and inspect.isfunction(value):
            return StaticMethodDoc
        elif (isinstance(context, ClassDoc) and inspect.ismethod(value) and
              value.im_self is not None and value.im_class is ClassType):
            return ClassMethodDoc
        elif isinstance(context, ClassDoc) and inspect.ismethod(value):
            return InstanceMethodDoc
        elif inspect.isroutine(value):
            return FunctionDoc
        elif isinstance(value, property):
            return PropertyDoc
        else:
            return ValueDoc

    # This can be overriden by subclasses.
    def inspector_method(self, value, context=None):
        """
        @return: A routine that should be used to inspect the given
        value.  This routine should accept two parameters, a value and
        a L{ValueDoc}; and should udpate the L{ValueDoc} with API
        documentation information about the value.  Typically, this
        routine is a bound instancemethod of L{Inspector} itself.
        
        @rtype: C{routine}
        """
        if inspect.ismodule(value):
            return self.inspect_module
        elif inspect.isclass(value):
            return self.inspect_class
        elif inspect.isfunction(value):
            return self.inspect_function
        elif inspect.ismethod(value):
            return self.inspect_method
        elif inspect.isroutine(value):
            return self.inspect_builtin
        elif isinstance(value, property):
            return self.inspect_property
        else:
            return self.inspect_value

    #////////////////////////////////////////////////////////////
    # Module Inspection
    #////////////////////////////////////////////////////////////

    UNDOCUMENTED_MODULE_VARS = (
        '__builtins__', '__doc__', '__all__', '__file__', '__path__',
        '__name__', '__extra_epydoc_fields__', '__docformat__')
    """A list of module variables that should not be documented."""

    def inspect_module(self, module, moduledoc):
        # Record the current module name, to restrict the set
        # of children that we'll inspect.
        self._current_module = moduledoc.dotted_name
        
        # Record the module's docstring & docformat.
        if hasattr(module, '__doc__'):
            moduledoc.docstring = module.__doc__
        if hasattr(module, '__docformat__'):
            moduledoc.docformat = module.__docformat__

        # Record the module's __all__ attribute (public names).
        if hasattr(module, '__all__'):
            try:
                public_names = [str(name) for name in module.__all__]
                moduledoc.public_names = public_names
            except: pass

        # Record the module's parent package, if it has one.
        dotted_name = moduledoc.dotted_name
        if dotted_name is not None and len(dotted_name) > 1:
            package_name = str(dotted_name[:-1])
            package = sys.modules.get(package_name)
            if package is not None:
                moduledoc.package = self.inspect(package, context=moduledoc)

        # Add the module to its parent package's submodules list.
        if moduledoc.package is not None:
            moduledoc.package.submodules.append(moduledoc)

        # Record the module's children.
        for child_name in dir(module):
            if child_name in self.UNDOCUMENTED_MODULE_VARS: continue
            child = getattr(module, child_name)

            # Create a VariableDoc for the child, and inspect its
            # value if it's defined in this module.
            container = self.get_containing_module(child)
            if container != None and container == moduledoc.dotted_name:
                child_val_doc = self.inspect(child, context=moduledoc)
                child_var_doc = VariableDoc(child_name, child_val_doc)
                child_var_doc.is_imported = 0
            elif container is None or moduledoc.dotted_name is None:
                child_val_doc = self.inspect(child, context=moduledoc)
                child_var_doc = VariableDoc(child_name, child_val_doc)
                child_var_doc.is_imported = None # = unknown.
            else:
                child_val_doc = self.get_valuedoc(child)
                child_var_doc = VariableDoc(child_name, child_val_doc)
                child_var_doc.is_imported = 1

            moduledoc.children[child_name] = child_var_doc

        # Reset the current module name to None.
        self._current_module = None

    #////////////////////////////////////////////////////////////
    # Class Inspection
    #////////////////////////////////////////////////////////////

    UNDOCUMENTED_CLASS_VARS = (
        '__doc__', '__module__', '__dict__', '__weakref__')
    """A list of class variables that should not be documented."""

    def inspect_class(self, cls, classdoc):
        # Record the class's docstring.
        if hasattr(cls, '__doc__'):
            classdoc.docstring = cls.__doc__

        # Record the class's __all__ attribute (public names).
        if hasattr(cls, '__all__'):
            try:
                public_names = [str(name) for name in cls.__all__]
                classdoc.public_names = public_names
            except: pass

        # Record the class's base classes; and add the class to its
        # base calss's subclass lists.
        if hasattr(cls, '__bases__'):
            for base in cls.__bases__:
                basedoc = self.inspect(base, context=classdoc)
                classdoc.bases.append(basedoc)
                basedoc.subclasses.append(classdoc)

        # Record the class's children.
        for child_name in dir(cls):
            if child_name in self.UNDOCUMENTED_CLASS_VARS: continue
            child_var_doc = self.get_class_child(cls, classdoc, child_name)
            if child_var_doc is not None:
                # Note: use child_var_doc.name instead of child_name,
                # to handle private name mangling.
                classdoc.children[child_var_doc.name] = child_var_doc

    def get_class_child(self, cls, classdoc, name):
        # Look for the requested object by searching the base order.
        # This way, we get the object from the class that defines it.
        # This is important e.g. to tell if an instance method is
        # inherited or not.
        base_order = inspect.getmro(cls)
        for base in base_order:
            if not hasattr(base, '__dict__'): continue
            if base.__dict__.has_key(name):
                try: child = getattr(base, name)
                except: child = base.__getattribute__(base, name)
            
                # If it's private and belongs to this class, then undo
                # the private name mangling.  If it's private, and
                # belongs to a base class, then don't list it at all.
                private_prefix = '_%s__' % base.__name__
                if name.startswith(private_prefix):
                    if base is base_order[0]:
                        name = name[len(private_prefix)-2:]
                    else:
                        return None
                    
                # Create & return a VariableDoc for it.
                valuedoc = self.inspect(child, context=classdoc)
                return VariableDoc(name, valuedoc)

        # If we couldn't find it, then try some fallbacks.
        else:
            try:
                try: child = getattr(cls, name)
                except: child = cls.__getattribute__(cls, name)
                valuedoc = self.inspect(child, context=classdoc)
                return VariableDoc(name, valuedoc)
            except:
                return VariableDoc(name, ValueDoc())

    #////////////////////////////////////////////////////////////
    # Routine Inspection
    #////////////////////////////////////////////////////////////

    def inspect_method(self, method, routinedoc):
        self.inspect_function(method.im_func, routinedoc)

    def inspect_function(self, func, funcdoc):
        # Record the function's docstring.
        if hasattr(func, '__doc__'):
            funcdoc.docstring = func.__doc__

        # Record the function's signature.
        if isinstance(func, FunctionType):
            self.inspect_function_signature(func, funcdoc)
        elif inspect.isroutine(func):
            self.parse_function_signature(func, funcdoc)

    def inspect_builtin(self, func, funcdoc):
        # Record the builtin's docstring.
        if hasattr(func, '__doc__'):
            funcdoc.docstring = func.__doc__

        # Record the builtin's signature.
        if not self.parse_function_signature(func, funcdoc):
            funcdoc.args = [ArgDoc('...')]

    def inspect_function_signature(self, func, funcdoc):
        # Get the function's signature
        (args, vararg, kwarg, defaults) = inspect.getargspec(func)

        # Try extracting a signature from the docstring.
        if self.parse_function_signature(func, funcdoc):
            # [XX] check for consistency??
            return

        # Add positional arguments.
        args = [ArgDoc(arg) for arg in args]
        funcdoc.args = args

        # Set default values.
        if defaults is not None:
            offset = len(args)-len(defaults)
            for i in range(len(defaults)):
                args[i+offset].default = self.inspect(defaults[i])

        # Add the vararg.
        if vararg is not None:
            funcdoc.vararg = ArgDoc(vararg)

        # Add the keyword arguments.
        if kwarg is not None:
            funcdoc.kwarg = ArgDoc(kwarg)

    # [XX] todo: add optional type modifiers?
    _SIGNATURE_RE = re.compile(
        # Class name (for builtin methods)
        r'^\s*((?P<self>\w+)\.)?' +
        # The function name (must match exactly)
        r'(?P<func>\w+)' +
        # The parameters
        r'\((?P<params>(\s*\[?\s*[\w\-\.]+(=.+?)?'+
        r'(\s*\[?\s*,\s*\]?\s*[\w\-\.]+(=.+?)?)*\]*)?)\s*\)' +
        # The return value (optional)
        r'(\s*(->)\s*(?P<return>\S.*?))?'+
        # The end marker
        r'\s*(\n|\s+(--|<=+>)\s+|$|\.\s|\.\n)')
    """A regular expression that is used to extract signatures from
    docstrings."""
        
    def parse_function_signature(self, func, funcdoc):
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
        # If there's no docstring, then don't do anything.
        if not funcdoc.docstring: return 0

        m = self._SIGNATURE_RE.match(funcdoc.docstring)
        
        if not m or m.group('func') != func.__name__:
            return 0
        
        params = m.group('params')
        rtype = m.group('return')
        selfparam = m.group('self')
        
        # Extract the parameters from the signature.
        funcdoc.args = []
        if params:
            # Figure out which parameters are optional.
            while '[' in params or ']' in params:
                m2 = re.match(r'(.*)\[([^\[\]]+)\](.*)', params)
                if not m2: return 0
                (start, mid, end) = m2.groups()
                mid = re.sub(r'((,|^)\s*[\w\-\.]+)', r'\1=...', mid)
                params = start+mid+end

            params = re.sub(r'=...=' , r'=', params)
            for name in params.split(','):
                if '=' in name:
                    (name, default_repr) = name.split('=',1)
                    default = ValueDoc(repr=default_repr)
                else:
                    default = None
                name = name.strip()
                if name == '...':
                    funcdoc.vararg = ArgDoc('...', default=default)
                elif name.startswith('**'):
                    funcdoc.kwarg = ArgDoc(name[2:], default=default)
                elif name.startswith('*'):
                    funcdoc.vararg = ArgDoc(name[1:], default=default)
                else:
                    funcdoc.args.append(ArgDoc(name, default=default))

        # Extract the return type/value from the signature
        if rtype:
            funcdoc.returns = rtype #ArgDoc('return', type=rtype)

        # Add the self parameter, if it was specified.
        if selfparam:
            funcdoc.args.insert(0, ArgDoc(selfparam))

        # Remove the signature from the docstring.
        funcdoc.docstring = funcdoc.docstring[m.end():]
            
        # We found a signature.
        return 1

    def add_builtin_signature(self, func, funcdoc):
        pass

    #////////////////////////////////////////////////////////////
    # Property Inspection
    #////////////////////////////////////////////////////////////

    def inspect_property(self, prop, propdoc):
        # Record the property's docstring.
        if hasattr(prop, '__doc__'):
            propdoc.docstring = prop.__doc__

        # Record the property's access functions.
        propdoc.fget = self.inspect(prop.fget)
        propdoc.fset = self.inspect(prop.fset)
        propdoc.fdel = self.inspect(prop.fdel)

    #////////////////////////////////////////////////////////////
    # Value Inspection
    #////////////////////////////////////////////////////////////

    def inspect_value(self, val, valdoc):
        # It's just a generic value; nothing else to do.
        pass

    #////////////////////////////////////////////////////////////
    # Helper functions
    #////////////////////////////////////////////////////////////

    def uid(self, value):
        """
        @return: A unique hashable identifier for the given value.
        """
        # Every time we access a method, we get a new object, with a
        # new pyid.  So instead of using the method's pyid, use the
        # pyid of its class, function, and self variable.
        if inspect.ismethod(value):
            return (id(value.im_class), id(value.im_func),
                    id(value.im_self))
        else:
            return id(value)

    def get_canonical_name(self, value):
        """
        @return: the canonical name for C{value}, or C{None} if no
        canonical name can be found.  Currently, C{get_canonical_name}
        can find canonical names for: modules; functions; non-nested
        classes; methods of non-nested classes; and some class methods
        of non-nested classes.
        
        @rtype: L{DottedName} or C{None}
        """
        if not hasattr(value, '__name__'): return None

        # Get the name via inspection.
        if isinstance(value, ModuleType):
            dotted_name = DottedName(value.__name__)
        elif isinstance(value, ClassType):
            dotted_name = DottedName(value.__module__, value.__name__)
        elif (inspect.ismethod(value) and value.im_self is not None and
              value.im_class is ClassType): # class method.
            class_name = self.get_canonical_name(value.im_self)
            if class_name is None: return None
            dotted_name = DottedName(class_name, value.__name__)
        elif inspect.ismethod(value):
            class_name = self.get_canonical_name(value.im_class)
            if class_name is None: return None
            dotted_name = DottedName(class_name, value.__name__)
        elif isinstance(value, FunctionType):
            module_name = self._find_function_module(value)
            if module_name is None: return None
            dotted_name = DottedName(module_name, value.__name__)
        else:
            return None

        # Verify the name.
        named_value = sys.modules.get(dotted_name[0])
        if named_value is None: return None
        for identifier in dotted_name[1:]:
            try: named_value = getattr(named_value, identifier)
            except: return None
        if self.uid(value) == self.uid(named_value):
            return dotted_name
        else:
            return None

    def get_containing_module(self, value):
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

######################################################################
## TESTING
######################################################################

if __name__ == '__main__':
    import epydoc_test
    del sys.modules['epydoc_test']
    import epydoc_test
    inspector = DocInspector()
    #import re; inspector.inspect(re)
    val = inspector.inspect(epydoc_test)#.classes[0]
    #val = Inspector().inspect(list)
    print val.pp(depth=-1, exclude=['subclasses', 'bases', 'value',
                                    'is_alias', 'name'])
    #print Inspector().inspect(A)
        

   
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
    
    def add_module_child(self, child, child_name, moduledoc):
        if isinstance(child, zope.interfaces.Interface):
            moduledoc.add_zope_interface(child_name)
        else:
            Inspector.add_module_child(self, child, child_name, moduledoc)

    def add_class_child(self, child, child_name, classdoc):
        if isinstance(child, zope.interfaces.Interface):
            classdoc.add_zope_interface(child_name)
        else:
            Inspector.add_class_child(self, child, child_name, classdoc)

    def inspect_zope_interface(self, interface, interfacename):
        pass # etc...
"""        
