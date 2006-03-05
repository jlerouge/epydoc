# epydoc -- API Documentation Classes
#
# Copyright (C) 2005 Edward Loper
# Author: Edward Loper <edloper@loper.org>
# URL: <http://epydoc.sf.net>
#
# $Id$

"""
Classes for encoding API documentation about Python programs.

These classes are used as a common representation for combining
information derived from inspection and from parsing.

The API documentation for a Python program is encoded using a graph of
L{APIDoc} objects, each of which encodes information about a single
Python variable or value.  C{APIDoc} has two direct subclasses:
L{VariableDoc}, for documenting variables; and L{ValueDoc}, for
documenting values.  The C{ValueDoc} class is subclassed further, to
define the different pieces of information that should be recorded
about each value type (See the documentation for L{ValueDoc} for a
complete list).

The distinction between variables and values is intentionally kept
explicit.  This allows us to distinguish information about a variable
itself (such as whether it should be considered 'public' in its
containing namespace) from information about the value it contains
(such as what type the value has).  This distinction is also important
because several variables can contain the same value: each variable
should be described by a separate C{VariableDoc}; but we only need one
C{ValueDoc}, since they share a single value.
"""
__docformat__ = 'epytext en'

######################################################################
## Imports
######################################################################

import types, re
from sets import Set
from epydoc import log
import epydoc

# Backwards compatibility imports:
try: sorted
except NameError: from epydoc.util import py_sorted as sorted

######################################################################
# Dotted Names
######################################################################

class DottedName:
    """
    A sequence of identifiers, separated by periods, used to name a
    Python variable, value, or argument.  The identifiers that make up
    a dotted name can be accessed using the indexing operator:

        >>> name = DottedName('epydoc', 'api_doc', 'DottedName')
        >>> print name
        epydoc.apidoc.DottedName
        >>> name[1]
        'api_doc'
    """
    UNREACHABLE = "??"
    _IDENTIFIER_RE = re.compile(r"[a-zA-Z_]\w*(-script)?'?"
                                r"(\.[a-zA-Z_]\w*'?)*$" + "|" +
                                re.escape(UNREACHABLE)+
                                r"(\.[a-zA-Z_]\w*'?)*(-\d+)?$")
    
    def __init__(self, *pieces):
        """
        Construct a new dotted name from the given sequence of pieces,
        each of which can be either a C{string} or a C{DottedName}.
        Each piece is divided into a sequence of identifiers, and
        these sequences are combined together (in order) to form the
        identifier sequence for the new C{DottedName}.  If a piece
        contains a string, then it is divided into substrings by
        splitting on periods, and each substring is checked to see if
        it is a valid identifier.
        """
        if len(pieces) == 0:
            raise ValueError, 'Empty DottedName'
        self._identifiers = []
        for piece in pieces:
            if isinstance(piece, DottedName):
                self._identifiers += piece._identifiers
            elif isinstance(piece, basestring):
                if not self._IDENTIFIER_RE.match(piece):
                    raise ValueError('Bad identifier %r' % (piece,))
                self._identifiers += piece.split('.')
            else:
                raise ValueError('Bad identifier %r' % (piece,))
        self._identifiers = tuple(self._identifiers)

    def __repr__(self):
        idents = [`ident` for ident in self._identifiers]
        return 'DottedName(' + ', '.join(idents) + ')'

    def __str__(self):
        """
        Return the dotted name as a string formed by joining its
        identifiers with periods:

            >>> print DottedName('epydoc', 'api_doc', DottedName')
            epydoc.apidoc.DottedName
        """
        return '.'.join(self._identifiers)

    def __add__(self, other):
        """
        Return a new C{DottedName} whose identifier sequence is formed
        by adding C{other}'s identifier sequence to C{self}'s.
        """
        return DottedName(self, other)

    def __getitem__(self, i):
        """
        Return the C{i}th identifier in this C{DottedName}.
        """
        if isinstance(i, types.SliceType):
            return self._identifiers[i.start:i.stop]
        else:
            return self._identifiers[i]

    def __hash__(self):
        return hash(self._identifiers)

    def __cmp__(self, other):
        """
        Compare this dotted name to C{other}.  Two dotted names are
        considered equal if their identifier subsequences are equal.
        """
        if other is None: return -1
        if not isinstance(other, DottedName):
            return -1
        return cmp(self._identifiers, other._identifiers)

    def __len__(self):
        """
        Return the number of identifiers in this dotted name.
        """
        return len(self._identifiers)

    def container(self):
        """
        Return the DottedName formed by removing the last identifier
        from this dotted name's identifier sequence.  If this dotted
        name only has one name in its identifier sequence, return
        C{None} instead.
        """
        if len(self._identifiers) == 1:
            return None
        else:
            return DottedName(*self._identifiers[:-1])

    def dominates(self, name):
        return self._identifiers == name._identifiers[:len(self)]

######################################################################
# UNKNOWN Value
######################################################################

class _Sentinel:
    """
    A unique value that won't compare equal to any other value.  This
    class is used to create L{UNKNOWN}.
    """
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return '<%s>' % self.name
    def __nonzero__(self):
        raise ValueError('Sentinel value <%s> can not be used as a boolean' %
                         self.name)

UNKNOWN = _Sentinel('UNKNOWN')
"""A special value used to indicate that a given piece of
information about an object is unknown.  This is used as the
default value for all instance variables."""

######################################################################
# API Documentation Objects: Abstract Base Classes
######################################################################

