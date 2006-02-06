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

from epydoc.apidoc import *
from sets import Set

class DocIndex:
    def __init__(self, value_index):
        self.values = []
        self.root = {}
        
        for (name, val_doc) in value_index:
            if val_doc.canonical_name != name: continue
            values.append(val_doc)
            if len(name) == 1:
                self.root.append(val_doc)

    def __get(self, name):
        # Make sure name is a DottedName.
        name = DottedName(name)

        # Get the root value specified by name[0]
        val_doc = self.root.get(name[0])
        var_doc = None

        for identifier in name[1:]:
            var_doc = val_doc[identifier]
            val_doc = var_doc.value
        return (var_doc, val_doc)
    
            
#             if isinstance(val, ModuleDoc):
#                 if identifier in val.variables:
#                     var = val.variables[identifier]
#                 elif identifier in val.subpackages:
#                     var = val.subpackages[identifier] # [xx]
#                 else:
#                     return None
#             elif isinstance(val, ClassDoc):
#                 if identifier in val.local_variables:
#                     var = val.local_variables[identifier]
#                 elif val.variables is not UNKNOWN and identifier in val.variables:
#                     var = val.variables[identifier]
#                 else:
#                     reutrn None
#            val = var.value
#        return (var, val)

    def get_variable(self, name):
        var, val = self.__get(name)
        if var is None:
            raise KeyError('Variable %s not found' % name)
        else:
            return var

    def get_value(self, name):
        var, val = self.__get(name)
        if val is None:
            raise KeyError('Value %s not found' % name)
        else:
            return val
    __getitem__ = get_value

    def __iter__(self):
        return iter(self.values)


######################################################################
## Doc Indexer
######################################################################

