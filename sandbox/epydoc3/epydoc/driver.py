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

from epydoc.apidoc import *
from epydoc.docinspector import DocInspector
from epydoc.docparser import DocParser
from epydoc.docmerger import DocMerger
from epydoc.docindexer import DocIndex
from epydoc.docstringparser import DocstringParser
from epydoc.docinheriter import DocInheriter
from epydoc.docwriter.plaintext import PlaintextWriter
from epydoc.docwriter.html import HTMLWriter
import sys, os, os.path, __builtin__

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

#         # Don't use epytext for __builtins__ [XX HOW??]
#         import __builtin__
#         builtins = inspector.inspect(value=__builtin__)
#         for vardoc in builtins.variables.values():
#             vardoc.value.canonical_container = builtins
#         builtins.docformat = 'plaintext'

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
            
    #/////////////////////////////////////////////////////////////////
    # Interface Method
    #/////////////////////////////////////////////////////////////////

    def build_docs(self, *items):
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
        # Get the docs for each name.
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
                else:
                    raise ValueError("Don't know what to do with %s" % item)
            else:
                doc_pairs.append(self._get_docs_from_pyobject(item))

        # Merge the inspection & parse docs.
        # [xx] what to do if we have no docs for something?
        docs = [self.merge_docs(*doc_pair) for doc_pair in doc_pairs]

        # Index the docs.
        docindex = DocIndex(docs)
    
        # Parse all docstrings.
        for val_doc in docindex.reachable_valdocs:
            self.docstring_parser.parse_docstring(val_doc)
        for var_doc in docindex.reachable_vardocs:
            self.docstring_parser.parse_docstring(var_doc)
    
        # Take care of inheritance.
        self.inheriter.inherit(docindex)

        return docindex

    def merge_docs(self, inspect_doc, parse_doc):
        # Merge the docs & return them.
        if inspect_doc and parse_doc:
            return self.merger.merge(inspect_doc, parse_doc)
        elif inspect_doc:
            return inspect_doc
        elif parse_doc:
            return parse_doc
        else:
            # what to do here exactly?
            print 'Warning -- no docs found for %s' % name
            raise ValueError

    #/////////////////////////////////////////////////////////////////
    # Documentation Generation
    #/////////////////////////////////////////////////////////////////
    
    def _get_docs_from_pyobject(self, obj):
        inspect_doc = parse_doc = None
        if self.inspect:
            inspect_doc = self.inspector.inspect(value=obj)
        if self.parse:
            pass # [xx] do something for parse??
        return (inspect_doc, parse_doc)
        

    def _get_docs_from_pyname(self, name):
        inspect_doc = parse_doc = None
        if self.parse:
            try:
                parse_doc = self.parser.parse(name=name)
            except ValueError, e:
                # [xx] overly-broad except!
                print 'Error: %s' % e
        if self.inspect:
            inspect_doc = self.inspector.inspect(name=name)
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
        # Normalize the filename.
        filename = os.path.normpath(os.path.abspath(filename))

        # When possible, use the source version of the file.
        try: filename = py_src_filename(filename)
        except ValueError: pass

        # Get the inspected & parsed docs (as appropriate)
        inspect_doc = parse_doc = None
        if self.inspect:
            inspect_doc = self.inspector.inspect(
                filename=filename, context=parent_docs[0])
        if self.parse:
            try:
                parse_doc = self.parser.parse(
                    filename=filename, context=parent_docs[1])
            except ValueError, e:
                # [xx] overly-broad except!
                print 'Error: %s' % e
        return (inspect_doc, parse_doc)

    def _get_docs_from_package_dir(self, package_dir, parent_docs=(None,None)):
        package_dir = os.path.normpath(os.path.abspath(package_dir))
        pkg_file = os.path.join(package_dir, '__init__')
        pkg_docs = self._get_docs_from_module_file(pkg_file, parent_docs)

        # Extract the package's __path__.
        if pkg_docs == (None, None):
            return []
        elif pkg_docs[0] is not None:
            pkg_path = pkg_docs[0].path
        else:
            pkg_path = pkg_docs[1].path
  
        module_filenames = Set()
        subpackage_dirs = Set()
        for subdir in pkg_path:
            if os.path.isdir(subdir):
                for name in os.listdir(subdir):
                    filename = os.path.join(subdir, name)
                    # Is it a valid module filename?
                    if is_module_file(filename):
                        module_filenames.add(os.path.splitext(filename)[0])
                    # Is it a valid package filename?
                    if is_package_dir(filename):
                        subpackage_dirs.add(filename)
  
        docs = [pkg_docs]
        for module_filename in module_filenames:
            if os.path.split(module_filename)[1] != '__init__':
                d = self._get_docs_from_module_file(module_filename, pkg_docs)
                docs.append(d)
        for subpackage_dir in subpackage_dirs:
            docs += self._get_docs_from_package_dir(subpackage_dir,
                                                    pkg_docs)
        return docs

######################################################################
## Better cli..
######################################################################
import epydoc
from optparse import OptionParser, OptionGroup