class APIDoc(object):
    """
    API documentation information for a single element of a Python
    program.  C{APIDoc} itself is an abstract base class; subclasses
    are used to specify what information should be recorded about each
    type of program element.  In particular, C{APIDoc} has two direct
    subclasses, C{VariableDoc} for documenting variables and
    C{ValueDoc} for documenting values; and the C{ValueDoc} class is
    subclassed further for different value types.

    Each C{APIDoc} subclass specifies the set of attributes that
    should be used to record information about the corresponding
    program element type.  The default value for each attribute is
    stored in the class; these default values can then be overridden
    with instance variables.  Most attributes use the special value
    L{UNKNOWN} as their default value, to indicate that the correct
    value for that attribute has not yet been determined.  This makes
    it easier to merge two C{APIDoc} objects that are documenting the
    same element (in particular, to merge information about an element
    that was derived from parsing with information that was derived
    from inspection).

    For all attributes with boolean values, use only the constants
    C{True} and C{False} to designate true and false.  In particular,
    do I{not} use other values that evaluate as true or false, such as
    C{2} or C{()}.  This restriction makes it easier to handle
    C{UNKNOWN} values.  For example, to test if a boolean attribute is
    C{True} or C{UNKNOWN}, use 'C{attrib in (True, UNKNOWN)}' or
    'C{attrib is not False}'.
    
    @ivar docstring: The documented item's docstring.
    @type docstring: C{string} or C{None}
    @ivar descr: A description of the documented item, extracted from
        its docstring.
    @type descr: L{ParsedDocstring<epydoc.markup.ParsedDocstring>}
    @ivar summary: A summary description of the documented item,
        extracted from its docstring.
    @type summary: L{ParsedDocstring<epydoc.markup.ParsedDocstring>}
    @ivar metadata: Metadata about the documented item, extracted from
        fields in its docstring.  This metadata is encoded as a
        dictionary whose keys are cannonical field tag names (such as
        C{'author'} or tuples of field tag name and argument value
        (such as C{('todo', '1.2')}.  The metadata dictionary's values
        are lists of L{ParsedDocstring<epydoc.markup.ParsedDocstring>}
        segments, each corresponding to the body of a single docstring
        field.
    @type metadata: C{dict}
    @ivar extra_docstring_fields: A list of new docstring fields
        tags that are defined by the documented item's docstring.
        These new field tags can be used by this item or by any
        item it contains.
    @type extra_docstring_fields: L{DocstringField
        <epydoc.docstringparser.DocstringField>}
    """
    docstring = UNKNOWN
    docstring_lineno = UNKNOWN # [xx] document!
    descr = UNKNOWN
    summary = UNKNOWN
    metadata = UNKNOWN
    extra_docstring_fields = UNKNOWN
    
    def __init__(self, **kwargs):
        """
        Construct a new C{APIDoc} object.  Keyword arguments may be
        used to initialize the new C{APIDoc}'s attributes.
        
        @raise TypeError: If a keyword argument is specified that does
            not correspond to a valid attribute for this (sub)class of
            C{APIDoc}.
        """
        for key in kwargs:
            if not hasattr(self, key):
                raise TypeError('%s got unexpected arg %r' %
                                (self.__class__.__name__, key))
        self.__dict__.update(kwargs)

    def _debug_setattr(self, attr, val):
        """
        Modify an C{APIDoc}'s attribute.

        @raise AttributeError: If C{attr} is not a valid attribute for
            this (sub)class of C{APIDoc}.
        """
        # Don't intercept special assignments like __class__, or
        # assignments to private variables.
        if attr.startswith('_'):
            return object.__setattr__(self, attr, val)
        if not hasattr(self, attr):
            raise AttributeError('%s does not define attribute %r' %
                            (self.__class__.__name__, attr))
        self.__dict__[attr] = val

    if epydoc.DEBUG:
        __setattr__ = _debug_setattr

    def __repr__(self):
       return '<%s>' % self.__class__.__name__
    
    def pp(self, doublespace=0, depth=5, exclude=(), include=()):
        """
        Return a pretty-printed string representation for the
        information contained in this C{APIDoc}.
        """
        return pp_apidoc(self, doublespace, depth, exclude, include)
    
    def __str__(self):
        return self.pp()

    def specialize_to(self, cls):
        if not issubclass(cls, self.__class__):
            raise ValueError, 'xxx'
        self.__class__ = cls
        
        # DO THIS [xx]?
        self.__init__(**self.__dict__)

    # [xx] consider making them un-hashable??
    __has_been_hashed = False
    def __hash__(self):
        self.__has_been_hashed = True
        return id(self.__dict__)

    def __cmp__(self, other):
        if not isinstance(other, APIDoc): return -1
        if self.__dict__ is other.__dict__: return 0
        else: return -1

    __mergeset = None
    def merge_and_overwrite(self, other):
        """
        Combine C{self} and C{other} into a X{merged object}, such
        that any changes made to one will affect the other.  Any
        attributes that C{other} had before merging will be discarded.
        This is accomplished by copying C{self.__dict__} over
        C{other.__dict__} and C{self.__class__} over C{other.__class__}.

        Care must be taken with this method, since it modifies the
        hash value of C{other}.  To help avoid the problems that this
        can cause, C{merge_and_overwrite} will raise an exception if
        C{other} has ever been hashed.

        @return: C{self}
        @raise ValueError: If C{other} has ever been hashed.
        """
        # If we're already merged, then there's nothing to do.
        if (self.__dict__ is other.__dict__ and
            self.__class__ is other.__class__): return self
            
        if other.__has_been_hashed:
            pass # [XX !!]
#             raise ValueError("Can only merge with APIDoc objects that "
#                              "have never been hashed")

        # If other was itself already merged with anything,
        # then we need to merge those too.
        a,b = (self.__mergeset, other.__mergeset)
        mergeset = (self.__mergeset or [self]) + (other.__mergeset or [other])
        other.__dict__.clear()
        for apidoc in mergeset:
            #if apidoc is self: pass
            apidoc.__class__ = self.__class__
            apidoc.__dict__ = self.__dict__
        self.__mergeset = mergeset
        # Sanity chacks.
        assert self in mergeset and other in mergeset
        for apidoc in mergeset:
            assert apidoc.__dict__ is self.__dict__
        # Return self.
        return self

######################################################################
# Variable Documentation Objects
######################################################################

