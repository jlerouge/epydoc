#!/usr/bin/env python
#
# objdoc: epydoc command-line interface
# Edward Loper
#
# Created [03/15/02 10:31 PM]
# $Id$
#

# Note: if you change this docstring, check that you didn't break
# _usage.
# Note: As it is, the usage message fits in an 80x24 window, but if it
# gets any bigger, it won't.
"""
Command-line interface for epydoc.

Usage::

 epydoc [OPTIONS] MODULES...
 
     MODULES...                The Python modules to document.
     --html                    Generate HTML output (default).
     --latex                   Generate LaTeX output.
     --pdf                     Generate pdf output, via LaTeX.
     --check                   Run documentation completeness checks.
     -o DIR, --output DIR      The output directory.
     -n NAME, --name NAME      The documented project's name.
     -u URL, --url URL         The documented project's url.
     -t PAGE, --top PAGE       The top page for the HTML documentation.
     -c SHEET, --css SHEET     CSS stylesheet for HTML files.
     --private-css SHEET       CSS stylesheet for private objects.
     -V, --version             Print the version of epydoc.
     -h, -?, --help, --usage   Display this usage message.
     -h TOPIC, --help TOPIC    Display information about TOPIC
                               (css, usage, docformat, or version).

 See the epytext(1) man page for a complete list of options.

@var PROFILE: Whether or not to run the profiler.

@var _encountered_internal_error: A global variable recording whether
any internal errors have been detected.  If this variable is set to
true, then L{cli} will issue a warning once it completes running.
"""
__docformat__ = 'epytext en'


##################################################
## Constants
##################################################

# Use "%(tex)s" to include the latex filename, "%(ps)s" for the
# postscript filename, etc.  (You must include the "s" after the close
# parenthasis).
LATEX_COMMAND = r"echo x | latex '\batchmode\input %(tex)s'"
MAKEINDEX_COMMAND = 'makeindex -q %(idx)s'
DVIPS_COMMAND = 'dvips -q %(dvi)s -o %(ps)s -G0 -Ppdf'
PS2PDF_COMMAND = ('ps2pdf -sPAPERSIZE=letter -dMaxSubsetPct=100 '+
                  '-dSubsetFonts=true -dCompatibilityLevel=1.2 '+
                  '-dEmbedAllFonts=true %(ps)s %(pdf)s')

## This is a more verbose version of LATEX_COMMAND.
#LATEX_COMMAND = r"echo x | latex %(tex)s"

PROFILE=0
##################################################
## Command-Line Interface
##################################################
import sys, os.path, re, getopt

def cli():
    """
    Command line interface for epydoc.
    
    @rtype: C{None}
    """
    # Parse the command line arguments.
    options = _parse_args()

    # Import all the specified modules.
    modules = _import(options['modules'], options['verbosity'])

    # Build their documentation
    docmap = _make_docmap(modules, options)

    # Perform the requested action.
    if options['action'] == 'html': _html(docmap, options)
    elif options['action'] == 'check': _check(docmap, options)
    elif options['action'] == 'latex': _latex(docmap, options, 'latex')
    elif options['action'] == 'dvi': _latex(docmap, options, 'dvi')
    elif options['action'] == 'ps': _latex(docmap, options, 'ps')
    elif options['action'] == 'pdf': _latex(docmap, options, 'pdf')
    else: raise ValueError('Unknown action %r' % options['action'])

    # Report any internal errors.
    if _encountered_internal_error:
        estr = ("An internal error occured.  To see the exception "+
                "that caused the\n error, use the '--debug' option.")
        print >>sys.stderr, '\n'+'!'*70
        print >>sys.stderr, estr
        print >>sys.stderr, '\n'+'!'*70

_encountered_internal_error = 0
def _internal_error(e=None):
    """
    Print a warning message about an internal error.
    @return: The return value from calling C{func}
    """
    if isinstance(e, KeyboardInterrupt): raise
    _encountered_internal_error = 1
    if sys.stderr.softspace: print >>sys.stderr
    if e: print >>sys.stderr, "INTERNAL ERROR: %s" % e
    else: print >>sys.stderr, "INTERNAL ERROR"
        
def _usage(exit_code=1):
    """
    Display a usage message.

    @param exit_code: An exit status that will be passed to
        C{sys.exit}.
    @type exit_code: C{int}
    @rtype: C{None}
    """
    if exit_code == 0: stream = sys.stdout
    else: stream = sys.stderr
    NAME = os.path.split(sys.argv[0])[-1]
    if NAME == '(imported)': NAME = 'epydoc'
    usage = __doc__.split('Usage::\n')[-1].replace('epydoc', NAME)
    usage = re.sub(r'\n\s*@[\s\S]*', '', usage)
    usage = re.sub(r'\n ', '\n', usage)
    print >>stream, '\nUsage:', usage.strip()+'\n'
    sys.exit(exit_code)

