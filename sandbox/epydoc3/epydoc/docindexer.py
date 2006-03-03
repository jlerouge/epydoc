# epydoc -- API documentation indexing
#
# Copyright (C) 2005 Edward Loper
# Author: Edward Loper <edloper@loper.org>
# URL: <http://epydoc.sf.net>
#
# $Id$

"""
Create an index containing the API documentation information contained
in a root set of C{ValueDoc}s, including any C{APIDoc}s that are
reachable from that set.
"""

######################################################################
## Imports
######################################################################

import sys # for maxint
from epydoc.apidoc import *
from epydoc import log
from sets import Set

# Backwards compatibility imports:
try: sorted
except NameError: from epydoc.util import py_sorted as sorted

class DocIndex:
    """
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
        #: A list of (name, ValueDoc) pairs.
        self._root_list = list(root)

        for apidoc in root:
            if apidoc.canonical_name in (None, UNKNOWN):
                raise ValueError("All APIdocs passed to DocIndexer "
                                 "must already have canonical names.")
        
        #: The set of all C{ValueDoc}s that are directly or indirectly
        #: reachable from the root set.  In particular, this set contains
        #: all C{ValueDoc}s that can be reached from the root set by
        #: following I{any} sequence of pointers to C{ValueDoc}s or
        #: C{VariableDoc}s.
        self.reachable_valdocs = Set()

        #: The set of all C{VariableDoc}s that are directly or indirectly
        #: reachable from the root set.  In particular, this set
        #: contains all C{VariableDoc}s that can be reached from the
        #: root set by following I{any} sequence of pointers to
        #: C{ValueDoc}s or C{VariableDoc}s.
        self.reachable_vardocs = Set()
        
        #: The set of all C{ValueDoc}s that are directly or indirectly
        #: contained in the root set.  In particular, this set contains
        #: all C{ValueDoc}s that can be reached from the root set by
        #: following only the C{ValueDoc} pointers defined by
        #: non-imported C{VariableDoc}s.  This will always be a subset
        #: of L{reachable_valdocs}.
        self.contained_valdocs = Set()

        #: A dictionary mapping from each C{ValueDoc} to the score that
        #: has been assigned to its current cannonical name.  If
        #: L{_assign_canonical_names()} finds a cannonical name with a
        #: better score, then it will replace the old name.
        self._score_dict = {}

        #: The set of names that have been used for unreachable objects.
        #: This is used to ensure there are no duplicate cannonical names
        #: assigned.
        self._unreachable_names = Set()

        # Initialize the root items list.  We sort them by length in
        # ascending order.  (This ensures that variables will shadow
        # submodules when appropriate.)
        self._root_list = sorted(root, key=lambda d:len(d.canonical_name))

        # [xx] this should really be separated out into a separate
        # step (linking):
        
        # Resolve any imported_from links, if the target of the link
        # is contained in the index.  We have to be a bit careful
        # here, because when we merge srcdoc & val_doc, we might
        # unintentionally create a duplicate entry in
        # reachable/contained valdocs sets.
        reachable_val_docs = reachable_valdocs(*self._root_list)
        for i, val_doc in enumerate(reachable_val_docs):
            if i % 100 == 0:
                log.progress(.1*i/len(reachable_val_docs), 'Resolving imports')
            if val_doc.imported_from not in (UNKNOWN, None):
                self._resolve_imports(val_doc)

        # Initialize _contained_valdocs and _reachable_valdocs; and
        # assign canonical names to any ValueDocs that don't already
        # have them.
        log.start_progress('Indexing documentation')
        for i, val_doc in enumerate(self._root_list):
            log.progress(i*.7/len(self._root_list),
                         val_doc.canonical_name)
            self._find_contained_valdocs(val_doc)
            # the following method does both canonical name assignment
            # and initialization of reachable_valdocs:
            self._assign_canonical_names(val_doc, val_doc.canonical_name)

        log.end_progress()

        # [XX] conflict check turned off!
        return
        # Check that we don't have any conflicts in the root set (and
        # remove redundancies).  This is intentionally done *after*
        # we resolve imported_from links.
        # [xx] I can probably get rid of this check eventually.
        for i1, valdoc1 in enumerate(self._root_list):
            for i2 in range(len(self._root_list)-1, i1, -1):
                valdoc2 = self._root_list[i2]
                if valdoc1.canonical_name.dominates(valdoc2.canonical_name):
                    del self._root_list[i2]
                    if self.get_valdoc(valdoc2.canonical_name) != valdoc2:
                        log.error(('bad root set: %r dominates %r '
                                   'but lookup direct inside %r gives %r') %
                               (valdoc1, valdoc2, valdoc1, 
                                self.get_valdoc(valdoc2.canonical_name)))
                        raise ValueError, 'Inconsistant root set'

    def _resolve_imports(self, val_doc):
        while val_doc.imported_from not in (UNKNOWN, None):
            # Find the valuedoc that the imported_from name points to.
            src_doc = self.get_valdoc(val_doc.imported_from)

            # If we don't have any valuedoc at that address, then
            # promote this proxy valuedoc to a full (albeit empty)
            # one, and add it to our root set.
            if src_doc is None:
                val_doc.canonical_name = val_doc.imported_from
                val_doc.imported_from = None
                self._root_list.append(val_doc) # <- should I do this? [xx]
                if isinstance(val_doc, NamespaceDoc):
                    log.warn("hoomy %r" % val_doc)
                break

            # If we *do* have something at that address, then
            # merge the proxy `val_doc` with it.
            elif src_doc != val_doc:
                src_doc.merge_and_overwrite(val_doc)

            # If the imported_from link points back at src_doc
            # itself, then we most likely have a variable that's
            # shadowing a submodule that it should be equal to.
            # So just get rid of the variable. [xx] ??
            elif src_doc == val_doc:
                parent_name = DottedName(*val_doc.imported_from[:-1])
                var_name = val_doc.imported_from[-1]
                parent = self.get_valdoc(parent_name)
                del parent.variables[var_name]

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
        for root_valdoc in self._root_list:
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
            children = self._vardocs_reachable_from(val_doc)
            for child in children:
                if child.name == identifier:
                    var_doc = child
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
    # Index initialization
    #////////////////////////////////////////////////////////////

    def _find_contained_valdocs(self, val_doc):
        """
        Initialize the instance variable L{contained_valdocs}, by
        recursively traversing the API documentation tree, starting at
        the given valuedoc.
        """
        # Cycle check:
        if val_doc in self.contained_valdocs: return
        # Add the val_doc to contained_valdocs:
        self.contained_valdocs.add(val_doc)
        # Recurse:
        for var_doc in self._vardocs_reachable_from(val_doc):
            self.reachable_vardocs.add(var_doc)
            if var_doc.value is UNKNOWN: continue
            # [xx] what should we do with UNKNOWN for imported?
            if var_doc.is_imported is not True:#not in (True, UNKNOWN):
                self._find_contained_valdocs(var_doc.value)
        
    def _assign_canonical_names(self, val_doc, name, score=0):
        """
        Assign a canonical name to C{val_doc} (if it doesn't have one
        already), and (recursively) to each variable in C{val_doc}.
        In particular, C{val_doc} will be assigned the canonical name
        C{name} iff either:
          - C{val_doc}'s canonical name is C{UNKNOWN}; or
          - C{val_doc}'s current canonical name was assigned by this
            method; but the score of the new name (C{score}) is higher
            than the score of the current name (C{score_dict[val_doc]}).
            
        Note that canonical names will even be assigned to values
        like integers and C{None}; but these should be harmless.

        This method also initializes the instance variable
        L{reachable_vardocs}.
        """
        # If we've already visited this node, and our new score
        # doesn't beat our old score, then there's nothing more to do.
        # Note that since score increases strictly monotonically, this
        # also prevents us from going in cycles.
        if (val_doc in self._score_dict and
            score <= self._score_dict[val_doc]):
            return

        # Add val_doc to reachable_valudocs.
        self.reachable_valdocs.add(val_doc)
        
        # Update val_doc's canonical name, if appropriate.
        if (val_doc not in self._score_dict and
            val_doc.canonical_name is not UNKNOWN):
            # If this is the fist time we've seen val_doc, and it
            # already has a name, then don't change that name.
            self._score_dict[val_doc] = sys.maxint
            name = val_doc.canonical_name
            score = 0
        else:
            # Otherwise, update the name iff the new score is better
            # than the old one.
            if (val_doc not in self._score_dict or
                score > self._score_dict[val_doc]):
                val_doc.canonical_name = name
                self._score_dict[val_doc] = score

        # Recurse to any contained values.
        for var_doc in self._vardocs_reachable_from(val_doc):
            if var_doc.value is UNKNOWN: continue
            varname = DottedName(name, var_doc.name)

            # This check is for cases like curses.wrapper, where an
            # imported variable shadows its value's "real" location.
            if self._var_shadows_self(var_doc, varname):
                self._fix_self_shadowing_var(var_doc, varname)

            # Find the score for this new name.            
            vardoc_score = score-1
            if var_doc.is_imported is UNKNOWN: vardoc_score -= 10
            elif var_doc.is_imported: vardoc_score -= 100
            if var_doc.is_alias is UNKNOWN: vardoc_score -= 10
            elif var_doc.is_alias: vardoc_score -= 1000
            
            self._assign_canonical_names(var_doc.value, varname, vardoc_score)

        # Recurse to any directly reachable values.
        for val_doc_2 in self._valdocs_reachable_from(val_doc):
            val_name, val_score = self._unreachable_name(val_doc_2)
            self._assign_canonical_names(val_doc_2, val_name, val_score)

    def _var_shadows_self(self, var_doc, varname):
        return (var_doc.value not in (None, UNKNOWN) and
                var_doc.value.canonical_name not in (None, UNKNOWN) and
                var_doc.value.canonical_name != varname and
                varname.dominates(var_doc.value.canonical_name))

    def _fix_self_shadowing_var(self, var_doc, varname):
        # If possible, find another name for the shadowed value.
        cname = var_doc.value.canonical_name
        for i in range(1, len(cname)-1):
            new_name = DottedName(*(cname[:i]+(cname[i]+"'",)+cname[i+1:]))
            val_doc = self.get_valdoc(new_name)
            if val_doc is not None:
                log.warn("%s shadows its own value -- using %s instead" %
                         (varname, new_name))
                var_doc.value = val_doc
                return

        # If we couldn't find the actual value, then at least
        # invalidate the canonical name.
        log.warn('%s shadows itself' % varname)
        del var_doc.value.canonical_name

    def _unreachable_name(self, val_doc):
        assert isinstance(val_doc, ValueDoc)
        
        # [xx] (when) does this help?
        if (isinstance(val_doc, ModuleDoc) and
            len(val_doc.canonical_name)==1 and val_doc.package is None):
            for root_val in self._root_list:
                if root_val.canonical_name == val_doc.canonical_name:
                    if root_val != val_doc: 
                        log.error("Name conflict: %r vs %r" %
                                  (val_doc, root_val))
                    break
            else:
                return val_doc.canonical_name, -1000

        if val_doc.imported_from not in (UNKNOWN, None):
            name = DottedName(DottedName.UNREACHABLE, val_doc.imported_from)
        elif (val_doc.pyval is not UNKNOWN and
              hasattr(val_doc.pyval, '__name__')):
            try:
                name = DottedName(DottedName.UNREACHABLE,
                                  val_doc.pyval.__name__)
            except ValueError:
                name = DottedName(DottedName.UNREACHABLE)
        else:
            name = DottedName(DottedName.UNREACHABLE)

        # Uniquify the name.
        if name in self._unreachable_names:
            n = 2
            while DottedName('%s-%s' % (name,n)) in self._unreachable_names:
                n += 1
            name = DottedName('%s-%s' % (name,n))
        self._unreachable_names.add(name)
        
        return name, -10000

    def _vardocs_reachable_from(self, val_doc):
        """
        Return a list of all C{VariableDoc}s that are directly
        reachable from the given C{ValueDoc}.
        """
        if (isinstance(val_doc, NamespaceDoc)
            and val_doc.variables is not UNKNOWN):
            return val_doc.variables.values()
        else:
            return []

    def _valdocs_reachable_from(self, val_doc):
        """
        Return a list of all valuedocs that are directly reachable
        from the given C{ValueDoc}.  (This does not include variables
        of a C{NamespaceDoc}, since they're reachable I{indirectly}
        via a VariableDoc.)
        """
        reachable = []
        # Recurse to any other valuedocs reachable from this val_doc.
        if (isinstance(val_doc, ModuleDoc) and
            val_doc.package not in (UNKNOWN, None)):
            reachable.append(val_doc.package)
        if isinstance(val_doc, ClassDoc):
            if val_doc.bases is not UNKNOWN:
                for cls in val_doc.bases:
                    reachable.append(cls)
            if val_doc.subclasses is not UNKNOWN:
                for cls in val_doc.subclasses:
                    reachable.append(cls)
            #if val_doc.mro is not UNKNOWN:
            #    for cls in val_doc.mro():
            #        reachable.append(cls)
        if isinstance(val_doc, PropertyDoc):
            if val_doc.fget not in (UNKNOWN, None):
                reachable.append(val_doc.fget)
            if val_doc.fset not in (UNKNOWN, None):
                reachable.append(val_doc.fset)
            if val_doc.fdel not in (UNKNOWN, None):
                reachable.append(val_doc.fdel)
        return reachable
    