class VariableDoc(APIDoc):
    """
    API documentation information about a single Python variable.

    @note: The only time a C{VariableDoc} will have its own docstring
    is if that variable was created using an assignment statement, and
    that assignment statement had a docstring-comment or was followed
    by a pseudo-docstring.

    @ivar container: API documentation for the namespace that contains
        this variable.
    @type container: L{ValueDoc}
    @ivar name: The name of this variable in its containing namespace.
    @type name: C{str}
    @ivar value: API documentation about this variable's value.
    @type value: L{ValueDoc}
    
    @ivar is_imported: Is this variable's value defined in another module?
        (Exception: variables that are explicitly included in __all__
        are considered non-imported, even if they are in fact imported.)
    @type is_imported: C{bool}
    @ivar is_instvar: Is this an instance variable?
    @type is_instvar: C{bool}
    @ivar is_alias: Is this an 'alias' variable?
    @type is_alias: C{bool}
    @ivar is_public: Is the variable considered 'public'?
    @type is_public: C{bool}

    @ivar overrides: The API documentation for the variable that is
        overridden by this variable (only applicable if the containing
        namespace is a class).  If the containing namespace is not a
        class, then C{overrides} should be C{None}.
    @type overrides: L{VariableDoc} or C{None}
    
    @ivar type_descr: A description of the variable's expected type,
        extracted from its docstring.
    @type type_descr: L{ParsedDocstring<epydoc.markup.ParsedDocstring>}
    """
    container = UNKNOWN
    name = UNKNOWN
    value = UNKNOWN
    is_imported = UNKNOWN
    is_instvar = UNKNOWN
    is_alias = UNKNOWN
    is_public = UNKNOWN
    overrides = UNKNOWN #: rename -- don't use a verb.
    type_descr = UNKNOWN
    
    def __init__(self, **kwargs):
        APIDoc.__init__(self, **kwargs)
        if self.is_public is UNKNOWN and self.name is not UNKNOWN:
            self.is_public = (not self.name.startswith('_') or
                              self.name.endswith('_'))
        
    def __repr__(self):
        if (self.container is not UNKNOWN and
            self.container.canonical_name is not UNKNOWN):
            return '<%s %s.%s>' % (self.__class__.__name__,
                                   self.container.canonical_name, self.name)
        if self.name is not UNKNOWN:
            return '<%s %s>' % (self.__class__.__name__, self.name)
        else:                     
            return '<%s>' % self.__class__.__name__

    def _get_canonical_name(self):
        if self.container is UNKNOWN:
            raise ValueError, `self`
        if (self.container is UNKNOWN or
            self.container.canonical_name is UNKNOWN):
            return UNKNOWN
        else:
            return self.container.canonical_name + self.name
    canonical_name = property(_get_canonical_name, doc="""
    A read-only property that can be used to get the variable's
    canonical name.  This is formed by taking the varaible's
    container's cannonical name, and adding the variable's name
    to it.""")

######################################################################
# Value Documentation Objects
######################################################################

class ValueDoc(APIDoc):
    """
    API documentation information about a single Python value.

    @ivar canonical_name: A dotted name that serves as a unique
        identifier for this C{ValueDoc}'s value.  If the value can be
        reached using a single sequence of identifiers (given the
        appropriate imports), then that sequence of identifiers is
        used as its canonical name.  If the value can be reached by
        multiple sequences of identifiers (i.e., if it has multiple
        aliases), then one of those sequences of identifiers is used.
        If the value cannot be reached by any sequence of identifiers
        (e.g., if it was used as a base class but then its variable
        was deleted), then its canonical name will start with C{'??'}.
        If necessary, a dash followed by a number will be appended to
        the end of a non-reachable identifier to make its canonical
        name unique.

        When possible, canonical names are chosen when new
        C{ValueDoc}s are created.  However, this is sometimes not
        possible.  If a canonical name can not be chosen when the
        C{ValueDoc} is created, then one will be assigned during
        indexing.
    @type canonical_name: L{DottedName}

    @ivar pyval: A pointer to the actual Python object described by
        this C{ValueDoc}.
    @type pyval: Python object
    @ivar ast: The syntax tree of the Python source code that was used
        to create this value.
    @type ast: C{list}
    @ivar repr: A text representation of this value.
    @type repr: C{unicode}
    @ivar type: API documentation for the value's type
    @type type: L{ValueDoc}
    @ivar imported_from: If C{imported_from} is not None, then this
        value was imported from another file.  C{imported_from} is
        the dotted name of the variable that this value was imported
        from.  If that variable is documented, then its C{value} may
        contain more complete API documentation about this value.  The
        C{imported_from} attribute is used by the source code parser
        to link imported values to their source values.  When
        possible, these alias C{ValueDoc}s are replaced by the
        imported value's C{ValueDoc} during indexing.
    """
    canonical_name = UNKNOWN
    pyval = UNKNOWN
    ast = UNKNOWN
    repr = UNKNOWN
    type = UNKNOWN # [XX] NOT USED YET?? FOR PROPERTY??
    imported_from = None

    toktree = UNKNOWN # from the tokenizing docparser.
    
    def __repr__(self):
        if self.canonical_name is not UNKNOWN:
            return '<%s %s>' % (self.__class__.__name__, self.canonical_name)
        elif self.repr is not UNKNOWN:
            return '<%s %s>' % (self.__class__.__name__, self.repr)
        else:                     
            return '<%s>' % self.__class__.__name__

    def valdoc_links(self):
        return []
    def vardoc_links(self):
        return []

def reachable_valdocs(*root):
    """
    @return: The set of all C{ValueDoc}s that are directly or
    indirectly reachable from the root set.  In particular, this set
    contains all C{ValueDoc}s that can be reached from the root set by
    following I{any} sequence of pointers to C{ValueDoc}s or
    C{VariableDoc}s.
    """
    val_queue = list(root)
    val_set = Set()
    while val_queue:
        val_doc = val_queue.pop()
        val_set.add(val_doc)
        val_queue.extend([v for v in val_doc.valdoc_links()
                          if v not in val_set])
        val_queue.extend([v.value for v in val_doc.vardoc_links()
                          if (v.value not in (None, UNKNOWN) and
                              v.value not in val_set)])
    return val_set

def contained_valdocs(*root):
    """
    @return: The set of all C{ValueDoc}s that are directly or
    indirectly contained in the root set.  In particular, this set
    contains all C{ValueDoc}s that can be reached from the root set by
    following only the C{ValueDoc} pointers defined by non-imported
    C{VariableDoc}s.  This will always be a subset of
    L{reachable_valdocs}.
    """
    val_queue = list(root)
    val_set = Set()
    while val_queue:
        val_doc = val_queue.pop()
        val_set.add(val_doc)
        val_queue.extend([v.value for v in val_doc.vardoc_links()
                          if (v.value not in (None, UNKNOWN) and 
                              v.value not in val_set and
                              v.is_imported != True)])
    return val_set

        
    
