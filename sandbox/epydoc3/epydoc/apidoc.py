"""
Classes for encoding API documentation about Python programs.

Terminiology:
  - X{entity}: Anything that can be documented
  - X{value}: A Python object
  - X{variable}: A Python variable
  - X{argument}: An argument to a function

.. inheritancegraph:: APIDoc, VariableDoc, ValueDoc, etc..

 Architecture graph::

            +-----------+       
 python --> | Inspector |
 object     +-----------+
                  |
                  V
             +---------+      +--------+
  source --> | Shallow |      |  Full  | <-- source
   code      | Parser  |      | Parser |      code
             +---------+      +--------+
                      |        |
                      |        |
                      V        V
                   +---------------+
                   |  Name Finder  |
                   +---------------+
                           |
                           V
                  +------------------+
                  | Docstring Parser |
                  +------------------+
                           |
                           V
                      +---------+
                      | Writers |
                      +---------+

Blocks:
  - Inspector: creates a ValueDoc from a Python object
  - Shallow Parser: finds variable docstrings & imports

Stages:
  1. Create DocMap
  2. Run Inspector
     2a. Do inspection
     2b. Find a unique name for each object
  3. Run Parser
  4. Parse & process Docstrings
  5. Send to Writer...

- APIDoc: API documentation about *something*
  - DocstringAcceptingAPIDoc -- has docstring, descr, summary, metadata
    - VariableDoc -- contains ValueDoc, has name
    - ValueDoc -- has value, canonical dotted name
      - ModuleDoc
      - ClassDoc
      - RoutineDoc
      - PropertyDoc
  - ArgDoc -- an argument to a routine

But.. param can have a descr..  So why not just say that all APIDoc
objects *can* have a docstring, but some are unlikely to (eg function
arguments).

.. [XX] Better name for VariableOrValueDoc??

"""

# A sentinel is a unique value.
try: sentinel = object
except: sentinel = lambda:[]
sentinel = lambda:[]

import types, re

######################################################################
# Top level??
######################################################################

def pydoc(name):
    try:
        self.help(get_object(name))
    except:
        filename = find_filename(name)
        objdoc = DocInspector().parse(filename)
        
def help(object):
    # X
    objdoc = DocInspector().inspect(object)

    # Y
    ShallowParser().parse(objdoc)

    
    filename = find_filename(object)
    if filname is not None:
        ShallowParser.parse(filename)

def help(modules):
    for module in modules:
        inspected = []
        parsed = []
        try: inspected.append(inspector.inspect(module))
        except: parsed.append(parser.parse(module))

    #for valuedoc in inspected:
    #    parser.
        
    
######################################################################
# Documentation Graph
######################################################################

class DocCollection:
    """

    A set of objects that should be documented.
    
    """
    def __init__(self, *objects):
        """

        @param objects: The objects to document.  Can be actual
        objects or names. ??
          
        """
        
        
        self._docs = {}
        """Map from DottedName to apidoc"""

    def get(self, dotted_name, default=None):
        try: return self[dotted_name]
        except KeyError: return default

    def __getitem__(self, dotted_name):
        for i in range(len(dotted_name)-2, -1, -1):
            module_name = DottedName(dotted_name[:i])
            val = self._docs.get(module_name)
            if val is not None:
                for j in range(i, len(dotted_name)):
                    pass # ??? get child named foo.
                return val
        raise KeyError, str(dotted_name)

    def __setitem__(self, dotted_name, apidoc):
        self._docs[dotted_name] = apidoc
        
######################################################################
# Dotted Names
######################################################################
_IDENTIFIER_RE = re.compile('[a-zA-Z_]\w*(.[a-zA-Z_]\w*)*')
class DottedName:
    """
    The name of a Python object, specified as a list of identifiers.
    """
    def __init__(self, *identifiers):
        if len(identifiers) == 0:
            raise ValueError, 'Empty DottedName'
        self._identifiers = []
        for identifier in identifiers:
            if isinstance(identifier, DottedName):
                self._identifiers += identifier._identifiers
            elif isinstance(identifier, types.StringType):
                assert _IDENTIFIER_RE.match(identifier), 'Bad identifier'
                self._identifiers += identifier.split('.')
            else:
                assert 0, 'bad identifier: %r' % identifier
        self._identifiers = tuple(self._identifiers)

    def __repr__(self):
        return '.'.join(self._identifiers)

    def __getitem__(self, i):
        if isinstance(i, types.SliceType):
            return self._identifiers[i.start:i.stop]
        else:
            return self._identifiers[i]

    def __hash__(self):
        return hash(self._identifiers)

    def __cmp__(self, other):
        if not isinstance(other, DottedName): return -1
        return cmp(self._identifiers, other._identifiers)

    def __len__(self):
        return len(self._identifiers)

    def __contains__(self, other):
        return self._identifiers[len(other)] == other._identifiers
    
    def parent(self):
        if len(self._identifiers) == 1:
            return None
        else:
            return DottedName(self._identifiers[:-1])

