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
    -o DIR, --output DIR      The output directory for HTML files.
    -n NAME, --name NAME      The documented project's name.
    -u URL, --url URL         The documented project's url.
    -c SHEET, --css SHEET     CSS stylesheet for HTML files.
    -t PAGE, --toppage PAGE   The top page for the documentation.
    --navlink LINK            HTML code for the navbar's homepage link.
    --private-css SHEET       CSS stylesheet for private objects.
    --help-file FILE          HTML body for the help page.
    --no-frames               Do not create frames-based table of contents.
    --no-private              Do not document private objects.
    --show-imports            Include lists of importes.
    --docformat=FORMAT        Set the default value for __docformat__.
    --builtins                Add all builtin modules to MODULES.
    -v, --verbose             Display a progress bar.
    -vv, -vvv, -vvvv          Produce sucessively more verbose output.
    -q, --quiet               Supress epytext warnings and errors.
    --check                   Run documentation completeness checks.
    -p                        Run checks on private objects.
    -V, --version             Print the version of epydoc.
    -h, -?, --help, --usage   Display this usage message.
    -h TOPIC, --help TOPIC    Display information about TOPIC
                              (css, usage, docformat, or version).

@var PROFILE: Whether or not to run the profiler.

@var _encountered_internal_error: A global variable recording whether
any internal errors have been detected.  If this variable is set to
true, then L{cli} will issue a warning once it completes running.
"""
__docformat__ = 'epytext en'

import sys, os.path, re, getopt

PROFILE=0

##################################################
## Command-Line Interface
##################################################

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
    print >>stream, 'Usage:', usage.strip()
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
        C{target}, C{modules}, C{verbosity}, C{prj_name}, C{check},
        C{check_private}, C{show_imports}, C{frames}, C{private},
        C{quiet}, C{debug}, C{toppage}, and C{docformat}.
    @rtype: C{None}
    """
    # Default values.
    options = {'target':'html', 'modules':[], 'verbosity':0,
               'prj_name':'', 'check':0, 'check_private':0,
               'show_imports':0, 'frames':1, 'private':1,
               'quiet':0, 'debug':0, 'docformat':None,
               'toppage':None}

    # Get the command-line arguments, using getopts.
    shortopts = 'c:fh:n:o:t:u:Vvpq?:'
    longopts = ('check frames help= usage= helpfile= help-file= '+
                'help_file= output= target= url= version verbose ' +
                'private-css= private_css= quiet show-imports '+
                'show_imports css= no_private no-private name= '+
                'builtins no-frames no_frames debug docformat= '+
                'doc-format= doc_format= toppage= top_page= '+
                'top-page= navlink= nav_link= nav-link=').split()
    try:
        (opts, modules) = getopt.getopt(sys.argv[1:], shortopts, longopts)
    except getopt.GetoptError, e:
        if e.opt in ('h', '?', 'help', 'usage'): _usage(0)
        print >>sys.stderr, ('%s; run "%s -h" for usage' %
                              (e,os.path.basename(sys.argv[0])))
        sys.exit(1)

    # Parse the arguments.
    for (opt, val) in opts:
        if opt in ('--check',): options['check'] = 1
        elif opt in ('--css', '-c'): options['css'] = val
        elif opt in ('--debug',): options['debug']=1
        elif opt in ('--docformat', '--doc-format', '--doc_format'):
            from epydoc.objdoc import set_default_docformat
            set_default_docformat(val)
        elif opt in ('--frames', '-f'):
            print ('Warning: the "--frames" argument is depreciated; '+
                   'frames are now\n         generated by default.')
        elif opt in ('--no-frames', '--no_frames'): options['frames'] = 0
        elif opt in ('--help', '-?', '--usage', '-h'): _help(val)
        elif opt in ('--helpfile', '--help-file', '--help_file'):
            options['help'] = val
        elif opt in ('--name', '-n'): options['prj_name']=val
        elif opt in ('--navlink', '--nav-link', '--nav_link'):
            options['prj_link'] = val
        elif opt in ('--no-private', '--no_private'): options['private']=0
        elif opt in ('--output', '--target', '-o'): options['target']=val
        elif opt in ('-p',): options['check_private'] = 1
        elif opt in ('--private-css', '--private_css'):
            options['private_css'] = val
        elif opt in ('--quiet', '-q'): options['quiet'] -= 3
        elif opt in ('--show-imports', '--show_imports'):
            options['show_imports'] = 1
        elif opt in ('-t', '--toppage', '--top-page', '--top_page'):
            options['toppage'] = val
        elif opt in ('--url', '-u'): options['prj_url']=val
        elif opt in ('--verbose', '-v'): options['verbosity'] += 1
        elif opt in ('--version', '-V'): _version()
        elif opt in ('--builtins',):
            modules += sys.builtin_module_names
            modules.remove('__main__')
        else:
            _usage()

    # Make sure we got some modules.
    if len(modules) == 0:
        print >>sys.stderr, ('no modules specified; run "%s -h" for usage' %
                             os.path.basename(sys.argv[0]))
        sys.exit(1)
    options['modules'] = modules

    return options

