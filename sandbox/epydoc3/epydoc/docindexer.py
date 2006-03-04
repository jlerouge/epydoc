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

######################################################################
## Canonical Names
######################################################################
# [xx] Should score_dict and unreachable_names be module-level vars??
# that would mean that if we come back and run add_canonical_names
# again on a given set of apidoc objects, we'll still be ok.

_name_scores = {}
"""A dictionary mapping from each C{ValueDoc} to the score that has
been assigned to its current cannonical name.  If
L{_assign_canonical_names()} finds a cannonical name with a better
score, then it will replace the old name."""

_unreachable_names = Set()
"""The set of names that have been used for unreachable objects.  This
is used to ensure there are no duplicate cannonical names assigned."""

def add_canonical_names(docindex):
    log.start_progress('Indexing documentation')
    for i, val_doc in enumerate(docindex.root):
        log.progress(float(i)/len(docindex.root), val_doc.canonical_name)
        _assign_canonical_names(val_doc, val_doc.canonical_name,
                                docindex, 0)
    log.end_progress()

def _assign_canonical_names(val_doc, name, docindex, score):
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
    if val_doc in _name_scores and score <= _name_scores[val_doc]:
        return

    # Update val_doc's canonical name, if appropriate.
    if (val_doc not in _name_scores and
        val_doc.canonical_name is not UNKNOWN):
        # If this is the fist time we've seen val_doc, and it
        # already has a name, then don't change that name.
        _name_scores[val_doc] = sys.maxint
        name = val_doc.canonical_name
        score = 0
    else:
        # Otherwise, update the name iff the new score is better
        # than the old one.
        if (val_doc not in _name_scores or
            score > _name_scores[val_doc]):
            val_doc.canonical_name = name
            _name_scores[val_doc] = score

    # Recurse to any contained values.
    for var_doc in val_doc.vardoc_links():
        if var_doc.value is UNKNOWN: continue
        varname = DottedName(name, var_doc.name)

        # This check is for cases like curses.wrapper, where an
        # imported variable shadows its value's "real" location.
        if _var_shadows_self(var_doc, varname):
            _fix_self_shadowing_var(var_doc, varname, docindex)

        # Find the score for this new name.            
        vardoc_score = score-1
        if var_doc.is_imported is UNKNOWN: vardoc_score -= 10
        elif var_doc.is_imported: vardoc_score -= 100
        if var_doc.is_alias is UNKNOWN: vardoc_score -= 10
        elif var_doc.is_alias: vardoc_score -= 1000
        
        _assign_canonical_names(var_doc.value, varname, docindex, vardoc_score)

    # Recurse to any directly reachable values.
    for val_doc_2 in val_doc.valdoc_links():
        val_name, val_score = _unreachable_name_for(val_doc_2, docindex)
        _assign_canonical_names(val_doc_2, val_name, docindex, val_score)

def _var_shadows_self(var_doc, varname):
    return (var_doc.value not in (None, UNKNOWN) and
            var_doc.value.canonical_name not in (None, UNKNOWN) and
            var_doc.value.canonical_name != varname and
            varname.dominates(var_doc.value.canonical_name))

def _fix_self_shadowing_var(var_doc, varname, docindex):
    # If possible, find another name for the shadowed value.
    cname = var_doc.value.canonical_name
    for i in range(1, len(cname)-1):
        new_name = DottedName(*(cname[:i]+(cname[i]+"'",)+cname[i+1:]))
        val_doc = docindex.get_valdoc(new_name)
        if val_doc is not None:
            log.warning("%s shadows its own value -- using %s instead" %
                        (varname, new_name))
            var_doc.value = val_doc
            return

    # If we couldn't find the actual value, then at least
    # invalidate the canonical name.
    log.warning('%s shadows itself' % varname)
    del var_doc.value.canonical_name

def _unreachable_name_for(val_doc, docindex):
    assert isinstance(val_doc, ValueDoc)
    
    # [xx] (when) does this help?
    if (isinstance(val_doc, ModuleDoc) and
        len(val_doc.canonical_name)==1 and val_doc.package is None):
        for root_val in docindex.root:
            if root_val.canonical_name == val_doc.canonical_name:
                if root_val != val_doc: 
                    log.error("Name conflict: %r vs %r" %
                              (val_doc, root_val))
                break
        else:
            return val_doc.canonical_name, -1000

    # Assign it an 'unreachable' name:
    if (val_doc.pyval is not UNKNOWN and
          hasattr(val_doc.pyval, '__name__')):
        try:
            name = DottedName(DottedName.UNREACHABLE,
                              val_doc.pyval.__name__)
        except ValueError:
            name = DottedName(DottedName.UNREACHABLE)
    else:
        name = DottedName(DottedName.UNREACHABLE)

    # Uniquify the name.
    if name in _unreachable_names:
        n = 2
        while DottedName('%s-%s' % (name,n)) in _unreachable_names:
            n += 1
        name = DottedName('%s-%s' % (name,n))
    _unreachable_names.add(name)
    
    return name, -10000

######################################################################
## Linking
######################################################################

def link_imports(docindex):
    log.start_progress('Resolving imports')

    # Get the set of all ValueDocs that are reachable from the root.
    reachable_val_docs = docindex.reachable_valdocs()
    
    for i, val_doc in enumerate(reachable_val_docs):
        # Report on our progress.
        if i % 100 == 0:
            percent = float(i)/len(reachable_val_docs)
            log.progress(percent, '%d%% resolved' % (100.*percent))

        # Check if the ValueDoc has an unresolved imported_from link.
        # If so, then resolve it.
        while val_doc.imported_from not in (UNKNOWN, None):
            # Find the valuedoc that the imported_from name points to.
            src_doc = docindex.get_valdoc(val_doc.imported_from)

            # If we don't have any valuedoc at that address, then
            # promote this proxy valuedoc to a full (albeit empty)
            # one.
            if src_doc is None:
                val_doc.canonical_name = val_doc.imported_from
                val_doc.imported_from = None
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
                parent = docindex.get_valdoc(parent_name)
                try:
                    del parent.variables[var_name]
                except KeyError:
                    log.error("HMmm %s %s %r %r" %
                              (parent_name, var_name, parent, src_doc))

    log.end_progress()
