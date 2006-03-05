# epydoc -- Driver
#
# Copyright (C) 2005 Edward Loper
# Author: Edward Loper <edloper@loper.org>
# URL: <http://epydoc.sf.net>
#
# $Id$

"""
The top-level programmatic interface to epydoc.
"""

######################################################################
## Contents
######################################################################
## 1. build_docs() -- the main interface.
## 2. merge_docs() -- helper, used to merge parse & inspect info
## 3. link_imports() -- helper, used to connect imported vars w/ values
## 4. assign_canonical_names() -- helper, used to set canonical names
## 5. inherit_docs() -- helper, used to inherit docs from base classes

######################################################################
## Imports
######################################################################

import sys, os, os.path, __builtin__
from epydoc.apidoc import *
from epydoc.docinspector import inspect_docs
from epydoc.docparser import parse_docs, ParseError
from epydoc.docstringparser import parse_docstring
from epydoc import log

from epydoc.util import * # [xx] hmm

######################################################################
## 1. build_docs()
######################################################################

def build_doc_index(self, items, inspect=True, parse=True):
    return DocBuilder(inspect, parse).build_doc_index(*items)

class DocBuilder:
    def __init__(self, inspect=True, parse=True):
        if not parse and not inspect:
            raise ValueError, 'either parse or inspect must be true.'
        self.inspect = inspect
        self.parse = parse

        self._progress_estimator = None
        """A L{_ProgressEstimator} used to keep track of progress when
        generating the initial docs for the given items.  (It is not
        known in advance how many items a package directory will
        contain, since it might depend on those packages' __path__
        values.)"""
            
    #/////////////////////////////////////////////////////////////////
    # Interface Methods
    #/////////////////////////////////////////////////////////////////

    def build_doc(self, item):
        """
        Build API documentation for a given item, and return it as
        an L{APIDoc} object.
        """
        docindex = self.build_doc_index(item)
        return docindex.root[0]

    def build_doc_index(self, *items):
        """
        Build API documentation for the given list of items, and
        return it in the form of a L{DocIndex}.  Each item can be any
        of the following (tried in order):
          - A string naming a python package directory
            (e.g., C{'epydoc/markup'})
          - A string naming a python file
            (e.g., C{'epydoc/docparser.py'})
          - A string naming a python object
            (e.g., C{'epydoc.docparser.DocParser'})
          - A (non-string) python object
            (e.g., C{list.append})
        """
        # Get the basic docs for each item.
        doc_pairs = self._get_docs_from_items(items)

        # Merge the inspection & parse docs.
        if self.parse and self.inspect:
            log.start_progress('Merging parsed & inspected information')
            docs = []
            for i, (inspect_doc, parse_doc) in enumerate(doc_pairs):
                if inspect_doc is not None and parse_doc is not None:
                    if inspect_doc.canonical_name not in (None, UNKNOWN):
                        name = inspect_doc.canonical_name
                    else:
                        name = parse_doc.canonical_name
                    log.progress(float(i)/len(doc_pairs), name)
                    docs.append(merge_docs(inspect_doc, parse_doc))
                elif inspect_doc is not None:
                    docs.append(inspect_doc)
                elif parse_doc is not None:
                    docs.append(parse_doc)
            log.end_progress()
        elif self.inspect:
            docs = [doc_pair[0] for doc_pair in doc_pairs if doc_pair[0]]
        else:
            docs = [doc_pair[1] for doc_pair in doc_pairs if doc_pair[1]]

        # Collect the docs into a single index.
        docindex = DocIndex(docs)

        # Replace any proxy valuedocs that we got from importing with
        # their targets.
        if self.parse:
            log.start_progress('Linking imported variables')
            reachable_valdocs = docindex.reachable_valdocs(True)
            for i, val_doc in enumerate(reachable_valdocs):
                self._report_valdoc_progress(i, val_doc, reachable_valdocs)
                link_imports(val_doc, docindex)
            log.end_progress()

        # Assign canonical names.
        log.start_progress('Indexing documentation')
        reachable_valdocs = docindex.reachable_valdocs(True)
        for i, val_doc in enumerate(reachable_valdocs):
            log.progress(float(i)/len(docindex.root), val_doc.canonical_name)
            assign_canonical_names(val_doc, val_doc.canonical_name, docindex)
        log.end_progress()
    
        # Parse the docstrings for each object.
        log.start_progress('Parsing docstrings')
        for i, val_doc in enumerate(reachable_valdocs):
            self._report_valdoc_progress(i, val_doc, reachable_valdocs)
            # the value's docstring
            parse_docstring(val_doc, docindex)
            # the value's variables' docstrings
            if (isinstance(val_doc, NamespaceDoc) and
                val_doc.variables not in (None, UNKNOWN)):
                for var_doc in val_doc.variables.values():
                    parse_docstring(var_doc, docindex)
        log.end_progress()
    
        # Take care of inheritance.
        log.start_progress('Inheriting documentation')
        for i, val_doc in enumerate(reachable_valdocs):
            if isinstance(val_doc, ClassDoc):
                percent = float(i)/len(reachable_valdocs)
                log.progress(percent, val_doc.canonical_name)
                inherit_docs(val_doc)
        log.end_progress()

        # Initialize the groups & sortedvars attributes.
        log.start_progress('Sorting & Grouping')
        for i, val_doc in enumerate(reachable_valdocs):
            if isinstance(val_doc, NamespaceDoc):
                percent = float(i)/len(reachable_valdocs)
                log.progress(percent, val_doc.canonical_name)
                val_doc.init_sorted_variables()
                val_doc.init_groups()
        log.end_progress()

        return docindex

    def _report_valdoc_progress(self, i, val_doc, val_docs):
        if (isinstance(val_doc, (ModuleDoc, ClassDoc)) and
            val_doc.canonical_name != UNKNOWN and
            not val_doc.canonical_name[0].startswith('??')):
            log.progress(float(i)/len(val_docs), val_doc.canonical_name)

    #/////////////////////////////////////////////////////////////////
    # Documentation Generation
    #/////////////////////////////////////////////////////////////////

    def _get_docs_from_items(self, items):
        # Start the progress bar.
        log.start_progress('Building documentation')
        self._progress_estimator = self._ProgressEstimator(items)

        # Collect (inspectdoc, parsedoc) pairs for each item.
        doc_pairs = []
        for item in items:
            if isinstance(item, basestring):
                if is_module_file(item):
                    doc_pairs.append(self._get_docs_from_module_file(item))
                elif is_package_dir(item):
                    doc_pairs += self._get_docs_from_package_dir(item)
                # [xx] add a case for is_py_script.

                ## builtins:
                elif hasattr(__builtin__, item):
                    val = getattr(__builtin__, item)
                    doc_pairs.append(self._get_docs_from_pyobject(val))
                elif is_pyname(item):
                    # what about builtins here..?
                    doc_pairs.append(self._get_docs_from_pyname(item))
                elif os.path.isdir(item):
                    log.error("Directory %r is not a package" % item)
                elif os.path.isfile(item):
                    log.error("File %s is not a Python module" % item)
                else:
                    log.error("Could not find a file or object named %s" %
                              item)
            else:
                doc_pairs.append(self._get_docs_from_pyobject(item))
                
        log.end_progress()
        return doc_pairs

    def _get_docs_from_pyobject(self, obj):
        self._progress_estimator.complete += 1
        log.progress(self._progress_estimator.progress(), `obj`)
        
        inspect_doc = parse_doc = None
        if self.inspect:
            try:
                inspect_doc = inspect_docs(value=obj)
            except ImportError, e:
                log.error(e)
        if self.parse:
            pass # [xx] do something for parse??
        return (inspect_doc, parse_doc)

    def _get_docs_from_pyname(self, name):
        self._progress_estimator.complete += 1
        log.progress(self._progress_estimator.progress(), name)
        
        inspect_doc = parse_doc = None
        if self.parse:
            try:
                parse_doc = parse_docs(name=name)
            except ParseError, e:
                log.error(e)
            except ImportError, e:
                log.error('While parsing %s: %s' % (name, e))
        if self.inspect:
            try:
                inspect_doc = inspect_docs(name=name)
            except ImportError, e:
                log.error(e)
        return (inspect_doc, parse_doc)

    def _get_docs_from_module_file(self, filename, parent_docs=(None,None)):
        """
        Construct and return the API documentation for the python
        module with the given filename.

        @param parent_doc: The C{ModuleDoc} of the containing package.
            If C{parent_doc} is not provided, then this method will
            check if the given filename is contained in a package; and
            if so, it will construct a stub C{ModuleDoc} for the
            containing package(s).
        """
        # Record our progress.
        modulename = os.path.splitext(os.path.split(filename)[1])[0]
        if modulename == '__init__':
            modulename = os.path.split(os.path.split(filename)[0])[1]
        if parent_docs[0]:
            modulename = DottedName(parent_docs[0].canonical_name, modulename)
        elif parent_docs[1]:
            modulename = DottedName(parent_docs[1].canonical_name, modulename)
        log.progress(self._progress_estimator.progress(),
                     '%s (%s)' % (modulename, filename))
        self._progress_estimator.complete += 1
        
        # Normalize the filename.
        filename = os.path.normpath(os.path.abspath(filename))

        # When possible, use the source version of the file.
        try: filename = py_src_filename(filename)
        except ValueError: pass

        # Get the inspected & parsed docs (as appropriate)
        inspect_doc = parse_doc = None
        if self.inspect:
            try:
                inspect_doc = inspect_docs(
                    filename=filename, context=parent_docs[0])
            except ImportError, e:
                log.error(e)
        if self.parse:
            try:
                parse_doc = parse_docs(
                    filename=filename, context=parent_docs[1])
            except ParseError, e:
                log.error(e)
            except ImportError, e:
                log.error('While parsing %s: %s' % (filename, e))
        return (inspect_doc, parse_doc)

    def _get_docs_from_package_dir(self, package_dir, parent_docs=(None,None)):
        pkg_dir = os.path.normpath(os.path.abspath(package_dir))
        pkg_file = os.path.join(pkg_dir, '__init__')
        pkg_docs = self._get_docs_from_module_file(pkg_file, parent_docs)

        # Extract the package's __path__.
        if pkg_docs == (None, None):
            return []
        elif pkg_docs[0] is not None:
            pkg_path = pkg_docs[0].path
        else:
            pkg_path = pkg_docs[1].path
  
        module_filenames = {}
        subpackage_dirs = Set()
        for subdir in pkg_path:
            if os.path.isdir(subdir):
                for name in os.listdir(subdir):
                    filename = os.path.join(subdir, name)
                    # Is it a valid module filename?
                    if is_module_file(filename):
                        basename = os.path.splitext(filename)[0]
                        if os.path.split(basename)[1] != '__init__':
                            module_filenames[basename] = filename
                    # Is it a valid package filename?
                    if is_package_dir(filename):
                        subpackage_dirs.add(filename)

        # Update our estimate of the number of modules in this package.
        self._progress_estimator.revise_estimate(package_dir,
                                                 module_filenames.items(),
                                                 subpackage_dirs)

        docs = [pkg_docs]
        for module_filename in module_filenames.values():
            d = self._get_docs_from_module_file(module_filename, pkg_docs)
            docs.append(d)
        for subpackage_dir in subpackage_dirs:
            docs += self._get_docs_from_package_dir(subpackage_dir, pkg_docs)
        return docs

    #/////////////////////////////////////////////////////////////////
    # Progress Estimation (for Documentation Generation)
    #/////////////////////////////////////////////////////////////////
    
    class _ProgressEstimator:
        def __init__(self, items):
            self.est_totals = {}
            self.complete = 0
            
            for item in items:
                if is_package_dir(item):
                    self.est_totals[item] = self._est_pkg_modules(item)
                else:
                    self.est_totals[item] = 1

        def progress(self):
            total = sum(self.est_totals.values())
            return float(self.complete) / total

        def revise_estimate(self, pkg_item, modules, subpackages):
            del self.est_totals[pkg_item]
            for item in modules:
                self.est_totals[item] = 1
            for item in subpackages:
                self.est_totals[item] = self._est_pkg_modules(item)

        def _est_pkg_modules(self, package_dir):
            num_items = 0
            
            if is_package_dir(package_dir):
                for name in os.listdir(package_dir):
                    filename = os.path.join(package_dir, name)
                    if is_module_file(filename):
                        num_items += 1
                    elif is_package_dir(filename):
                        num_items += self._est_pkg_modules(filename)
                        
            return num_items
        
