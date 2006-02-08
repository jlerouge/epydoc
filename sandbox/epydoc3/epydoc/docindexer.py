# epydoc -- API documentation indexing
#
# Copyright (C) 2005 Edward Loper
# Author: Edward Loper <edloper@loper.org>
# URL: <http://epydoc.sf.net>
#
# $Id$

"""
Create an index containing the API documentation information contained
in a set of C{ValueDoc}s, including any C{ValueDoc}s that are
reachable from that set.  This index is encoded as a dictionary
mapping from canonical names to C{ValueDoc} objects, and contains a
single entry for each C{ValueDoc} that is reachable from the original
set of C{ValueDoc}s.  Any C{ValueDoc} that did not already have a
canonical name will be assigned a canonical name.  The
C{canonical_container} properties will also be initialized for all
reachable C{ValueDoc}s.


"""

######################################################################
## Imports
######################################################################

import sys # for maxint
from epydoc.apidoc import *
from sets import Set

class DocIndex:
    """
    A collection of C{APIDoc} objects that can be reached from a root
    set of C{APIDoc} objects.  These C{APIDoc}s are indexed in two
    ways:
    
      - As mappings from fully qualified dotted names to the
        C{APIDoc}s that are reachable via those names.  Separate
        mappings are provided for C{ValueDoc}s and C{VariableDoc}s,
        since C{ValueDoc}s and C{VariableDoc}s can share names.  If a
        single name can be used to refer to both a package-local
        variable and a subpackage, then the package-local variable
        'shadows' the subpackage.

      - As a list of all the C{ValueDoc}s that are 'contained'
        (directly or indirectly) in the root set.  In particular, this
        list contains the C{ValueDoc}s in the root set, plus any
        C{ValueDoc}s that can be reached from that set via
        non-imported variables of C{NamespaceDoc}s.  It does I{not}
        include: (a) values that can only be reached from the root set
        via import statments; and (b) values that can only be reached
        from the root set via non-variable pointers (e.g., the base
        class list of a C{ClassDoc}; the package pointer of a
        C{ModuleDoc}; or the C{fget}/C{fset}/C{fdel} functions of a
        property).
    """
    def __init__(self, root):
        """
        Create a new documentation index, based on the given root set
        of C{ValueDoc}s.  If any C{APIDoc}s reachable from the root
        set does not have a canonical name, then it will be assigned
        one.  etc.
        
        @param root: A dictionary mapping from names to C{ValueDoc}s.
        """
        #: A dictionary specifying the root set of C{ValueDocs}, along
        #: with their names.
        self._root = root
        
        #: The set of all C{ValueDoc}s that are directly or indirectly
        #: contained in the root set.
        self.contained_valdocs = Set()

        #: The set of all C{ValueDoc}s that are directly or indirectly
        #: reachable from the root set.
        self.reachable_valdocs = Set()
        
        #: A dictionary mapping from each C{ValueDoc} to the score that
        #: has been assigned to its current cannonical name.  If
        #: L{_index()} finds a cannonical name with a better score,
        #: then it will replace the old name.
        self._score_dict = {}

        #: The set of names that have been used for unreachable objects.
        #: This is used to ensure there are no duplicate cannonical names
        #: assigned.
        self._unreachable_names = Set()

        # [xx] check that we don't have conflicts in the root set?

        # Initialize _contained_valdocs and _reachable_valdocs; and
        # assign canonical names to any ValueDocs that don't already
        # have them.
        for name, val_doc in root.items():
            self._find_contained_valdocs(val_doc)
            self._assign_canonical_names(val_doc, name)

        for val_doc in self.reachable_valdocs:
            # Resolve any imported_from links, if the target of the
            # link is contained in the index.
            if val_doc.imported_from not in (UNKNOWN, None):
                srcdoc = self.get_valdoc(val_doc.imported_from)
                if srcdoc is not val_doc and srcdoc is not None:
                    val_doc.__class__ = srcdoc.__class__
                    val_doc.__dict__ = srcdoc.__dict__

            # Set the canonical_container attribute on all reachable
            # valuedocs (where possible).
            container_name = val_doc.canonical_name.container()
            if container_name is None:
                val_doc.canonical_container = None
            else:
                container_doc = self.get_valdoc(container_name)
                if container_doc is not None:
                    val_doc.canonical_container = container_doc

    #////////////////////////////////////////////////////////////
    # Lookup methods
    #////////////////////////////////////////////////////////////

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
        for (root_name, root_valdoc) in self._root.items():
            if name[:len(root_name)] == root_name[:]:
                val_doc = root_valdoc
                var_doc = None
                break
        else:
            return None, None
                
        # Starting at the selected root valdoc, walk down the variable
        # chain until we find the requested value/variable.
        for identifier in name[len(root_name):]:
            if val_doc is UNKNOWN:
                return None, None
            
            # First, check for variables in namespaces.
            children = self._vardocs_reachable_from(val_doc)
            for child in children:
                if child.name == identifier:
                    var_doc = child
                    val_doc = var_doc.value
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
            if var_doc.value is UNKNOWN: continue
            # [xx] what should we do with UNKNOWN here?
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
            # Find the score for this new name.            
            vardoc_score = score-1
            if var_doc.is_imported is UNKNOWN: vardoc_score -= 10
            elif var_doc.is_imported: vardoc_score -= 100
            if var_doc.is_alias is UNKNOWN: vardoc_score -= 10
            elif var_doc.is_alias: vardoc_score -= 1000
            # Imported vars don't count as "contained".
            self._assign_canonical_names(var_doc.value, varname, vardoc_score)

        # Recurse to any directly reachable values.
        for val_doc_2 in self._valdocs_reachable_from(val_doc):
            name = self._unreachable_name(val_doc_2)
            self._assign_canonical_names(val_doc_2, name, -10000)

    def _unreachable_name(self, val_doc):
        if val_doc.imported_from not in (UNKNOWN, None):
            name = DottedName('??', val_doc.imported_from)
        elif (val_doc.pyval is not UNKNOWN and
              hasattr(val_doc.pyval, '__name__')):
            name = DottedName('??', val_doc.pyval.__name__)
        else:
            name = DottedName('??')

        # Uniquify the name.
        if name in self._unreachable_names:
            n = 2
            while DottedName('%s-%s' % (name,n)) in self._unreachable_names:
                n += 1
            name = DottedName('%s-%s' % (name,n))
        self._unreachable_names.add(name)
        
        return name

    def _vardocs_reachable_from(self, val_doc):
        """
        Return a list of all C{VariableDoc}s that are directly
        reachable from the given C{ValueDoc}.
        """
        val_docs = []
        if (isinstance(val_doc, ClassDoc)
            and val_doc.local_variables is not UNKNOWN):
            val_docs += val_doc.local_variables.values()
        if (isinstance(val_doc, NamespaceDoc)
            and val_doc.variables is not UNKNOWN):
            val_docs += val_doc.variables.values()
        return val_docs

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
            val_doc.package not in(UNKNOWN, None)):
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
    








    



        

        

        
    