def _help(arg):
    """
    Display a speficied help message, and exit.

    @param arg: The name of the help message to display.  Currently,
        only C{"css"} and C{"usage"} are recognized.
    @type arg: C{string}
    @rtype: C{None}
    """
    arg = arg.strip().lower()
    if arg == 'css':
        from epydoc.css import STYLESHEETS
        print '\nThe following built-in CSS stylesheets are available:'
        names = STYLESHEETS.keys()
        names.sort()
        maxlen = max(*[len(name) for name in names])
        format = '    %'+`-maxlen-1`+'s %s'
        for name in names:
            print format % (name, STYLESHEETS[name][1])
        print
        sys.exit(0)
    elif arg == 'version':
        _version()
    elif arg in ('docformat', 'doc_format', 'doc-format'):
        print '\n__docformat__ is a module variable that specifies the markup'
        print 'language for the docstrings in a module.  Its value is a '
        print 'string, consisting the name of a markup language, optionally '
        print 'followed by a language code (such as "en" for English).  Epydoc'
        print 'currently recognizes the following markup language names:'
        print '  - epytext'
        print '  - plaintext'
        print
        sys.exit(0)
    else:
        _usage(0)
    
def _version():
    """
    Display the version information, and exit.
    
    @rtype: C{None}
    """
    import epydoc
    print "Epydoc version %s" % epydoc.__version__
    sys.exit(0)

def _parse_args():
    """
    Process the command line arguments; return a dictionary containing
    the relevant info.

    @return: A dictionary mapping from configuration parameters to
        values.  If a parameter is specified on the command line, then
        that value is used; otherwise, a default value is used.
        Currently, the following configuration parameters are set:
        C{target}, C{modules}, C{verbosity}, C{prj_name}, C{output},
        C{check_private}, C{show_imports}, C{frames}, C{private},
        C{debug}, C{top}, C{list_classes_separately}, and C{docformat}.
    @rtype: C{None}
    """
    # Default values.
    options = {'target':None, 'modules':[], 'verbosity':1,
               'prj_name':'', 'action':'html', 'check_private':0,
               'show_imports':0, 'frames':1, 'private':1,
               'list_classes_separately': 0, 'debug':0,
               'docformat':None, 'top':None}

    # Get the command-line arguments, using getopts.
    shortopts = 'c:fh:n:o:t:u:Vvpq?:'
    longopts = ('check frames help= usage= helpfile= help-file= '+
                'help_file= output= target= url= version verbose ' +
                'private-css= private_css= quiet show-imports '+
                'show_imports css= no_private no-private name= '+
                'builtins no-frames no_frames noframes debug '+
                'docformat= doc-format= doc_format= top=  navlink= '+
                'nav_link= nav-link= latex html dvi ps pdf '+
                'separate-classes separate_classes').split()
    try:
        (opts, modules) = getopt.getopt(sys.argv[1:], shortopts, longopts)
    except getopt.GetoptError, e:
        if e.opt in ('h', '?', 'help', 'usage'): _usage(0)
        print >>sys.stderr, ('%s; run "%s -h" for usage' %
                              (e,os.path.basename(sys.argv[0])))
        sys.exit(1)

    # Parse the arguments.
    for (opt, val) in opts:
        if opt in ('--check',): options['action'] = 'check'
        elif opt in ('--css', '-c'): options['css'] = val
        elif opt in ('--debug',): options['debug']=1
        elif opt in ('--dvi',): options['action'] = 'dvi'
        elif opt in ('--docformat', '--doc-format', '--doc_format'):
            from epydoc.objdoc import set_default_docformat
            set_default_docformat(val)
        elif opt in ('--frames', '-f'):
            print ('Warning: the "--frames" argument is depreciated; '+
                   'frames are now\n         generated by default.')
        elif opt in ('--no-frames', '--no_frames', '--noframes'):
            options['frames'] = 0
        elif opt in ('--help', '-?', '--usage', '-h'): _help(val)
        elif opt in ('--helpfile', '--help-file', '--help_file'):
            options['help'] = val
        elif opt in ('--html',): options['action'] = 'html'
        elif opt in ('--latex',): options['action']='latex'
        elif opt in ('--name', '-n'): options['prj_name']=val
        elif opt in ('--navlink', '--nav-link', '--nav_link'):
            options['prj_link'] = val
        elif opt in ('--no-private', '--no_private'): options['private']=0
        elif opt in ('--output', '--target', '-o'): options['target']=val
        elif opt in ('-p',): options['check_private'] = 1
        elif opt in ('--pdf',): options['action'] = 'pdf'
        elif opt in ('--private-css', '--private_css'):
            options['private_css'] = val
        elif opt in ('--ps',): options['action'] = 'ps'
        elif opt in ('--quiet', '-q'): options['verbosity'] -= 1
        elif opt in ('--separate-classes', '--separate_classes'):
            options['list_classes_separately'] = 1
        elif opt in ('--show-imports', '--show_imports'):
            options['show_imports'] = 1
        elif opt in ('-t', '--top'): options['top'] = val
        elif opt in ('--url', '-u'): options['prj_url']=val
        elif opt in ('--verbose', '-v'): options['verbosity'] += 1
        elif opt in ('--version', '-V'): _version()
        elif opt in ('--builtins',):
            modules += sys.builtin_module_names
            modules.remove('__main__')
        else:
            _usage()

    # Pick a default target directory, if none was specified.
    if options['target'] is None:
        if options['action'] == 'html':
            options['target'] = 'html'
        elif options['action'] in ('latex', 'dvi', 'ps', 'pdf'):
            options['target'] = 'latex'

    # Check that the options all preceed the filenames.
    for m in modules:
        if m == '-': break
        elif m[0:1] == '-':
            estr = 'options must preceed modules'
            print >>sys.stderr, ('%s; run "%s -h" for usage' %
                                 (estr,os.path.basename(sys.argv[0])))
            sys.exit(1)
        
    # Make sure we got some modules.
    modules = [m for m in modules if m != '-']
    if len(modules) == 0:
        print >>sys.stderr, ('no modules specified; run "%s -h" for usage' %
                             os.path.basename(sys.argv[0]))
        sys.exit(1)
    options['modules'] = modules

    return options

