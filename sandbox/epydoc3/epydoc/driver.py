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
## Imports
######################################################################

import sys, os, os.path, __builtin__
from epydoc.apidoc import *
from epydoc.docinspector import DocInspector
from epydoc.docparser import DocParser, ParseError
from epydoc.docmerger import DocMerger
from epydoc.docindexer import DocIndex
from epydoc.docstringparser import DocstringParser
from epydoc.docinheriter import DocInheriter
from epydoc.docwriter.plaintext import PlaintextWriter
from epydoc import log

from epydoc.util import * # [xx] hmm


######################################################################
## The Driver
######################################################################

class DocBuilder:
    def __init__(self, inspect=True, parse=True, inspector=None,
                 parser=None, merger=None, docstring_parser=None,
                 inheriter=None):
        if not parse and not inspect:
            raise ValueError, 'either parse or inspect must be true.'
        self.inspect = inspect
        self.parse = parse

        # Defaults for the tool chain.
        if inspector is None:
            inspector = DocInspector()
        if parser is None:
            parser = DocParser(inspector.inspect(value=__builtin__))
        if merger is None:
            merger = DocMerger()
        if docstring_parser is None:
            docstring_parser = DocstringParser()
        if inheriter is None:
            inheriter = DocInheriter()

        self.inspector = inspector
        """The L{DocInspector} that should be used to inspect python
        objects and extract their documentation information."""
        
        self.parser = parser
        """The L{DocParser} that should be used to parse python source
        files, and extract documentation about the objects they contain."""
        
        self.merger = merger
        """The L{DocMerger} that should be used to combine information
        from the inspector and parser (when both sources of information
        are availalbe."""
        
        self.docstring_parser = docstring_parser
        """The L{DocstringParser} that should be used to parse
        the docstrings of the documented objects."""
        
        self.inheriter = inheriter
        """The L{DocInheriter} that should be used to propagate
        inherited information from base classes to their subclasses."""

        self._progress_estimator = None
        """A L{_ProgressEstimator} used to keep track of progress when
        generating the initial docs for the given items.  (It is not
        known in advance how many items a package directory will
        contain, since it might depend on those packages' __path__
        values.)"""
            
    #/////////////////////////////////////////////////////////////////
    # Interface Method
    #/////////////////////////////////////////////////////////////////

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
                    docs.append(self.merger.merge(inspect_doc, parse_doc))
                elif inspect_doc is not None:
                    docs.append(inspect_doc)
                elif parse_doc is not None:
                    docs.append(parse_doc)
            log.end_progress()
        elif self.inspect:
            docs = [doc_pair[0] for doc_pair in doc_pairs]
        else:
            docs = [doc_pair[1] for doc_pair in doc_pairs]

        # Index the docs.
        docindex = DocIndex(docs)
    
        # Parse all docstrings.  (Sort them first, so that warnings
        # from the same module get listed consecutively.)
        val_docs = sorted(docindex.reachable_valdocs,
                          key=lambda doc: doc.canonical_name)
        log.start_progress('Parsing docstrings')
        for i, val_doc in enumerate(val_docs):
            if (isinstance(val_doc, (ModuleDoc, ClassDoc)) and
                val_doc.canonical_name[0] != '??'):
                log.progress(float(i)/len(val_docs),
                             str(val_doc.canonical_name))
            self.docstring_parser.parse_docstring(val_doc)
            if (isinstance(val_doc, ClassDoc) and
                val_doc.local_variables not in (None, UNKNOWN)):
                for var_doc in val_doc.local_variables.values():
                    self.docstring_parser.parse_docstring(var_doc)
            if (isinstance(val_doc, NamespaceDoc) and
                val_doc.variables not in (None, UNKNOWN)):
                for var_doc in val_doc.variables.values():
                    self.docstring_parser.parse_docstring(var_doc)
        log.end_progress()
    
        # Take care of inheritance.
        self.inheriter.inherit(docindex)

        return docindex

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
                inspect_doc = self.inspector.inspect(value=obj)
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
                parse_doc = self.parser.parse(name=name)
            except ParseError, e:
                log.error(e)
            except ImportError, e:
                log.error('While parsing %s: %s' % (name, e))
        if self.inspect:
            try:
                inspect_doc = self.inspector.inspect(name=name)
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
                inspect_doc = self.inspector.inspect(
                    filename=filename, context=parent_docs[0])
            except ImportError, e:
                log.error(e)
        if self.parse:
            try:
                parse_doc = self.parser.parse(
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

        