class NamespaceDoc(ValueDoc):
    """
    API documentation information about a singe Python namespace
    value.  (I.e., a module or a class).

    @ivar variables: The contents of the namespace, encoded as a
        dictionary mapping from identifiers to C{VariableDoc}s.  This
        dictionary contains all names defined by the namespace,
        including imported variables, aliased variables, and variables
        inherited from base classes (once L{DocInheriter
        <epydoc.docinheriter.DocInheriter>} has added them).
    @type variables: C{dict} from C{string} to L{VariableDoc}
    @ivar sorted_variables: A list of all variables defined by this
        namespace, in sorted order.  The elements of this list should
        exactly match the values of L{variables}.  The sort order for
        this list is defined as follows:
        
          - Any variables listed in a C{@sort} docstring field are
            listed in the order given by that field.
          - These are followed by any variables that were found while
            parsing the source code, in the order in which they were
            defined in the source file.
          - Finally, any remaining variables are listed in
            alphabetical order.
            
    @type sorted_variables: C{list} of L{VariableDoc}
    @ivar group_names: A list of the names of the group, in the order
        in which they should be listed.  The first element of this
        list is always the special group name C{''}, which is used for
        variables that do not belong to any group.
    @type group_names: C{list} of C{string}
    @ivar groups: The groups defined by the namespace's docstring,
        encoded as a dictionary mapping from group names to lists of
        C{VariableDoc}s.  The lists of C{VariableDoc}s are pre-sorted.
        The key C{''} is used for variables that do not belong to any
        other group.
    @type groups: C{dict} from C{string} to (C{list} of L{VariableDoc})
    """
    variables = UNKNOWN
    sorted_variables = UNKNOWN
    group_names = UNKNOWN
    groups = UNKNOWN
    group_specs = UNKNOWN #: list of (groupname, (identnames))
    sort_spec = UNKNOWN #: list of names

    def __init__(self, **kwargs):
        kwargs.setdefault('variables', {})
        APIDoc.__init__(self, **kwargs)
        assert self.variables != UNKNOWN

    def valdoc_links(self):
        return []
    def vardoc_links(self):
        return self.variables.values()

    def init_sorted_variables(self):
        """
        Initialize the L{sorted_variables} attribute, based on the
        L{variables} and L{sort_spec} attributes.  This should usually
        be called after all variables have been added to C{variables}
        (including any inherited variables for classes).  
        """
        unsorted = self.variables.copy()
        self.sorted_variables = []
    
        # Add any variables that are listed in sort_spec
        if self.sort_spec is not UNKNOWN:
            for ident in self.sort_spec:
                var_doc = unsorted.pop(ident, None)
                if var_doc is not None:
                    self.sorted_variables.append(var_doc)
                elif '*' in ident:
                    regexp = re.compile('^%s$' % ident.replace('*', '(.*)'))
                    # sort within matching group?
                    for name, var_doc in unsorted.items():
                        if regexp.match(name):
                            self.sorted_variables.append(var_doc)
                            unsorted.remove(var_doc)
    
        # Add any remaining variables in alphabetical order.
        var_docs = unsorted.items()
        var_docs.sort()
        for name, var_doc in var_docs:
            self.sorted_variables.append(var_doc)

    def init_groups(self):
        """
        Initialize the L{groups} attribute, based on the
        L{sorted_variables} and L{group_specs} attributes.
        """
        if self.sorted_variables == UNKNOWN:
            self.init_sorted_variables
        assert len(self.sorted_variables) == len(self.variables)
        
        self.group_names = [''] + [n for (n,vs) in self.group_specs]
        self.groups = {}
        
        # Make the common case fast:
        if len(self.group_names) == 1:
            self.groups[''] = self.sorted_variables
            return
    
        for group in self.group_names:
            self.groups[group] = []
    
        # Create a mapping from elt -> group name.
        varname2groupname = {}
        regexp_groups = []
    
        for group_name, var_names in self.group_specs:
            for var_name in var_names:
                if '*' not in var_name:
                    varname2groupname[var_name] = group_name
                else:
                    var_name_re = '^%s$' % var_name.replace('*', '(.*)')
                    var_name_re = re.compile(var_name_re)
                    regexp_groups.append( (group_name, var_name_re) )
    
        # Use the elt -> group name mapping to put each elt in the
        # right group.
        for var_doc in self.sorted_variables:
            group_name = varname2groupname.get(var_doc.name, '')
            self.groups[group_name].append(var_doc)
    
        # Handle any regexp groups, by moving elements from the
        # ungrouped list to the appropriate group.
        ungrouped = self.groups['']
        for (group_name, regexp) in regexp_groups:
            for i in range(len(ungrouped)-1, -1, -1):
                elt = ungrouped[i]
                if regexp.match(elt.name):
                    self.groups[group_name].append(elt)
                    del ungrouped[i]
    
        # [xx] check for empty groups???
        
        
        
    
class ModuleDoc(NamespaceDoc):
    """
    API documentation information about a single module.

    @ivar package: API documentation for the module's containing package.
    @type package: L{ModuleDoc}
    @ivar docformat: The markup language used by docstrings in this module.
    @type docformat: C{string}
    @ivar submodules: Modules contained by this module (if this module
        is a package).  (Note: on rare occasions, a module may have a
        submodule that is shadowed by a variable with the same name.)
    @ivar filename: The name of the file that defines the module.
    @type filename: C{string}
    """
    package = UNKNOWN
    docformat = UNKNOWN
    submodules = UNKNOWN
    is_package = UNKNOWN
    filename = UNKNOWN
    path = UNKNOWN

    def valdoc_links(self):
        val_docs = []
        if self.package not in (None, UNKNOWN): val_docs.append(self.package)
        if self.submodules not in (None, UNKNOWN): val_docs += self.submodules
        return val_docs
    def vardoc_links(self):
        return self.variables.values()

    def select_variables(self, group=None, value_type=None, public=None,
                         imported=None):
        """
        Return a specified subset of this module's L{sorted_variables}
        list.  If C{value_type} is given, then only return variables
        whose values have the specified type.  If C{group} is given,
        then only return variables that belong to the specified group.

        @require: The L{sorted_variables} and L{groups} attributes
            must be initialized before this method can be used.  See
            L{init_sorted_variables()} and L{init_groups()}.

        @param value_type: A string specifying the value type for
            which variables should be returned.  Valid values are:
              - 'class' - variables whose values are classes or types.
              - 'function' - variables whose values are functions.
              - 'other' - variables whose values are not classes,
                 exceptions, types, or functions.
        @type value_type: C{string}
        
        @param group: The name of the group for which variables should
            be returned.  A complete list of the groups defined by
            this C{ModuleDoc} is available in the L{group_names}
            instance variable.  The first element of this list is
            always the special group name C{''}, which is used for
            variables that do not belong to any group.
        @type group: C{string}
        """
        if self.sorted_variables == UNKNOWN or self.groups == UNKNOWN:
            raise ValueError('sorted_variables and groups must be '
                             'initialized first.')
        
        if group is None: var_list = self.sorted_variables
        else: var_list = self.groups[group]

        # Public/private filter (Count UNKNOWN as public)
        if public is True:
            var_list = [v for v in var_list if v.is_public is not False]
        elif public is False:
            var_list = [v for v in var_list if v.is_public is False]

        # Imported filter (Count UNKNOWN as non-imported)
        if imported is True:
            var_list = [v for v in var_list if v.is_imported is True]
        elif imported is False:
            var_list = [v for v in var_list if v.is_imported is not True]

        if value_type is None:
            return var_list
        elif value_type == 'class':
            return [var_doc for var_doc in var_list
                    if (isinstance(var_doc.value, ClassDoc))]
        elif value_type == 'function':
            return [var_doc for var_doc in var_list
                    if isinstance(var_doc.value, RoutineDoc)]
        elif value_type == 'other':
            return [var_doc for var_doc in var_list
                    if not isinstance(var_doc.value,
                                      (ClassDoc, RoutineDoc))]
        else:
            raise ValueError('Bad value type %r' % value_type)