######################################################################
## Doc Merger
######################################################################

MERGE_PRECEDENCE = {
    'repr': 'parse',
    'canonical_name': 'inspect', # hmm.. change this? [xx]
    'is_imported': 'parse',
    'is_alias': 'parse',
    'docformat': 'parse',
    'is_package': 'parse',
    'sort_spec': 'parse',
    'subpackages': 'inspect',
    'filename': 'parse',
    }
DEFAULT_MERGE_PRECEDENCE = 'inspect'

_attribute_mergefunc_registry = {}
def register_attribute_mergefunc(attrib, mergefunc):
    """
    Register an attribute merge function.  This function will be
    called by L{merge_docs()} when it needs to merge the attribute
    values of two C{APIDoc}s.

    @param attrib: The name of the attribute whose values are merged
    by C{mergefunc}.

    @param mergefun: The merge function, whose sinature is:

    >>> def mergefunc(inspect_val, parse_val, precedence, cyclecheck, path):
    ...     return calculate_merged_value(inspect_val, parse_val)

    Where C{inspect_val} and C{parse_val} are the two values to
    combine; C{precedence} is a string indicating which value takes
    precedence for this attribute (C{'inspect'} or C{'parse'});
    C{cyclecheck} is a value used by C{merge_docs()} to make sure that
    it only visits each pair of docs once; and C{path} is a string
    describing the path that was taken from the root to this
    attribute (used to generate log messages).

    If the merge function needs to call C{merge_docs}, then it should
    pass C{cyclecheck} and C{path} back in.  (When appropriate, a
    suffix should be added to C{path} to describe the path taken to
    the merged values.)
    """
    _attribute_mergefunc_registry[attrib] = mergefunc