class DocIndexer:
    """
    A processing class that creates an index containing the API
    documentation information contained in a set of C{ValueDoc}s,
    including any C{ValueDoc}s that are reachable from that set.  This
    index is encoded as a dictionary mapping from canonical names to
    C{ValueDoc} objects, and contains a single entry for each
    C{ValueDoc} that is reachable from the original set of
    C{ValueDoc}s.

    Any C{ValueDoc} that did not already have a canonical name will be
    assigned a canonical name.  If the C{ValueDoc}'s value can be
    reached using a single sequence of identifiers (given the
    appropriate imports), then that sequence of identifiers will be
    used as its canonical name.  If the value can be reached by
    multiple sequences of identifiers (i.e., if it has multiple
    aliases), then one of those sequences of identifiers is used.  If
    the value cannot be reached by any sequence of identifiers (e.g.,
    if it was used as a base class but then its variable was deleted),
    then its canonical name will start with C{'??'}.  If necessary, a
    dash followed by a number will be appended to the end of a
    non-reachable identifier to make its canonical name unique.

    If C{DocIndexer} finds a C{ValueDoc} with an C{imported_from}
    value, then it will replace it with the C{ValueDoc} whose
    canonical name is C{imported_from}, if such a C{ValueDoc} is
    found.

    C{DocIndexer} also initializes the C{canonical_container}
    properties of all C{ValueDoc}s reachable from the given set.
    """
    def index(self, valuedocs):
        docindex = {} # maps dottedname -> val_doc
        score_dict = {}
        cyclecheck = Set()

        # Find canonical names for all variables & values, and add
        # them to the docindex.
        for val_doc in valuedocs:
            self._index(docindex, val_doc, val_doc.canonical_name,
                       0, score_dict, cyclecheck)

        cyclecheck = Set()
        for val_doc in valuedocs:
            self._unreachables(docindex, val_doc, cyclecheck)

        for name, val_doc in docindex.items():
            # This ensures that we visit each val_doc only once:
            if val_doc.canonical_name != name: continue
            
            # If there are any ValueDocs that are aliases for other
            # ValueDocs, then replace them with the source ValueDoc
            # (if we have found it). [XX] HM NOT QUITE RIGHT??
            if val_doc.imported_from is not UNKNOWN:
                if val_doc.imported_from in docindex:
                    srcdoc = docindex[val_doc.imported_from]
                    if srcdoc is not val_doc:
                        val_doc.__class__ = srcdoc.__class__
                        val_doc.__dict__ = srcdoc.__dict__

            # Set the canonical_container attribute.
            container_name = val_doc.canonical_name.container()
            val_doc.canonical_container = docindex.get(container_name)

        return docindex

    def _index(self, docindex, val_doc, name, score, score_dict, cyclecheck):
        if val_doc in cyclecheck: return

        # Add this val_doc to the index.
        docindex[name] = val_doc

        # Use this name as the val_doc object's canonical name if
        # either:
        #  - The val_doc doesn't have a canonical name; or
        #  - The current canonical name was assigned by this method,
        #    but the new name has a better score.
        # (Note: this will even assign names to values like integers
        # and None; but that should be harmless.)
        if ((val_doc.canonical_name is UNKNOWN or
             (val_doc in score_dict and score>score_dict[val_doc]))):
            score_dict[val_doc] = score
            val_doc.canonical_name = name

        # If this ValueDoc is a namespace, then recurse to its variables.
        cyclecheck.add(val_doc)

        for var_doc in self._variabledocs_reachable_from(val_doc):
            varname = DottedName(name, var_doc.name)
            
            vardoc_score = score
            if var_doc.is_imported is UNKNOWN: vardoc_score -= 1
            elif var_doc.is_imported: vardoc_score -= 10
            if var_doc.is_alias is UNKNOWN: vardoc_score -= 1
            elif var_doc.is_alias: vardoc_score -= 100
            if var_doc.value is not UNKNOWN:
                self._index(docindex, var_doc.value, varname,
                            vardoc_score, score_dict, cyclecheck)

        #for valuedoc2 in self._valuedocs_reachable_from(val_doc):
        #    self._index(docindex, valuedoc2, DottedName('??'), -10000,
        #                score_dict, cyclecheck)

        cyclecheck.remove(val_doc)

    # [XX] NEED TO ADD NUMBERS TO MAKE THESE UNIQUE?
    def _unreachables(self, docindex, val_doc, cyclecheck):
        if val_doc in cyclecheck: return
        cyclecheck.add(val_doc)

        if val_doc.canonical_name is UNKNOWN:
            # Pick a name for the value.
            if val_doc.imported_from not in (UNKNOWN, None):
                if val_doc.imported_from not in docindex:
                    val_name = val_doc.imported_from
                else:
                    val_name = DottedName('??', val_doc.imported_from)
            elif (val_doc.pyval is not UNKNOWN and
                hasattr(val_doc.pyval, '__name__')):
                val_name = DottedName('??', val_doc.pyval.__name__)
            else:
                val_name = DottedName('??')

            # Make sure it's unique.
            if val_name in docindex:
                n = 2
                while DottedName('%s-%s' % (val_name,n)) in docindex:
                    n += 1
                val_name = DottedName('%s-%s' % (val_name,n))
                                    
            val_doc.canonical_name = val_name

        # Add the value to the index.
        docindex[val_doc.canonical_name] = val_doc

        for valuedoc2 in self._valuedocs_reachable_from(val_doc):
            self._unreachables(docindex, valuedoc2, cyclecheck)
        for var_doc in self._variabledocs_reachable_from(val_doc):
            if var_doc.value is not UNKNOWN:
                self._unreachables(docindex, var_doc.value, cyclecheck)
                                   

    def _variabledocs_reachable_from(self, val_doc):
        val_docs = []
        if (isinstance(val_doc, ClassDoc)
            and val_doc.local_variables is not UNKNOWN):
            val_docs += val_doc.local_variables.values()
        if (isinstance(val_doc, NamespaceDoc)
            and val_doc.variables is not UNKNOWN):
            val_docs += val_doc.variables.values()
        return val_docs

    def _valuedocs_reachable_from(self, val_doc):
        """
        Return a list of all valuedocs that are directly reachable
        from the given val_doc.  (This does not include variables of a
        Namespace doc, since they're reachable indirectly via a
        VariableDoc.)
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
    