######################################################################
# API Documentation Objects: Abstract Base Classes
######################################################################

class APIDoc:
    """
    API documentation information for a single docmentable item.  A
    X{documentable item} is anything that can be individually
    documented.  Currently, this includes variables, values, and
    function parameters.
    """
    def __init__(self, docstring=None):
        self.docstring = docstring
        """The item's docstring.
        @type: C{string}"""

        self.descr = None
        """A description of the item, extracted from its docstring.
        @type: L{ParsedDocstring}"""

        self.summary = None
        """A summary of the item, extracted from its docstring.
        @type: L{ParsedDocstring}"""

        self.metadata = {}
        """Metadata about the item, extracted from its docstring."""

    def referenced_apidocs(self): # [XX] ???
        """
        @return: A list of all APIDocs that are directly referenced by
        this APIDoc.  (E.g., children, base classes, etc.)
        """

    #////////////////////////////////////////////////////////////
    # String Representation (for debugging)
    #////////////////////////////////////////////////////////////

    _STR_FIELDS = ['docstring', 'descr', 'summary', 'metadata']
    """A list of the fields that should be printed by L{pp()}."""

    def __str__(self):
        return self.pp()
    
    def pp(self, doublespace=0, depth=2, exclude=[]):
        """
        @return: A string representation for this C{APIDoc}.
        @param doublespace: If true, then extra lines will be
            inserted to make the output more readable.
        @param depth: The maximum depth that pp will descend
            into descendent VarDocs.  To put no limit on
            depth, use C{depth=-1}.
        """
        if hasattr(self, '_cyclecheck') or depth == 0:
            if hasattr(self, 'name') and self.name is not None:
                return '%s...' % self.name
            else:
                return '...'
        self._cyclecheck = True

        if 'pyid' in exclude:
            s = self.__class__.__name__
        else:
            s = '%s 0x%x' % (self.__class__.__name__, id(self))

        # Only print non-empty fields:
        fields = [field for field in self._STR_FIELDS
                  if getattr(self, field) and field not in exclude]
        
        for field in fields:
            fieldval = getattr(self, field)
            if doublespace: s += '\n |'
            s += '\n +- %s' % field

            if isinstance(fieldval, types.ListType):
                s += self.__pp_list(fieldval, doublespace, depth,
                                    exclude, (field is fields[-1]))
            elif isinstance(fieldval, types.DictType):
                s += self.__pp_dict(fieldval, doublespace, 
                                    depth, exclude, (field is fields[-1]))
            elif isinstance(fieldval, APIDoc):
                s += self.__pp_apidoc(fieldval, doublespace, depth,
                                      exclude, (field is fields[-1]))
            else:
                s += ' = ' + self.__pp_val(fieldval, doublespace,
                                           depth, exclude)
                    
        del self._cyclecheck
        return s

    def __pp_list(self, items, doublespace, depth, exclude, is_last):
        line1 = (is_last and ' ') or '|'
        s = ''
        for item in items:
            line2 = ((item is items[-1]) and ' ') or '|'
            joiner = '\n %s  %s ' % (line1, line2)
            if doublespace: s += '\n %s  |' % line1
            s += '\n %s  +- ' % line1
            valstr = self.__pp_val(item, doublespace, depth, exclude)
            s += joiner.join(valstr.split('\n'))
        return s

    def __pp_dict(self, dict, doublespace, depth, exclude, is_last):
        items = dict.items()
        items.sort()
        line1 = (is_last and ' ') or '|'
        s = ''
        for item in items:
            line2 = ((item is items[-1]) and ' ') or '|'
            joiner = '\n %s  %s ' % (line1, line2)
            if doublespace: s += '\n %s  |' % line1
            s += '\n %s  +- ' % line1
            valstr = self.__pp_val(item[1], doublespace, depth, exclude)
            s += joiner.join(('%s => %s' % (item[0], valstr)).split('\n'))
        return s

    def __pp_apidoc(self, val, doublespace, depth, exclude, is_last):
        line1 = (is_last and ' ') or '|'
        s = ''
        if doublespace: s += '\n %s  |  ' % line1
        s += '\n %s  +- ' % line1
        joiner = '\n %s    ' % line1
        childstr = val.pp(doublespace, depth-1, exclude)
        return s + joiner.join(childstr.split('\n'))
        
    def __pp_val(self, val, doublespace, depth, exclude):
        if isinstance(val, APIDoc):
            return val.pp(doublespace, depth-1, exclude)
        else:
            valrepr = repr(val)
            if len(valrepr) < 40: return valrepr
            else: return valrepr[:37]+'...'