def parse_arguments(args):
    # Construct the option parser.
    usage = '%prog ACTION [options] NAMES...'
    version = "Epydoc, version %s" % epydoc.__version__
    optparser = OptionParser(usage=usage, version=version)
    action_group = OptionGroup(optparser, 'Actions')
    options_group = OptionGroup(optparser, 'Options')

    # Add options -- Actions
    action_group.add_option(                                # --html
        "--html", action="store_const", dest="action", const="html",
        help="Write HTML output.")
    action_group.add_option(                                # --latex
        "--latex", action="store_const", dest="action", const="latex",
        help="Write LaTeX output. (not implemented yet)")
    action_group.add_option(                                # --dvi
        "--dvi", action="store_const", dest="action", const="dvi",
        help="Write DVI output. (not implemented yet)")
    action_group.add_option(                                # --ps
        "--ps", action="store_const", dest="action", const="ps",
        help="Write Postscript output. (not implemented yet)")
    action_group.add_option(                                # --pdf
        "--pdf", action="store_const", dest="action", const="pdf",
        help="Write PDF output. (not implemented yet)")
    action_group.add_option(                                # --check
        "--check", action="store_const", dest="action", const="check",
        help="Check completeness of docs. (not implemented yet)")

    # Options I haven't ported over yet are...
    # separate-classes (??) -- for latex only
    # command-line-order (??)
    # ignore-param-mismatch -- not implemented yet, but will be related
    #                          to DocInheriter
    # tests=...

    # Add options -- Options
    options_group.add_option(                                # --output
        "--output", "-o", dest="target", metavar="PATH",
        help="The output directory.  If PATH does not exist, then "
        "it will be created.")
    options_group.add_option(                                # --show-imports
        "--inheritance", dest="inheritance", metavar="STYLE",
        help="The format for showing inheritance objects.  STYLE "
        "should be \"grouped\", \"listed\", or \"inherited\".")
    options_group.add_option(                                # --output
        "--docformat", dest="docformat", metavar="NAME",
        help="The default markup language for docstrings.  Defaults "
        "to \"%default\".")
    options_group.add_option(                                # --css
        "--css", "-c", dest="css", metavar="STYLESHEET",
        help="The CSS stylesheet.  STYLESHEET can be either a "
        "builtin stylesheet or the name of a CSS file.")
    options_group.add_option(                                # --name
        "--name", dest="prj_name", metavar="NAME",
        help="The documented project's name (for the navigation bar).")
    options_group.add_option(                                # --url
        "--url", dest="prj_url", metavar="URL",
        help="The documented project's URL (for the navigation bar).")
    options_group.add_option(                                # --navlink
        "--navlink", dest="prj_link", metavar="HTML",
        help="HTML code for a navigation link to place in the "
        "navigation bar.")
    options_group.add_option(                                # --top
        "--top", dest="top_page", metavar="PAGE",
        help="The \"top\" page for the HTML documentation.  PAGE can "
        "be a URL, the name of a module or class, or one of the "
        "special names \"trees.html\", \"indices.html\", or \"help.html\"")
    # [XX] output encoding isnt' implemented yet!!
    options_group.add_option(                                # --top
        "--encoding", dest="encoding", metavar="NAME",
        help="The output encoding for generated HTML files.")
    options_group.add_option(
        "--help-file", dest="help_file", metavar="FILE",
        help="An alternate help file.  FILE should contain the body "
        "of an HTML file -- navigation bars will be added to it.")
    options_group.add_option(                                # --frames
        "--show-frames", action="store_true", dest="show_frames",
        help="Include frames in the output.")
    options_group.add_option(                                # --no-frames
        "--no-frames", action="store_false", dest="show_frames",
        help="Do not include frames in the output.")
    options_group.add_option(                                # --private
        "--show-private", action="store_true", dest="show_private",
        help="Include private variables in the output.")
    options_group.add_option(                                # --no-private
        "--no-private", action="store_false", dest="show_private",
        help="Do not include private variables in the output.")
    options_group.add_option(                                # --show-imports
        "--show-imports", action="store_true", dest="show_imports",
        help="List each module's imports.")
    options_group.add_option(                                # --show-imports
        "--no-imports", action="store_false", dest="show_imports",
        help="Do not list each module's imports.")
    options_group.add_option(                             # --quiet
        "--quiet", "-q", action="count", dest="quiet",
        help="Decrease the verbosity.")
    options_group.add_option(                             # --verbose
        "--verbose", "-v", action="count", dest="verbose",
        help="Increase the verbosity.")
    options_group.add_option(                             # --denug
        "--debug", action="store_true", dest="debug",
        help="Show full tracebacks for internal errors.")

    # Add the option groups.
    optparser.add_option_group(action_group)
    optparser.add_option_group(options_group)

    # Set the option parser's defaults.
    optparser.set_defaults(action="html", show_frames=True,
                           docformat='epytext', 
                           show_private=True, show_imports=False,
                           debug=False, inheritance="grouped",
                           verbose=1, quiet=0)

    # Parse the arguments.
    options, names = optparser.parse_args()
    
    # Check to make sure all options are valid.
    if len(names) == 0:
        optparser.error("No names specified.")
    if options.inheritance not in ('grouped', 'listed', 'included'):
        optparser.error("Bad inheritance style.  Valid options are "
                        "grouped, listed, and included.")

    # Calculate verbosity.
    options.verbosity = options.verbose - options.quiet

    # The target default depends on the action.
    if options.target is None:
        options.target = options.action
    
    # Return parsed args.
    return options, names