class ClassDoc(NamespaceDoc):
    """
    API documentation information about a single class.

    @ivar bases: API documentation for the class's base classes.
    @type bases: C{list} of L{ClassDoc}
    @ivar subclasses: API documentation for the class's known subclasses.
    @type subclasses: C{list} of L{ClassDoc}
    """
    bases = UNKNOWN
    subclasses = UNKNOWN

    def valdoc_links(self):
        val_docs = []
        if self.bases not in (None, UNKNOWN): val_docs += self.bases
        if self.subclasses not in (None, UNKNOWN): val_docs += self.subclasses
        return val_docs
    def vardoc_links(self):
        return self.variables.values()
    
    def is_type(self):
        if self.canonical_name == DottedName('type'): return True
        if self.bases is UNKNOWN: return False
        for base in self.bases:
            if isinstance(base, ClassDoc) and base.is_type():
                return True
        return False
    
    def is_exception(self):
        if self.canonical_name == DottedName('Exception'): return True
        if self.bases is UNKNOWN: return False
        for base in self.bases:
            if isinstance(base, ClassDoc) and base.is_exception():
                return True
        return False
    
    def is_newstyle_class(self):
        if self.canonical_name == DottedName('object'): return True
        if self.bases is UNKNOWN: return False
        for base in self.bases:
            if isinstance(base, ClassDoc) and base.is_newstyle_class():
                return True
        return False

    def mro(self):
        if self.is_newstyle_class():
            return self._c3_mro()
        else:
            return self._dfs_bases([], Set())
        
    def _dfs_bases(self, mro, seen):
        if self in seen: return mro
        mro.append(self)
        seen.add(self)
        if self.bases is not UNKNOWN:
            for base in self.bases:
                if isinstance(base, ClassDoc):
                    base._dfs_bases(mro, seen)
                elif base.imported_from is not UNKNOWN:
                    log.info("No information available for base %r" % base)
                else:
                   log.warning("While calculating the MRO for %r, encountered "
                               "a base that's not a class: %r" % (self, base))
        return mro

    def _c3_mro(self):
        """
        Compute the class precedence list (mro) according to C3.
        @seealso: U{http://www.python.org/2.3/mro.html}
        """
        return self._c3_merge([[self]] +
                              map(ClassDoc._c3_mro, self.bases) +
                              [list(self.bases)])

    def _c3_merge(self, seqs):
        """
        Helper function for L{_c3_mro}.
        """
        res = []
        while 1:
          nonemptyseqs=[seq for seq in seqs if seq]
          if not nonemptyseqs: return res
          for seq in nonemptyseqs: # find merge candidates among seq heads
              cand = seq[0]
              nothead=[s for s in nonemptyseqs if cand in s[1:]]
              if nothead: cand=None #reject candidate
              else: break
          if not cand: raise "Inconsistent hierarchy"
          res.append(cand)
          for seq in nonemptyseqs: # remove cand
              if seq[0] == cand: del seq[0]
    
    def select_variables(self, group=None, value_type=None,
                         inherited=None, public=None, imported=None):
        """
        Return a specified subset of this class's L{sorted_variables}
        list.  If C{value_type} is given, then only return variables
        whose values have the specified type.  If C{group} is given,
        then only return variables that belong to the specified group.
        If C{inherited} is True, then only return inherited variables;
        if C{inherited} is False, then only return local variables.

        @require: The L{sorted_variables} and L{groups} attributes
            must be initialized before this method can be used.  See
            L{init_sorted_variables()} and L{init_groups()}.

        @param value_type: A string specifying the value type for
            which variables should be returned.  Valid values are:
              - 'instancemethod' - variables whose values are
                instance methods.
              - 'classmethod' - variables whose values are class
                methods.
              - 'staticmethod' - variables whose values are static
                methods.
              - 'properties' - variables whose values are properties.
              - 'class' - variables whose values are nested classes
                (including exceptions and types).
              - 'instancevariable' - instance variables.  This includes
                any variables that are explicitly marked as instance
                variables with docstring fields; and variables with
                docstrings that are initialized in the constructor.
              - 'classvariable' - class variables.  This includes any
                variables that are not included in any of the above
                categories.
        @type value_type: C{string}
        
        @param group: The name of the group for which variables should
            be returned.  A complete list of the groups defined by
            this C{ClassDoc} is available in the L{group_names}
            instance variable.  The first element of this list is
            always the special group name C{''}, which is used for
            variables that do not belong to any group.
        @type group: C{string}

        @param inherited: If C{None}, then return both inherited and
            local variables; if C{True}, then return only inherited
            variables; if C{False}, then return only local variables.
        """
        if self.sorted_variables == UNKNOWN or self.groups == UNKNOWN:
            raise ValueError('sorted_variables and groups must be '
                             'initialized first.')
        
        if group is None: var_list = self.sorted_variables
        else: var_list = self.groups[group]

        # Public/private filter (Count UNKNOWN as public)
        if public is True:
            var_list = [v for v in var_list if v.is_public is not False]
        elif public is False:
            var_list = [v for v in var_list if v.is_public is False]

        # Inherited filter (Count UNKNOWN as non-inherited)
        if inherited is None: pass
        elif inherited:
            var_list = [v for v in var_list if v.container != self]
        else:
            var_list = [v for v in var_list if v.container == self ]

        # Imported filter (Count UNKNOWN as non-imported)
        if imported is True:
            var_list = [v for v in var_list if v.is_imported is True]
        elif imported is False:
            var_list = [v for v in var_list if v.is_imported is not True]
        
        if value_type is None:
            return var_list
        elif value_type == 'method':
            return [var_doc for var_doc in var_list
                    if (isinstance(var_doc.value, RoutineDoc) and
                        var_doc.is_instvar in (False, UNKNOWN))]
        elif value_type == 'instancemethod':
            return [var_doc for var_doc in var_list
                    if (isinstance(var_doc.value, RoutineDoc) and
                        not isinstance(var_doc.value, ClassMethodDoc) and
                        not isinstance(var_doc.value, StaticMethodDoc) and
                        var_doc.is_instvar in (False, UNKNOWN))]
        elif value_type == 'classmethod':
            return [var_doc for var_doc in var_list
                    if (isinstance(var_doc.value, ClassMethodDoc) and
                        var_doc.is_instvar in (False, UNKNOWN))]
        elif value_type == 'staticmethod':
            return [var_doc for var_doc in var_list
                    if (isinstance(var_doc.value, StaticMethodDoc) and
                        var_doc.is_instvar in (False, UNKNOWN))]
        elif value_type == 'property':
            return [var_doc for var_doc in var_list
                    if (isinstance(var_doc.value, PropertyDoc) and
                        var_doc.is_instvar in (False, UNKNOWN))]
        elif value_type == 'class':
            return [var_doc for var_doc in var_list
                    if (isinstance(var_doc.value, ClassDoc) and
                        var_doc.is_instvar in (False, UNKNOWN))]
        elif value_type == 'instancevariable':
            return [var_doc for var_doc in var_list
                    if var_doc.is_instvar is True]
        elif value_type == 'classvariable':
            return [var_doc for var_doc in var_list
                    if (var_doc.is_instvar in (False, UNKNOWN) and
                        not isinstance(var_doc.value, RoutineDoc))]
        else:
            raise ValueError('Bad value type %r' % value_type)