def _import(module_names, verbosity):
    """
    @return: A list of the modules contained in the given files.
        Duplicates are removed.
    @rtype: C{list} of C{module}
    @param module_names: The list of module filenames.
    @type module_names: C{list} of C{string}
    @param verbosity: Verbosity level for tracing output.
    @type verbosity: C{int}
    """
    from epydoc.imports import import_module, find_modules

    # First, expand packages.
    for name in module_names[:]:
        if os.path.isdir(name):
            module_names.remove(name)
            new_modules = find_modules(name)
            if new_modules: module_names += new_modules
            elif verbosity >= 0:
                if sys.stderr.softspace: print >>sys.stderr
                print  >>sys.stderr, 'Error: %r is not a pacakge' % name

    if verbosity > 0:
        print >>sys.stderr, 'Importing %s modules.' % len(module_names)
    modules = []
    progress = _Progress('Importing', verbosity, len(module_names))
    
    for name in module_names:
        progress.report(name)
        # Import the module, and add it to the list.
        try:
            module = import_module(name)
            if module not in modules: modules.append(module)
            elif verbosity > 2:
                if sys.stderr.softspace: print >>sys.stderr
                print >>sys.stderr, '    (duplicate)'
        except ImportError, e:
            if verbosity >= 0:
                if sys.stderr.softspace: print >>sys.stderr
                print  >>sys.stderr, e

    if len(modules) == 0:
        print >>sys.stderr, '\nError: no modules successfully loaded!'
        sys.exit(1)
    return modules

def _make_docmap(modules, options):
    """
    Construct the documentation map for the given modules.

    @param modules: The modules that should be documented.
    @type modules: C{list} of C{Module}
    @param options: Options from the command-line arguments.
    @type options: C{dict}
    """
    from epydoc.objdoc import DocMap

    verbosity = options['verbosity']
    document_bases = (options['action'] != 'check')
    d = DocMap(verbosity, document_bases)
    if options['verbosity'] > 0:
        print  >>sys.stderr, ('Building API documentation for %d modules.'
                              % len(modules))
    progress = _Progress('Building docs for', verbosity, len(modules))
    
    for module in modules:
        progress.report(module.__name__)
        # Add the module.  Catch any exceptions that get generated.
        try: d.add(module)
        except Exception, e:
            if options['debug']: raise
            else: _internal_error(e)
        except:   
            if options['debug']: raise
            else: _internal_error()
                
    return d