def cli(args):
    options, names = parse_arguments(args)

    # Build docs for the named values.
    docbuilder = DocBuilder()
    docindex = docbuilder.build_docs(*names)

    # Perform the specified action.
    if options.action == 'html':
        _sandbox(_html, docindex, options)
    else:
        print >>sys.stderr, '\nUnsupported action %s!' % options.action

_encountered_internal_error = 0
def _sandbox(func, *args, **kwargs):
    error = None
    try:
        func(*args, **kwargs)
    except Exception, e:
        if options.debug: raise
        if isinstance(e, (OSError, IOError)):
            print >>sys.stderr, '\nFile error:\n%s\n' % e
        else:
            print >>sys.stderr, '\nINTERNAL ERROR:\n%s\n' % e
            _encountered_internal_error = 1
    except:
        if options.debug: raise
        print >>sys.stderr, '\nINTERNAL ERROR\n'
        _encountered_internal_error = 1

def _html(docindex, options):
    html_writer = HTMLWriter(docindex, **options.__dict__)
    num_files = 20 # HMM!

    if options.verbosity > 0:
        print  >>sys.stderr, ('Writing HTML docs (%d files) to %r.' %
                              (num_files, options.target))
    progress = _Progress('Writing', options.verbosity, num_files, 1)
    html_writer.write(options.target, progress.report)
    

######################################################################
## Progress Bar
######################################################################

class _Progress:
    """

    The progress meter that is used by C{cli} to report its progress.
    It prints the status to C{stderrr}.  Depending on the verbosity,
    setting it will produce different outputs.

    To update the progress meter, call C{report} with the name of the
    object that is about to be processed.
    """
    def __init__(self, action, verbosity, total_items, html_file=0):
        """
        Create a new progress meter.

        @param action: A string indicating what action is performed on
            each objcet.  Examples are C{"writing"} and C{"building
            docs for"}.
        @param verbosity: The verbosity level.  This controls what the
            progress meter output looks like.
        @param total_items: The total number of items that will be
            processed with this progress meter.  This is used to let
            the user know how much progress epydoc has made.
        @param html_file: Whether to assume that arguments are html
            file names, and munge them appropriately.
        """
        self._action = action
        self._verbosity = verbosity
        self._total_items = total_items
        self._item_num = 1
        self._html_file = 0

    def report(self, argument):
        """
        Update the progress meter.
        @param argument: The object that is about to be processed.
        """
        if self._verbosity <= 0: return
        
        if self._verbosity==1:
            if self._item_num == 1 and self._total_items <= 70:
                sys.stderr.write('  [')
            if (self._item_num % 60) == 1 and self._total_items > 70:
                sys.stderr.write('  [%3d%%] ' %
                                 (100.0*self._item_num/self._total_items))
            sys.stderr.write('.')
            sys.stderr.softspace = 1
            if (self._item_num % 60) == 0 and self._total_items > 70:
                print >>sys.stderr
            if self._item_num == self._total_items:
                if self._total_items <= 70: sys.stderr.write(']')
                print >>sys.stderr
        elif self._verbosity>1:
            TRACE_FORMAT = (('  [%%%dd/%d]' % (len(`self._total_items`),
                                               self._total_items))+
                            ' %s %%s' % self._action)

            if self._html_file:
                (dir, file) = os.path.split(argument)
                (root, d) = os.path.split(dir)
                if d in ('public', 'private'):
                    argument = os.path.join(d, file)
                else:
                    fname = argument
            
            print >>sys.stderr, TRACE_FORMAT % (self._item_num, argument)
        self._item_num += 1
            
######################################################################
## Help Interface
######################################################################

def help(names, inspect=True, parse=True):
    """
    Given a name, find its docs.
    """
    def progress(s):
        print 'Writing %s...' % s
        
    builder = DocBuilder(inspect=inspect, parse=parse)
    docindex = builder.build_docs(*names)
    writer = HTMLWriter(docindex)
    writer.write('/home/edloper/public_html/epydoc', progress)
    
######################################################################
## Temporary CLI
######################################################################
if __name__ == '__main__':
    cli(sys.argv[1:])
#     parse = inspect = True
#     if '-parse' in sys.argv[1:]:
#         inspect = False
#         sys.argv.remove('-parse')
#     if '-inspect' in sys.argv[1:]:
#         parse = False
#         sys.argv.remove('-inspect')
        
#     if len(sys.argv) <= 1:
#         print 'usage: %s <name>' % sys.argv[0]
#     else:
#         help(sys.argv[1:], inspect, parse)