######################################################################
# Variable Documentation Objects
######################################################################

class VariableDoc(APIDoc):
    """
    API documentation information about a single Python variable.
    Each variable is uniquely identified by its dotted name.
    """
    _STR_FIELDS = (['name'] + APIDoc._STR_FIELDS +
                   ['valuedoc', 'is_imported', 'is_alias', 'is_instvar'])

    def __init__(self, name, valuedoc, is_imported='unknown',
                 is_alias='unknown', is_instvar=0, docstring=None):
        """Create a new C{VariableDoc}."""
        APIDoc.__init__(self, docstring=docstring)
        
        self.name = name
        """The variable's dotted name."""

        self.valuedoc = valuedoc
        """API documentation about the variable's value."""

        self.is_imported = is_imported
        """Is this variable's value defined in another module?"""

        self.is_instvar = is_instvar
        """Is this an instance variable?"""

        self.is_alias = is_alias
        """Is this an 'alias' variable?"""

        self.type = None
        """A description of the variable's expected type."""

        self.public = True # [XX] set based on name.
        """Should the variable be considered 'public'?"""

######################################################################
# Value Documentation Objects
######################################################################

class ValueDoc(APIDoc):
    """
    API documentation information about a single Python value.
    """
    _STR_FIELDS = (['dotted_name']+APIDoc._STR_FIELDS+
                   ['value', 'repr', 'type'])
    
    NO_VALUE = sentinel()
    """A unique object that is used as the value of L{ValueDoc._value}
    when the value is unknown."""
    
    def __init__(self, dotted_name=None, value=NO_VALUE, repr=None,
                 type=None):
        """Create a new C{ValueDoc}."""
        APIDoc.__init__(self)

        self.dotted_name = dotted_name
        """The value's canonical dotted name."""
        
        self.value = value
        """The python object described by this C{ValueDoc}."""

        self.repr = repr
        """A string representation of the value."""

        self.type = type
        """A description of the value's type."""

class NamespaceDoc(ValueDoc):
    """
    API documentation information about a singe Python namespace
    value.  (I.e., a module or a class).
    """
    _STR_FIELDS = ValueDoc._STR_FIELDS + ['children']

    def __init__(self, dotted_name=None):
        ValueDoc.__init__(self, dotted_name=dotted_name)

        self.children = {}
        """The contents of the namespace, encoded as a dictionary
        mapping from (short) names to C{VariableDoc}s.  This
        dictionary contains all names defined by the namespace,
        including imported and aliased variables.
        @type: C{dict} from C{string} to L{VariableDoc}"""

        self.groupnames = []
        """A list of the names of the groups, in sorted order."""

        self.groups = {}
        """The groups defined by the namespace's docstring, encoded as
        a dictionary mapping from group names to lists of
        C{VariableDoc}s.  The lists of C{VariableDoc}s are pre-sorted.
        @type: C{dict} from C{string} to (C{list} of L{VariableDoc})
        """

    def add_child(self, variabledoc):
        """
        Add the given C{VariableDoc} as a child of this namepsace.  If
        the namespace already defines a child with the same name, it
        will be replaced.
        """
        assert isinstance(variabledoc, VariableDoc)
        self.children[variabledoc.name] = variabledoc

    def get_children(self, group=None, doctype=None):
        # [XX] ignores groups right now.
        variabledocs = self.children.keys()
        if doctype is None:
            return variabledocs
        elif doctype is ValueDoc:
            # Group None's with ValueDoc's.
            return [variabledoc for variabledoc in variabledocs if
                    variabledoc.valuedoc is None or
                    variabledoc.valuedoc.__class__ is doctype]
        else:
            return [variabledoc for variabledoc in variabledocs if
                    variabledoc.valuedoc is not None and
                    variabledoc.valuedoc.__class__ is doctype]
    