def merge_docs(inspect_doc, parse_doc, cyclecheck=None, path=None):
    """
    Merge the API documentation information that was obtained from
    inspection with information that was obtained from parsing.
    C{inspect_doc} and C{parse_doc} should be two C{APIDoc} instances
    that describe the same object.  C{merge_docs} combines the
    information from these two instances, and returns the merged
    C{APIDoc}.

    If C{inspect_doc} and C{parse_doc} are compatible, then they will
    be I{merged} -- i.e., they will be coerced to a common class, and
    their state will be stored in a shared dictionary.  Once they have
    been merged, any change made to the attributes of one will affect
    the other.  The value for the each of the merged C{APIDoc}'s
    attributes is formed by combining the values of the source
    C{APIDoc}s' attributes, as follows:

      - If either of the source attributes' value is C{UNKNOWN}, then
        use the other source attribute's value.
      - Otherwise, if an attribute merge function has been registered
        for the attribute, then use that function to calculate the
        merged value from the two source attribute values.
      - Otherwise, if L{MERGE_PRECEDENCE} is defined for the
        attribute, then use the attribute value from the source that
        it indicates.
      - Otherwise, use the attribute value from the source indicated
        by L{DEFAULT_MERGE_PRECEDENCE}.

    If C{inspect_doc} and C{parse_doc} are I{not} compatible (e.g., if
    their values have incompatible types), then C{merge_docs()} will
    simply return either C{inspect_doc} or C{parse_doc}, depending on
    the value of L{DEFAULT_MERGE_PRECEDENCE}.  The two input
    C{APIDoc}s will not be merged or modified in any way.

    @param cyclecheck, path: These arguments should only be provided
        when C{merge_docs()} is called by an attribute merge
        function.  See L{register_attribute_mergefunc()} for more
        details.
    """
    assert isinstance(inspect_doc, APIDoc)
    assert isinstance(parse_doc, APIDoc)

    if cyclecheck is None:
        cyclecheck = Set()
        if inspect_doc.canonical_name not in (None, UNKNOWN):
            path = '%s' % inspect_doc.canonical_name
        elif parse_doc.canonical_name not in (None, UNKNOWN):
            path = '%s' % parse_doc.canonical_name
        else:
            path = '??'


    # If we've already examined this pair, then there's nothing
    # more to do.  The reason that we check id's here is that we
    # want to avoid hashing the APIDoc objects for now, so we can
    # use APIDoc.merge_and_overwrite() later.
    if (id(inspect_doc), id(parse_doc)) in cyclecheck:
        return inspect_doc
    cyclecheck.add( (id(inspect_doc), id(parse_doc)) )

    # If these two are already merged, then we're done.  (Two
    # APIDoc's compare equal iff they are identical or have been
    # merged.)
    if inspect_doc == parse_doc:
        return inspect_doc

    # Perform several sanity checks here -- if we accidentally
    # merge values that shouldn't get merged, then bad things can
    # happen.
    mismatch = None
    if (inspect_doc.__class__ != parse_doc.__class__ and
        not (issubclass(inspect_doc.__class__, parse_doc.__class__) or
             issubclass(parse_doc.__class__, inspect_doc.__class__))):
        mismatch = ("value types don't match -- i=%r, p=%r." %
                    (inspect_doc.__class__, parse_doc.__class__))
    if (isinstance(inspect_doc, ValueDoc) and
        isinstance(parse_doc, ValueDoc)):
        if (inspect_doc.pyval is not UNKNOWN and
            parse_doc.pyval is not UNKNOWN and
            inspect_doc.pyval is not parse_doc.pyval):
            mismatch = "values don't match."
        elif (inspect_doc.canonical_name not in (None, UNKNOWN) and
            parse_doc.canonical_name not in (None, UNKNOWN) and
            inspect_doc.canonical_name != parse_doc.canonical_name):
            mismatch = "canonical names don't match."
    if mismatch is not None:
        log.info("Not merging the parsed & inspected values of %s, "
                 "since their %s" % (path, mismatch))
        if DEFAULT_MERGE_PRECEDENCE == 'inspect':
            return inspect_doc
        else:
            return parse_doc

    # If one apidoc's class is a superclass of the other's, then
    # specialize it to the more specific class.
    if inspect_doc.__class__ is not parse_doc.__class__:
        if issubclass(inspect_doc.__class__, parse_doc.__class__):
            parse_doc.specialize_to(inspect_doc.__class__)
        if issubclass(parse_doc.__class__, inspect_doc.__class__):
            inspect_doc.specialize_to(parse_doc.__class__)
    assert inspect_doc.__class__ is parse_doc.__class__

    # The posargs and defaults are tied together -- if we merge
    # the posargs one way, then we need to merge the defaults the
    # same way.  So check them first.  (This is a minor hack)
    if (isinstance(inspect_doc, RoutineDoc) and
        isinstance(parse_doc, RoutineDoc)):
        _merge_posargs_and_defaults(inspect_doc, parse_doc, path)
    
    # Merge the two api_doc's attributes.
    for attrib in Set(inspect_doc.__dict__.keys() +
                      parse_doc.__dict__.keys()):
        # Be sure not to merge any private attributes (especially
        # __mergeset or __has_been_hashed!)
        if attrib.startswith('_'): continue
        merge_attribute(attrib, inspect_doc, parse_doc,
                             cyclecheck, path)

    # Set the dictionaries to be shared.
    return inspect_doc.merge_and_overwrite(parse_doc)