class RoutineDoc(ValueDoc):
    """
    API documentation information about a single routine.

    @ivar posargs: The names of the routine's positional arguments.
        If an argument list contains \"unpacking\" arguments, then
        their names will be specified using nested lists.  E.g., if
        a function's argument list is C{((x1,y1), (x2,y2))}, then
        posargs will be C{[['x1','y1'], ['x2','y2']]}.
    @type posargs: C{list}
    @ivar posarg_defaults: API documentation for the positional arguments'
        default values.  This list has the same length as C{posargs}, and
        each element of C{posarg_defaults} describes the corresponding
        argument in C{posargs}.  For positional arguments with no default,
        C{posargs_defaults} will contain None.
    @type posargs_defaults: C{list} of C{ValueDoc} or C{None}
    @ivar vararg: The name of the routine's vararg argument, or C{None} if
        it has no vararg argument.
    @type vararg: C{string} or C{None}
    @ivar kwarg: The name of the routine's keyword argument, or C{None} if
        it has no keyword argument.
    @type kwarg: C{string} or C{None}

    @ivar arg_descrs: A list of descriptions of the routine's
        arguments.  Each element of this list is a tuple C{(arg,
        descr)}, where C{arg} is an argument name (or a tuple of 
        of argument names); and C{descr} is a L{ParsedDocstring
        <epydoc.markup.ParsedDocstring>} describing the argument(s)
        specified by C{arg}.
    @type arg_descrs: C{list}
    
    @ivar arg_types: Descriptions of the expected types for the
        routine's arguments, encoded as a dictionary mapping from
        argument names to type descriptions.
    @type arg_types: C{dict} from C{string} to L{ParsedDocstring
        <epydoc.markup.ParsedDocstring>}

    @ivar return_descr: A description of the value returned by this
        routine.
    @type return_descr: L{ParsedDocstring<epydoc.markup.ParsedDocstring>}
    @ivar return_type: A description of expected type for the value
        returned by this routine.
    @type return_type: L{ParsedDocstring<epydoc.markup.ParsedDocstring>}

    @ivar exception_descrs: A list of descriptions of exceptions
        that the routine might raise.  Each element of this list is a
        tuple C{(exc, descr)}, where C{exc} is a string contianing the
        exception name; and C{descr} is a L{ParsedDocstring
        <epydoc.markup.ParsedDocstring>} describing the circumstances
        under which the exception specified by C{exc} is raised.
        
    @type exception_descrs: C{list}
    """
    posargs = UNKNOWN
    posarg_defaults = UNKNOWN
    vararg = UNKNOWN
    kwarg = UNKNOWN
    arg_descrs = UNKNOWN
    arg_types = UNKNOWN
    return_descr = UNKNOWN
    return_type = UNKNOWN
    exception_descrs = UNKNOWN

    def valdoc_links(self):
        return []
    def vardoc_links(self):
        return []
    
    def all_args(self):
        """
        @return: A list of the names of all arguments (positional,
        vararg, and keyword), in order.  If a positional argument
        consists of a tuple of names, then that tuple will be
        flattened.
        """
        all_args = _flatten(self.posargs)
        if self.vararg not in (None, UNKNOWN):
            all_args.append(self.vararg)
        if self.kwarg not in (None, UNKNOWN):
            all_args.append(self.kwarg)
        return all_args

def _flatten(lst, out=None):
    """
    Return a flattened version of C{lst}.
    """
    if out is None: out = []
    for elt in lst:
        if isinstance(elt, (list,tuple)):
            _flatten(elt, out)
        else:
            out.append(elt)
    return out

class ClassMethodDoc(RoutineDoc): pass
class StaticMethodDoc(RoutineDoc): pass