#     def __init__(self, value_index):
#         self.values = []
#         self.root = {}
        
#         for (name, val_doc) in value_index:
#             if val_doc.canonical_name != name: continue
#             values.append(val_doc)
#             if len(name) == 1:
#                 self.root.append(val_doc)

#     def __get(self, name):
#         # Make sure name is a DottedName.
#         name = DottedName(name)

#         # Get the root value specified by name[0]
#         val_doc = self.root.get(name[0])
#         var_doc = None

#         for identifier in name[1:]:
#             var_doc = val_doc[identifier]
#             val_doc = var_doc.value
#         return (var_doc, val_doc)
    
            
#     def get_variable(self, name):
#         var, val = self.__get(name)
#         if var is None:
#             raise KeyError('Variable %s not found' % name)
#         else:
#             return var

#     def get_value(self, name):
#         var, val = self.__get(name)
#         if val is None:
#             raise KeyError('Value %s not found' % name)
#         else:
#             return val
#     __getitem__ = get_value

#     def contents(self):
#         return self.contents

#     def __iter__(self):
#         return iter(self.values)


# #             if isinstance(val, ModuleDoc):
# #                 if identifier in val.variables:
# #                     var = val.variables[identifier]
# #                 elif identifier in val.subpackages:
# #                     var = val.subpackages[identifier] # [xx]
# #                 else:
# #                     return None
# #             elif isinstance(val, ClassDoc):
# #                 if identifier in val.local_variables:
# #                     var = val.local_variables[identifier]
# #                 elif val.variables is not UNKNOWN and identifier in val.variables:
# #                     var = val.variables[identifier]
# #                 else:
# #                     reutrn None
# #            val = var.value
# #        return (var, val)