def _merge_posargs_and_defaults(inspect_doc, parse_doc, path):
    # If either is unknown, then let merge_attrib handle it.
    if inspect_doc.posargs == UNKNOWN or parse_doc.posargs == UNKNOWN:
        return 
        
    # If the inspected doc just has '...', then trust the parsed doc.
    if inspect_doc.posargs == ['...'] and parse_doc.posargs != ['...']:
        inspect_doc.posargs = parse_doc.posargs
        inspect_doc.posarg_defaults = parse_doc.posarg_defaults

    # If they are incompatible, then check the precedence.
    elif inspect_doc.posargs != parse_doc.posargs:
        log.info("Warning: Not merging the parsed & inspected arg "
                 "lists for %s, since they don't match (%s vs %s)"
                  % (path, inspect_doc.posargs, parse_doc.posargs))
        if (MERGE_PRECEDENCE.get('posargs', DEFAULT_MERGE_PRECEDENCE) ==
            'inspect'):
            parse_doc.posargs = inspect_doc.posargs
            parse_doc.posarg_defaults = inspect_doc.posarg_defaults
        else:
            inspect_doc.posargs = parse_doc.posargs
            inspect_doc.posarg_defaults = parse_doc.posarg_defaults

def merge_attribute(attrib, inspect_doc, parse_doc, cyclecheck, path):
    precedence = MERGE_PRECEDENCE.get(attrib, DEFAULT_MERGE_PRECEDENCE)
    if precedence not in ('parse', 'inspect'):
        raise ValueError('Bad precedence value %r' % precedence)
    
    if (getattr(inspect_doc, attrib) is UNKNOWN and
        getattr(parse_doc, attrib) is not UNKNOWN):
        setattr(inspect_doc, attrib, getattr(parse_doc, attrib))
    elif (getattr(inspect_doc, attrib) is not UNKNOWN and
          getattr(parse_doc, attrib) is UNKNOWN):
        setattr(parse_doc, attrib, getattr(inspect_doc, attrib))
    elif (getattr(inspect_doc, attrib) is UNKNOWN and
          getattr(parse_doc, attrib) is UNKNOWN):
        pass
    else:
        # Both APIDoc objects have values; we need to merge them.
        inspect_val = getattr(inspect_doc, attrib)
        parse_val = getattr(parse_doc, attrib)
        if attrib in _attribute_mergefunc_registry:
            handler = _attribute_mergefunc_registry[attrib]
            merged_val = handler(inspect_val, parse_val, precedence,
                                 cyclecheck, path)
        elif precedence == 'inspect':
            merged_val = inspect_val
        elif precedence == 'parse':
            merged_val = parse_val

        setattr(inspect_doc, attrib, merged_val)
        setattr(parse_doc, attrib, merged_val)