class ModuleDoc(NamespaceDoc):
    """
    API documentation information about a single module.
    """
    _STR_FIELDS = (NamespaceDoc._STR_FIELDS +
                   ['package', 'docformat', 'public_names'])
    
    def __init__(self, dotted_name=None):
        """Create a new C{ModuleDoc}."""
        NamespaceDoc.__init__(self, dotted_name=dotted_name)

        self.package = None
        """API documentation for the module's containing package.
        @type: L{ModuleDoc}"""

        self.docformat = None
        """The markup language used by docstrings in this module.
        @type: C{string}"""

        self.public_names = None
        """A list of the names of ..., extracted from __all__
        @type: C{string}"""

class ClassDoc(NamespaceDoc):
    """
    API documentation information about a single class.
    """
    _STR_FIELDS = NamespaceDoc._STR_FIELDS + ['bases', 'subclasses']
    
    def __init__(self):
        """Create a new C{ClassDoc}."""
        NamespaceDoc.__init__(self)

        self.bases = []
        """API documentation for the class's base classes.
        @type: C{list} of L{ClassDoc}"""

        self.subclasses = []
        """API documentation for the class's known subclasses.
        @type: C{list} of L{ClassDoc}"""

class RoutineDoc(ValueDoc):
    """
    API documentation information about a single routine.
    """
    _STR_FIELDS = (ValueDoc._STR_FIELDS +
                   ['args', 'vararg', 'kwarg', 'returns', 'overrides'])
                   
    def __init__(self, args=None, vararg=None, kwarg=None, returns=None,
                 overrides=None):
        """Create a new C{FuncDoc}."""
        ValueDoc.__init__(self)

        self.args = args
        """API documentation for the routine's positional arguments.
        @type: C{list} of L{ArgDoc}"""

        self.vararg = vararg
        """API documentation for the routine's vararg argument, or
        C{None} if it has no vararg argument.
        @type: L{ArgDoc}"""

        self.kwarg = kwarg
        """API documentation for the routine's keyword argument, or
        C{None} if it has no keyword argument.
        @type: L{ArgDoc}"""

        self.returns = returns
        """A description of the value returned by this routine.
        @type: L{ArgDoc}? or C{string}?"""
        
        self.overrides = overrides
        """API documentation for the routine overriden by this
        routine.
        @type: L{RoutineDoc}"""

class FunctionDoc(RoutineDoc): pass
class InstanceMethodDoc(RoutineDoc): pass
class ClassMethodDoc(RoutineDoc): pass
class StaticMethodDoc(RoutineDoc): pass

def cm_doc_from_routine_doc(routine_doc):
    import copy
    cm_doc = copy.copy(routine_doc)
    cm_doc.__class__ = ClassMethodDoc
    cm_doc.dotted_name = None
    return cm_doc

def sm_doc_from_routine_doc(routine_doc):
    import copy
    sm_doc = copy.copy(routine_doc)
    sm_doc.__class__ = StaticMethodDoc
    sm_doc.dotted_name = None
    return sm_doc

class PropertyDoc(ValueDoc):
    """
    API documentation information about a single property.
    """
    _STR_FIELDS = (ValueDoc._STR_FIELDS +['fget', 'fset', 'fdel'])
                   
    def __init__(self):
        """Create a new C{PropertyDoc}."""
        ValueDoc.__init__(self)

        self.fget = None
        """API documentation for the property's get function.
        @type: L{RoutineDoc}"""
        
        self.fset = None
        """API documentation for the property's set function.
        @type: L{RoutineDoc}"""
        
        self.fdel = None
        """API documentation for the property's delete function.
        @type: L{RoutineDoc}"""
        
######################################################################
## Argument Documentation Objects
######################################################################
        
class ArgDoc(APIDoc):
    """
    API documentation for a single argument to a routine.
    """
    _STR_FIELDS = (APIDoc._STR_FIELDS +
                   ['name', 'default', 'type'])
                   
    def __init__(self, name=None, default=None, type=None):
        """Create a new C{ArgDoc}"""
        APIDoc.__init__(self)

        if isinstance(name, types.ListType): name = tuple(name)
        self.name = name
        """The argument's name."""

        self.default = default
        """API documentation for the argument's default value.
        @type: L{ValueDoc}"""

        self.type = type
        """A description of the argument's expected type.
        @type: L{ParsedDocstring}"""
        
    