# ######################################################################
# ## Doc Indexer
# ######################################################################

# class DocIndexer:
#     """
#     A processing class that creates an index containing the API
#     documentation information contained in a set of C{ValueDoc}s,
#     including any C{ValueDoc}s that are reachable from that set.  This
#     index is encoded as a dictionary mapping from canonical names to
#     C{ValueDoc} objects, and contains a single entry for each
#     C{ValueDoc} that is reachable from the original set of
#     C{ValueDoc}s.

#     Any C{ValueDoc} that did not already have a canonical name will be
#     assigned a canonical name.  If the C{ValueDoc}'s value can be
#     reached using a single sequence of identifiers (given the
#     appropriate imports), then that sequence of identifiers will be
#     used as its canonical name.  If the value can be reached by
#     multiple sequences of identifiers (i.e., if it has multiple
#     aliases), then one of those sequences of identifiers is used.  If
#     the value cannot be reached by any sequence of identifiers (e.g.,
#     if it was used as a base class but then its variable was deleted),
#     then its canonical name will start with C{'??'}.  If necessary, a
#     dash followed by a number will be appended to the end of a
#     non-reachable identifier to make its canonical name unique.

#     If C{DocIndexer} finds a C{ValueDoc} with an C{imported_from}
#     value, then it will replace it with the C{ValueDoc} whose
#     canonical name is C{imported_from}, if such a C{ValueDoc} is
#     found.

#     C{DocIndexer} also initializes the C{canonical_container}
#     properties of all C{ValueDoc}s reachable from the given set.
#     """
#     def index(self, valuedocs):
#         docindex = {} # maps dottedname -> val_doc
#         score_dict = {}
#         cyclecheck = Set()

#         # Find canonical names for all variables & values, and add
#         # them to the docindex.
#         for val_doc in valuedocs:
#             self._index(docindex, val_doc, val_doc.canonical_name,
#                        0, score_dict, cyclecheck)

#         # Assign canonical names to any variables that are unreachable
#         # from the root.
#         cyclecheck = Set()
#         for val_doc in valuedocs:
#             self._unreachables(docindex, val_doc, cyclecheck)

#         # Resolve any imported_from links.
#         for name, val_doc in docindex.items():
#             # This ensures that we visit each val_doc only once:
#             if val_doc.canonical_name != name: continue
            
#             # If there are any ValueDocs that are aliases for other
#             # ValueDocs, then replace them with the source ValueDoc
#             # (if we have found it). [XX] HM NOT QUITE RIGHT??
#             if val_doc.imported_from is not UNKNOWN:
#                 if val_doc.imported_from in docindex:
#                     srcdoc = docindex[val_doc.imported_from]
#                     if srcdoc is not val_doc:
#                         val_doc.__class__ = srcdoc.__class__
#                         val_doc.__dict__ = srcdoc.__dict__

#             # Set the canonical_container attribute.
#             container_name = val_doc.canonical_name.container()
#             val_doc.canonical_container = docindex.get(container_name)

#         return docindex

#     def _index(self, docindex, val_doc, name, score, score_dict, cyclecheck):
#         if val_doc in cyclecheck: return

#         # Add this val_doc to the index.
#         docindex[name] = val_doc

#         # Use this name as the val_doc object's canonical name if
#         # either:
#         #  - The val_doc doesn't have a canonical name; or
#         #  - The current canonical name was assigned by this method,
#         #    but the new name has a better score.  (If val_doc already
#         #    had a canonical name before this method was called, then
#         #    it won't have a score in score_dict, so it won't be
#         #    replaced.)
#         # (Note: this will even assign names to values like integers
#         # and None; but that should be harmless.)
#         if ((val_doc.canonical_name is UNKNOWN or
#              (val_doc in score_dict and score>score_dict[val_doc]))):
#             score_dict[val_doc] = score
#             val_doc.canonical_name = name