def merge_variables(varlist1, varlist2, precedence, cyclecheck, path):
    # Merge all variables that are in both sets.
    for varname, var1 in varlist1.items():
        if varname in varlist2:
            var2 = varlist2[varname]
            var = merge_docs(var1, var2, cyclecheck, path+'.'+varname)
            varlist1[varname] = var
            varlist2[varname] = var

    # Copy any variables that are not in varlist1 over.
    for varname, var in varlist2.items():
        varlist1.setdefault(varname, var)

    return varlist1

def merge_value(value1, value2, precedence, cyclecheck, path):
    if value1 is None and value2 is None:
        return None
    elif value1 is None or value2 is None:
        if precedence == 'inspect': return value1
        else: return value2
    elif value1 is UNKNOWN:
        return value2
    elif value2 is UNKNOWN:
        if precedence == 'inspect': return value1
        else: return value2
    else:
        return merge_docs(value1, value2, cyclecheck, path)

# [xx] are these really necessary or useful??
def merge_package(v1, v2, precedence, cyclecheck, path):
    return merge_value(v1, v2, precedence, cyclecheck, path+'.<package>')
def merge_container(v1, v2, precedence, cyclecheck, path):
    return merge_value(v1, v2, precedence, cyclecheck, path+'.<container>')
def merge_overrides(v1, v2, precedence, cyclecheck, path):
    return merge_value(v1, v2, precedence, cyclecheck, path+'.<overrides>')