def _run(cmd, options):
    from epydoc.epytext import wordwrap
    if '|' in cmd: name = cmd.split('|')[1].strip().split(' ', 1)[0]
    else: name = cmd.strip().split(' ', 1)[0]
    if options['verbosity'] == 1:
        print >>sys.stderr, 'Running %s...' % name
    elif options['verbosity'] > 1:
        cmd_str = wordwrap(`cmd`, 10+len(name)).lstrip()
        print >>sys.stderr, 'Running %s' % cmd_str.rstrip()

    exitcode = os.system(cmd)
    if exitcode != 0:
        raise OSError('%s failed: %s' % (name, exitcode))

def _latex(docmap, options, format):
    """
    Create the LaTeX documentation for the objects in the given
    documentation map.  

    @param docmap: A documentation map containing the documentation
        for the objects whose API documentation should be created.
    @param options: Options from the command-line arguments.
    @type options: C{dict}
    @param format: One of C{'latex'}, C{'dvi'}, C{'ps'}, or C{'pdf'}.
    """
    from epydoc.latex import LatexFormatter

    # Create the documenter, and figure out how many files it will
    # generate.
    latex_doc = LatexFormatter(docmap, **options)
    num_files = latex_doc.num_files()
        
    # Write documentation.
    if options['verbosity'] > 0:
        print  >>sys.stderr, ('Writing LaTeX docs (%d files) to %r.' %
                              (num_files, options['target']))
    progress = _Progress('Writing', options['verbosity'], num_files)
    latex_doc.write(options['target'], progress.report)

    # Run latex, makeindex, dvi, ps, and pdf, as appropriate.
    oldpath = os.path.abspath(os.curdir)
    try:
        try:
            # Filenames (used by the external commands)
            filenames = {'tex': 'api.tex', 'idx': 'api.idx',
                         'dvi': 'api.dvi', 'ps': 'api.ps',
                         'pdf': 'api.pdf'}
        
            # latex -> dvi
            if format in ('dvi', 'ps', 'pdf'):
                # Go into the output directory.
                os.chdir(options['target'])
                
                _run(LATEX_COMMAND % filenames, options)
                _run(MAKEINDEX_COMMAND % filenames, options)
                _run(LATEX_COMMAND % filenames, options)
                _run(LATEX_COMMAND % filenames, options)
                
            # dvi -> postscript
            if format in ('ps', 'pdf'):
                _run(DVIPS_COMMAND % filenames, options)

            # postscript -> pdf
            if format in ('pdf',): 
                _run(PS2PDF_COMMAND % filenames, options)

        except OSError, e:
            print  >>sys.stderr, 'Error: %s' % e
            sys.exit(1)
    finally:
        os.chdir(oldpath)

def _html(docmap, options):
    """
    Create the HTML documentation for the objects in the given
    documentation map.  

    @param docmap: A documentation map containing the documentation
        for the objects whose API documentation should be created.
    @param options: Options from the command-line arguments.
    @type options: C{dict}
    """
    from epydoc.html import HTMLFormatter

    # Create the documenter, and figure out how many files it will
    # generate.
    html_doc = HTMLFormatter(docmap, **options)
    num_files = html_doc.num_files()

    # Write documentation.
    if options['verbosity'] > 0:
        print  >>sys.stderr, ('Writing HTML docs (%d files) to %r.' %
                              (num_files, options['target']))
    progress = _Progress('Writing', options['verbosity'], num_files, 1)
    html_doc.write(options['target'], progress.report)

def _check(docmap, options):
    """
    Run completeness checks on the objects in the given documentation
    map. 

    @param docmap: A documentation map containing the documentation
        for the objects whose API documentation should be created.
    @param options: Options from the command-line arguments.
    @type options: C{dict}
    """
    from epydoc.checker import DocChecker
    
    # Run completeness checks.
    if options['verbosity'] > 0:
        print  >>sys.stderr, 'Performing completeness checks'
    checker = DocChecker(docmap)
    if options['check_private']:
        checker.check(DocChecker.ALL_T | DocChecker.PUBLIC | 
                      DocChecker.PRIVATE | DocChecker.DESCR_LAZY | 
                      DocChecker.TYPE)
    else:
        checker.check(DocChecker.ALL_T | DocChecker.PUBLIC | 
                      DocChecker.DESCR_LAZY | DocChecker.TYPE)
           
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
        
if __name__ == '__main__':
    if PROFILE:
        from profile import Profile
        profiler = Profile()
        profiler.runcall(cli)
        profiler.print_stats()
    else:
        cli()