class PropertyDoc(ValueDoc):
    """
    API documentation information about a single property.
    
    @ivar fget: API documentation for the property's get function.
    @type fget: L{RoutineDoc}
    @ivar fset: API documentation for the property's set function.
    @type fset: L{RoutineDoc}
    @ivar fdel: API documentation for the property's delete function.
    @type fdel: L{RoutineDoc}
    """
    fget = UNKNOWN
    fset = UNKNOWN
    fdel = UNKNOWN
    type_descr = UNKNOWN # [XX]?? type of value that should be stored in the prop

    def valdoc_links(self):
        val_docs = []
        if self.fget not in (None, UNKNOWN): val_docs.append(self.fget)
        if self.fset not in (None, UNKNOWN): val_docs.append(self.fset)
        if self.fdel not in (None, UNKNOWN): val_docs.append(self.fdel)
        return val_docs
    def vardoc_links(self):
        return []

######################################################################
## Index
######################################################################

class DocIndex:
    """
    An index that .. hmm...  it *can't* be used to access some things,
    cuz they're not at the root level.  Do I want to add them or what?
    And if so, then I have a sort of a new top level.  hmm..  so
    basically the question is what to do with a name that's not in the
    root var's name space.  2 types:
      - entirely outside (eg os.path)
      - inside but not known (eg a submodule that we didn't look at?)
      - container of current thing not examined?
    
    An index of all the C{APIDoc} objects that can be reached from a
    root set of C{ValueDoc}s.  As a side effect of constructing this
    index, the reachable C{APIDoc}s are modified in several ways:
    
      - Canonicalization:
        - A cannonical name is assigned to any C{ValueDoc} that does
          not already have one.
          
      - Linking:
        - Any C{ValueDoc}s that define the C{imported_from} attribute
          are replaced by the referenced C{ValueDoc}, if it is
          reachable from the root set.
    
    The members of this index can be accessed by dotted name.  In
    particular, C{DocIndex} defines two mappings, accessed via the
    L{get_vardoc()} and L{get_valdoc()} methods, which can be used to
    access C{VariableDoc}s or C{ValueDoc}s respectively by name.  (Two
    separate mappings are necessary because a single name can be used
    to refer to both a variable and to the value contained by that
    variable.)

    Additionally, the index defines two sets of C{ValueDoc}s:
    \"reachable C{ValueDoc}s\" and \"contained C{ValueDoc}s\".  The
    X{reachable C{ValueDoc}s} are defined as the set of all
    C{ValueDoc}s that can be reached from the root set by following
    I{any} sequence of pointers to C{ValueDoc}s or C{VariableDoc}s.
    The X{contained C{ValueDoc}s} are defined as the set of all
    C{ValueDoc}s that can be reached from the root set by following
    only the C{ValueDoc} pointers defined by non-imported
    C{VariableDoc}s.  For example, if the root set contains a module
    C{m}, then the contained C{ValueDoc}s includes the C{ValueDoc}s
    for any functions, variables, or classes defined in that module,
    as well as methods and variables defined in classes defined in the
    module.  The reachable C{ValueDoc}s includes all of those
    C{ValueDoc}s, as well as C{ValueDoc}s for any values imported into
    the module, and base classes for classes defined in the module.
    """

    def __init__(self, root):
        """
        Create a new documentation index, based on the given root set
        of C{ValueDoc}s.  If any C{APIDoc}s reachable from the root
        set does not have a canonical name, then it will be assigned
        one.  etc.
        
        @param root: A list of C{ValueDoc}s.
        """
        for apidoc in root:
            if apidoc.canonical_name in (None, UNKNOWN):
                raise ValueError("All APIdocs passed to DocIndexer "
                                 "must already have canonical names.")
        
        # Initialize the root items list.  We sort them by length in
        # ascending order.  (This ensures that variables will shadow
        # submodules when appropriate.)
        self.root = sorted(root, key=lambda d:len(d.canonical_name))

    #////////////////////////////////////////////////////////////
    # Lookup methods
    #////////////////////////////////////////////////////////////
    # [xx]
    # Currently these only work for things reachable from the
    # root... :-/  I might want to change this so that imported
    # values can be accessed even if they're not contained.  
    # Also, I might want canonical names to not start with ??
    # if the thing is a top-level imported module..?

    def get_vardoc(self, name):
        """
        Return the C{VariableDoc} with the given name, or C{None} if this
        index does not contain a C{VariableDoc} with the given name.
        """
        var, val = self._get(name)
        return var

    def get_valdoc(self, name):
        """
        Return the C{ValueDoc} with the given name, or C{None} if this
        index does not contain a C{ValueDoc} with the given name.
        """
        var, val = self._get(name)
        return val

    def _get(self, name):
        """
        A helper function that's used to implement L{get_vardoc()}
        and L{get_valdoc()}.
        """
        # Convert name to a DottedName, if necessary.
        name = DottedName(name)

        # Look for an element in the root set whose name is a prefix
        # of `name`.  If we can't find one, then return None.
        for root_valdoc in self.root:
            if root_valdoc.canonical_name.dominates(name):
                var_doc, val_doc = self._get_from(
                    root_valdoc, name[len(root_valdoc.canonical_name):])
                if var_doc is not None or val_doc is not None:
                    return var_doc, val_doc

        # We didn't find it.
        return None, None
        
    def _get_from(self, root_valdoc, name):
        # Starting at the selected root val_doc, walk down the variable
        # chain until we find the requested value/variable.
        var_doc = None
        val_doc = root_valdoc
    
        for identifier in name:
            if val_doc == None:
                return None, None
            
            # First, check for variables in namespaces.
            for child_var in val_doc.vardoc_links():
                if child_var.name == identifier:
                    var_doc = child_var
                    val_doc = var_doc.value
                    if val_doc is UNKNOWN: val_doc = None
                    break

            # If that fails, then see if it's a submodule.
            else:
                if (isinstance(val_doc, ModuleDoc) and
                    val_doc.submodules is not UNKNOWN):
                    for submodule in val_doc.submodules:
                        if (submodule.canonical_name ==
                            DottedName(val_doc.canonical_name, identifier)):
                            var_doc = None
                            val_doc = submodule
                            if val_doc is UNKNOWN: val_doc = None
                            break
                    else:
                        return None, None
                else:
                    return None, None
            
        return (var_doc, val_doc)

    #////////////////////////////////////////////////////////////
    # etc
    #////////////////////////////////////////////////////////////

    def contained_valdocs(self, sorted_by_name=False):
        if sorted_by_name:
            return sorted(contained_valdocs(*self.root),
                          key=lambda doc:doc.canonical_name)
        else:
            return contained_valdocs(*self.root)
        
    def reachable_valdocs(self, sorted_by_name=False):
        if sorted_by_name:
            return sorted(reachable_valdocs(*self.root),
                          key=lambda doc:doc.canonical_name)
        else:
            return reachable_valdocs(*self.root)

    def container(self, api_doc):
        """
        Return the C{ValueDoc} that contains the given C{APIDoc}, or
        C{None} if its container is not in the index.
        """
        if isinstance(api_doc, VariableDoc):
            return api_doc.container
        if len(api_doc.canonical_name) == 1:
            return None
        elif isinstance(api_doc, ModuleDoc) and api_doc.package != UNKNOWN:
            return api_doc.package
        else:
            parent = api_doc.canonical_name.container()
            return self.get_valdoc(parent)

    def module_that_defines(self, api_doc):
        """
        Return the C{ModuleDoc} of the module that defines C{api_doc},
        or C{None} if that module is not in the index.  If C{api_doc}
        is itself a module, then C{api_doc} will be returned.
        """
        while not (isinstance(api_doc, ModuleDoc) or api_doc is None):
            api_doc = self.container(api_doc)
        return api_doc
    