def merge_fget(v1, v2, precedence, cyclecheck, path):
    return merge_value(v1, v2, precedence, cyclecheck, path+'.fget')
def merge_fset(v1, v2, precedence, cyclecheck, path):
    return merge_value(v1, v2, precedence, cyclecheck, path+'.fset')
def merge_fdel(v1, v2, precedence, cyclecheck, path):
    return merge_value(v1, v2, precedence, cyclecheck, path+'.fdel')

def merge_imported_from(v1, v2, precedence, cyclecheck, path):
    # Anything we got from inspection shouldn't have an imported_from
    # attribute -- it should be the actual object's documentation.
    assert v1 is None
    return None

def merge_bases(baselist1, baselist2, precedence, cyclecheck, path):
    # Be careful here -- if we get it wrong, then we could end up
    # merging two unrelated classes, which could lead to bad
    # things (e.g., a class that's its own subclass).  So only
    # merge two bases if we're quite sure they're the same class.
    # (In particular, if they have the same canonical name.)

    # If the lengths don't match up, then give up.  This is most
    # often caused by __metaclass__.
    if len(baselist1) != len(baselist2):
        log.info("Warning: Not merging the inspected & parsed base lists "
                 "for %s, since their lengths don't match (%s vs %s)" %
                 (path, len(baselist1), len(baselist2)))
        if precedence == 'inspect': return baselist1
        else: return baselist2

    # If any names disagree, then give up.
    for base1, base2 in zip(baselist1, baselist2):
        if ((base1.canonical_name not in (None, UNKNOWN) and
             base2.canonical_name not in (None, UNKNOWN)) and
            base1.canonical_name != base2.canonical_name):
            log.info("Warning: Not merging the parsed & inspected base "
                     "lists for %s, since the bases' names don't match "
                     "(%s vs %s)" % (path, base1.canonical_name,
                                     base2.canonical_name))
            if precedence == 'inspect': return baselist1
            else: return baselist2

    for i, (base1, base2) in enumerate(zip(baselist1, baselist2)):
        base = merge_docs(base1, base2, cyclecheck,
                           '%s.__bases__[%d]' % (path, i))
        baselist1[i] = baselist2[i] = base

    return baselist1