#         # If this ValueDoc is a namespace, then recurse to its variables.
#         cyclecheck.add(val_doc)

#         for var_doc in self._vardocs_reachable_from(val_doc):
#             varname = DottedName(name, var_doc.name)
#             # Find the score for this name.  Give decreased score to
#             # imported variables & known aliases.
#             vardoc_score = score
#             if var_doc.is_imported is UNKNOWN: vardoc_score -= 1
#             elif var_doc.is_imported: vardoc_score -= 10
#             if var_doc.is_alias is UNKNOWN: vardoc_score -= 1
#             elif var_doc.is_alias: vardoc_score -= 100
#             if var_doc.value is not UNKNOWN:
#                 self._index(docindex, var_doc.value, varname,
#                             vardoc_score, score_dict, cyclecheck)

#         cyclecheck.remove(val_doc)

#     # [XX] NEED TO ADD NUMBERS TO MAKE THESE UNIQUE?
#     def _unreachables(self, docindex, val_doc, cyclecheck):
#         if val_doc in cyclecheck: return
#         cyclecheck.add(val_doc)

#         if val_doc.canonical_name is UNKNOWN:
#             # Pick a name for the value.
#             if val_doc.imported_from not in (UNKNOWN, None):
#                 if val_doc.imported_from not in docindex:
#                     val_name = val_doc.imported_from
#                 else:
#                     val_name = DottedName('??', val_doc.imported_from)
#             elif (val_doc.pyval is not UNKNOWN and
#                 hasattr(val_doc.pyval, '__name__')):
#                 val_name = DottedName('??', val_doc.pyval.__name__)
#             else:
#                 val_name = DottedName('??')

#             # Make sure it's unique.
#             if val_name in docindex:
#                 n = 2
#                 while DottedName('%s-%s' % (val_name,n)) in docindex:
#                     n += 1
#                 val_name = DottedName('%s-%s' % (val_name,n))
                                    
#             val_doc.canonical_name = val_name

#         # Add the value to the index.
#         docindex[val_doc.canonical_name] = val_doc

#         for valuedoc2 in self._valdocs_reachable_from(val_doc):
#             self._unreachables(docindex, valuedoc2, cyclecheck)
#         for var_doc in self._vardocs_reachable_from(val_doc):
#             if var_doc.value is not UNKNOWN:
#                 self._unreachables(docindex, var_doc.value, cyclecheck)

#     def _vardocs_reachable_from(self, val_doc):
#         reachable = []
#         if (isinstance(val_doc, ClassDoc)
#             and val_doc.local_variables is not UNKNOWN):
#             reachable += val_doc.local_variables.values()
#         if (isinstance(val_doc, NamespaceDoc)
#             and val_doc.variables is not UNKNOWN):
#             reachable += val_doc.variables.values()
#         return reachable

#     def _valdocs_reachable_from(self, val_doc):
#         """
#         Return a list of all valuedocs that are directly reachable
#         from the given val_doc.  (This does not include variables of a
#         Namespace doc, since they're reachable indirectly via a
#         VariableDoc.)
#         """
#         reachable = []
#         # Recurse to any other valuedocs reachable from this val_doc.
#         if isinstance(val_doc, ModuleDoc):
#             if val_doc.package not in(UNKNOWN, None):
#                 reachable.append(val_doc.package)
#             if val_doc.submodules not in(UNKNOWN, None):
#                 reachable += val_doc.submodules
#         if isinstance(val_doc, ClassDoc):
#             if val_doc.bases is not UNKNOWN:
#                 reachable += val_doc.bases
#             if val_doc.subclasses is not UNKNOWN:
#                 reachable += val_doc.subclasses
#         if isinstance(val_doc, PropertyDoc):
#             if val_doc.fget not in (UNKNOWN, None):
#                 reachable.append(val_doc.fget)
#             if val_doc.fset not in (UNKNOWN, None):
#                 reachable.append(val_doc.fset)
#             if val_doc.fdel not in (UNKNOWN, None):
#                 reachable.append(val_doc.fdel)
#         return reachable
    