def _find_modules(module_names, verbosity):
    """
    @return: A list of the modules contained in the given files.
        Duplicates are removed.
    @rtype: C{list} of C{module}
    @param module_names: The list of module filenames.
    @type module_names: C{list} of C{string}
    @param verbosity: Verbosity level for tracing output.
    @type verbosity: C{int}
    """
    from epydoc.imports import import_module

    if verbosity > 0:
        print >>sys.stderr, 'Importing %s modules.' % len(module_names)
    modules = []
    module_num = 1
    num_modules = len(module_names)
    TRACE_FORMAT = ("  [%%%dd/%d] Importing %%s" %
                    (len(`num_modules`), num_modules))
    for name in module_names:
        if verbosity == 1:
            if module_num == 1 and num_modules <= 70: sys.stderr.write('  [')
            if (module_num % 60) == 1 and num_modules > 70:
                sys.stderr.write('  [%3d%%] ' % (100.0*module_num/num_modules))
            sys.stderr.write('.')
            sys.stderr.softspace = 1
            if (module_num % 60) == 0 and num_modules > 70: print >>sys.stderr
            if module_num == num_modules:
                if num_modules <= 70: sys.stderr.write(']')
                print >>sys.stderr
        elif verbosity > 1:
            print  >>sys.stderr, TRACE_FORMAT % (module_num, name)
        module_num += 1

        # Import the module, and add it to the list.
        try:
            module = import_module(name)
            if module not in modules:
                modules.append(module)
            elif verbosity > 2:
                print  >>sys.stderr, '  (duplicate)'
        except ImportError, e:
            if verbosity >= 0: 
                print  >>sys.stderr, '\n  Warning: %s' % e

    return modules

def cli():
    """
    Command line interface for epydoc.
    
    @rtype: C{None}
    """
    # Parse the command line arguments.
    options = _parse_args()

    # Import all the specified modules.
    modules = _find_modules(options['modules'], options['verbosity'])

    # Build their documentation
    docmap = _make_docmap(modules, options)

    # Perform the requested action.
    if options['check']: _check(docmap, options)
    else: _html(docmap, options)

    # Report any internal errors.
    if _encountered_internal_error:
        estr = ("An internal error occured.  To see the exception "+
                "that caused the\n error, use the '--debug' option.")
        print >>sys.stderr, '\n'+'!'*70
        print >>sys.stderr, estr
        print >>sys.stderr, '\n'+'!'*70

def _make_docmap(modules, options):
    """
    Construct the documentation map for the given modules.

    @param modules: The modules that should be documented.
    @type modules: C{list} of C{Module}
    @param options: Options from the command-line arguments.
    @type options: C{dict}
    """
    from epydoc.objdoc import DocMap

    # Don't bother documenting base classes if we're just running
    # checks.
    d = DocMap(options['quiet'], not options['check'])
    
    num_modules = len(modules)
    if options['verbosity'] > 0:
        print  >>sys.stderr, ('Building API documentation for %d modules.'
                              % num_modules)
    TRACE_FORMAT = ("  [%%%dd/%d] Building docs for %%s" %
                    (len(`num_modules`), num_modules))
    module_num = 1
    for module in modules:
        if options['verbosity'] == 1:
            if module_num == 1 and num_modules <= 70: sys.stderr.write('  [')
            if (module_num % 60) == 1 and num_modules > 70:
                sys.stderr.write('  [%3d%%] ' % (100.0*module_num/num_modules))
            sys.stderr.write('.')
            sys.stderr.softspace = 1
            if (module_num % 60) == 0 and num_modules > 70: print >>sys.stderr
            if module_num == num_modules:
                if num_modules <= 70: sys.stderr.write(']')
                print >>sys.stderr
        elif options['verbosity'] > 1:
            print >>sys.stderr, TRACE_FORMAT % (module_num, module.__name__)
        module_num += 1

        # Add the module.  Catch any exceptions that get generated.
        try: d.add(module)
        except Exception, e:
            if options['debug']: raise
            else: _internal_error(e)
        except:   
            if options['debug']: raise
            else: _internal_error()
                
    return d

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
    htmldoc = HTMLFormatter(docmap, **options)
    num_files = htmldoc.num_files()
        
    # Produce pretty trace output.
    def progress_callback(path, doc, verbosity=options['verbosity'],
                          num_files=num_files, file_num=[1]):
        if verbosity==1:
            if file_num[0] == 1 and num_files <= 70: sys.stderr.write('  [')
            if (file_num[0] % 60) == 1 and num_files > 70:
                sys.stderr.write('  [%3d%%] ' % (100.0*file_num[0]/num_files))
            sys.stderr.write('.')
            sys.stderr.softspace = 1
            if (file_num[0] % 60) == 0 and num_files > 70: print >>sys.stderr
            if file_num[0] == num_files:
                if num_files <= 70: sys.stderr.write(']')
                print >>sys.stderr
        elif verbosity>1:
            TRACE_FORMAT = (('  [%%%dd/%d]' % (len(`num_files`), num_files)) +
                            ' Writing %s')
            (dir, file) = os.path.split(path)
            (root, d) = os.path.split(dir)
            if d in ('public', 'private'): fname = os.path.join(d, file)
            else: fname = file
            print >>sys.stderr, TRACE_FORMAT % (file_num[0], fname)
        file_num[0] += 1
        
    # Write documentation.
    if options['verbosity'] > 0:
        print  >>sys.stderr, ('Writing API documentation (%d files) to %s.' %
                              (num_files, options['target']))
    htmldoc.write(options['target'], progress_callback)

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
    
if __name__ == '__main__':
    if PROFILE:
        from profile import Profile
        profiler = Profile()
        profiler.runcall(cli)
        profiler.print_stats()
    else:
        cli()
    