def merge_posarg_defaults(defaults1, defaults2, precedence,
                          cyclecheck, path):
    if len(defaults1) != len(defaults2):
        if precedence == 'inspect': return defaults1
        else: return defaults2
    defaults = []
    for i, (d1, d2) in enumerate(zip(defaults1, defaults2)):
        if d1 is not None and d2 is not None:
            d_path = '%s.<default-arg-val>[%d]' % (path, i)
            defaults.append(merge_docs(d1, d2, cyclecheck, d_path))
        elif precedence == 'inspect':
            defaults.append(d1)
        else:
            defaults.append(d2)
    return defaults

register_attribute_mergefunc('variables', merge_variables)
register_attribute_mergefunc('value', merge_value)
# [xx] are these useful/necessary?
#register_attribute_mergefunc('package', merge_package)
#register_attribute_mergefunc('container', merge_container)
register_attribute_mergefunc('overrides', merge_overrides)
register_attribute_mergefunc('fget', merge_fget)
register_attribute_mergefunc('fset', merge_fset)
register_attribute_mergefunc('fdel', merge_fdel)
register_attribute_mergefunc('imported_from', merge_imported_from)
register_attribute_mergefunc('bases', merge_bases)
register_attribute_mergefunc('posarg_defaults', merge_posarg_defaults)

######################################################################
## Import Linking
######################################################################

def link_imports(val_doc, docindex):
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
        # So just get rid of the variable.
        elif src_doc == val_doc:
            parent_name = DottedName(*val_doc.imported_from[:-1])
            var_name = val_doc.imported_from[-1]
            parent = docindex.get_valdoc(parent_name)
            if parent is not None and var_name in parent.variables:
                del parent.variables[var_name]
            src_doc.imported_from = None

######################################################################
## Canonical Name Assignment
######################################################################

_name_scores = {}
"""A dictionary mapping from each C{ValueDoc} to the score that has
been assigned to its current cannonical name.  If
L{assign_canonical_names()} finds a canonical name with a better
score, then it will replace the old name."""

_unreachable_names = Set()
"""The set of names that have been used for unreachable objects.  This
is used to ensure there are no duplicate cannonical names assigned."""

def assign_canonical_names(val_doc, name, docindex, score=0):
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
        
        assign_canonical_names(var_doc.value, varname, docindex, vardoc_score)

    # Recurse to any directly reachable values.
    for val_doc_2 in val_doc.valdoc_links():
        val_name, val_score = _unreachable_name_for(val_doc_2, docindex)
        assign_canonical_names(val_doc_2, val_name, docindex, val_score)

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
## Documentation Inheritance
######################################################################

def inherit_docs(class_doc):
    for base_class in list(class_doc.mro()):
        if base_class == class_doc: continue
        if base_class.variables is UNKNOWN: continue

        for name, var_doc in base_class.variables.items():
            # If it's a __private variable, then don't inherit it.
            if name.startswith('__') and not name.endswith('__'):
                continue
            
            # If class_doc doesn't have a variable with this name,
            # then inherit it.
            if name not in class_doc.variables:
                class_doc.variables[name] = var_doc

            # Otherwise, class_doc already contains a variable
            # that shadows var_doc.  But if class_doc's var is
            # local, then record the fact that it overrides
            # var_doc.
            elif (class_doc.variables[name].container==class_doc and
                  class_doc.variables[name].overrides is UNKNOWN):
                class_doc.variables[name].overrides = var_doc
                _inherit_info(class_doc.variables[name])

def _inherit_info(var_doc):
    """
    Inherit..
      - descr
      - summary
      - metadata??
      - param descrs & types?
      
    """
    # [XX] flesh this out!
    if var_doc.descr in (None, UNKNOWN):
        var_doc.descr = var_doc.overrides.descr
    if (var_doc.value not in (None, UNKNOWN) and
        var_doc.value.descr in (None, UNKNOWN)):
        var_doc.value.descr = var_doc.overrides.value.descr