######################################################################
## Pretty Printing
######################################################################

def pp_apidoc(api_doc, doublespace=0, depth=5, exclude=(), include=(),
              backpointers=None):
    """
    @return: A multiline pretty-printed string representation for the
        given C{APIDoc}.
    @param doublespace: If true, then extra lines will be
        inserted to make the output more readable.
    @param depth: The maximum depth that pp_apidoc will descend
        into descendent VarDocs.  To put no limit on
        depth, use C{depth=-1}.
    @param exclude: A list of names of attributes whose values should
        not be shown.
    @param backpointers: For internal use.
    """
    pyid = id(api_doc.__dict__)
    if backpointers is None: backpointers = {}
    if (hasattr(api_doc, 'canonical_name') and
        api_doc.canonical_name is not UNKNOWN):
        name = '%s for %s' % (api_doc.__class__.__name__,
                              api_doc.canonical_name)
    elif hasattr(api_doc, 'name') and api_doc.name is not UNKNOWN:
        name = '%s for %s' % (api_doc.__class__.__name__, api_doc.name)
    else:
        name = api_doc.__class__.__name__
        
    if pyid in backpointers:
        return '%s [%s] (defined above)' % (name, backpointers[pyid])
    
    if depth == 0:
        if hasattr(api_doc, 'name') and api_doc.name is not None:
            return '%s...' % api_doc.name
        else:
            return '...'

    backpointers[pyid] = len(backpointers)
    s = '%s [%s]' % (name, backpointers[pyid])

    # Only print non-empty fields:
    fields = [field for field in api_doc.__dict__.keys()
              if (field in include or
                  (getattr(api_doc, field) is not UNKNOWN
                   and field not in exclude))]
    if include:
        fields = [field for field in dir(api_doc)
                  if field in include]
    else:
        fields = [field for field in api_doc.__dict__.keys()
                  if (getattr(api_doc, field) is not UNKNOWN
                      and field not in exclude)]
    fields.sort()
    
    for field in fields:
        fieldval = getattr(api_doc, field)
        if doublespace: s += '\n |'
        s += '\n +- %s' % field

        if (isinstance(fieldval, types.ListType) and
            len(fieldval)>0 and
            isinstance(fieldval[0], APIDoc)):
            s += _pp_list(api_doc, fieldval, doublespace, depth,
                          exclude, include, backpointers,
                          (field is fields[-1]))
        elif (isinstance(fieldval, types.DictType) and
              len(fieldval)>0 and 
              isinstance(fieldval.values()[0], APIDoc)):
            s += _pp_dict(api_doc, fieldval, doublespace, 
                          depth, exclude, include, backpointers,
                          (field is fields[-1]))
        elif isinstance(fieldval, APIDoc):
            s += _pp_apidoc(api_doc, fieldval, doublespace, depth,
                            exclude, include, backpointers,
                            (field is fields[-1]))
        else:
            s += ' = ' + _pp_val(api_doc, fieldval, doublespace,
                                 depth, exclude, include, backpointers)
                
    return s

def _pp_list(api_doc, items, doublespace, depth, exclude, include,
              backpointers, is_last):
    line1 = (is_last and ' ') or '|'
    s = ''
    for item in items:
        line2 = ((item is items[-1]) and ' ') or '|'
        joiner = '\n %s  %s ' % (line1, line2)
        if doublespace: s += '\n %s  |' % line1
        s += '\n %s  +- ' % line1
        valstr = _pp_val(api_doc, item, doublespace, depth, exclude, include,
                         backpointers)
        s += joiner.join(valstr.split('\n'))
    return s

def _pp_dict(api_doc, dict, doublespace, depth, exclude, include,
              backpointers, is_last):
    items = dict.items()
    items.sort()
    line1 = (is_last and ' ') or '|'
    s = ''
    for item in items:
        line2 = ((item is items[-1]) and ' ') or '|'
        joiner = '\n %s  %s ' % (line1, line2)
        if doublespace: s += '\n %s  |' % line1
        s += '\n %s  +- ' % line1
        valstr = _pp_val(api_doc, item[1], doublespace, depth, exclude,
                         include, backpointers)
        s += joiner.join(('%s => %s' % (item[0], valstr)).split('\n'))
    return s

def _pp_apidoc(api_doc, val, doublespace, depth, exclude, include,
                backpointers, is_last):
    line1 = (is_last and ' ') or '|'
    s = ''
    if doublespace: s += '\n %s  |  ' % line1
    s += '\n %s  +- ' % line1
    joiner = '\n %s    ' % line1
    childstr = pp_apidoc(val, doublespace, depth-1, exclude,
                         include, backpointers)
    return s + joiner.join(childstr.split('\n'))
    
def _pp_val(api_doc, val, doublespace, depth, exclude, include, backpointers):
    from epydoc import markup
    if isinstance(val, APIDoc):
        return pp_apidoc(val, doublespace, depth-1, exclude,
                         include, backpointers)
    elif isinstance(val, markup.ParsedDocstring):
        valrepr = `val.to_plaintext(None)`
        if len(valrepr) < 40: return valrepr
        else: return valrepr[:37]+'...'
    else:
        valrepr = repr(val)
        if len(valrepr) < 40: return valrepr
        else: return valrepr[:37]+'...'

