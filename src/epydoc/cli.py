#!/usr/bin/env python
#
# objdoc: epydoc command-line interface
# Edward Loper
#
# Created [03/15/02 10:31 PM]
# $Id$
#

# Note: if you change this, check that you didn't break _usage. 
"""
Command-line interface for epydoc.

Usage::
    epydoc [-o DIR] [-n NAME] [-p] [-c SHEET] [-v] MODULE...
    epydoc --check [-p] [-v] MODULE...
    epydoc --help
    epydoc --version

    MODULE...
        List of filenames containing modules to process.  When
        documenting packages, the filename must include the package
        directory (i.e., you can't run epydoc within the package
        directory, using relative filenames).
        
    --help, --usage, -h, -?
        Display this usage message.

    --version, -V
        Print the version of epydoc.

    -o DIR, --output=DIR
        Output directory for HTML files
        
    -n NAME, --name=NAME
        Project name (for HTML header/footer)

    -u URL, --url=URL
        Project URL (for HTML header/footer)

    -f, --frames
        Generate a frame-based table of contents.

    -c=SHEET, --css=SHEET
        CSS stylesheet for HTML files.  If SHEET is a file, then the
        stylesheet is copied from that file; otherwise, SHEET is taken
        to be the name of a built-in stylesheet.  For a list of the
        built-in stylesheets, run "epydoc --help css".

    --private-css=SHEET
        CSS stylesheet for the HTML files containing private API
        documentation.  If SHEET is a file, then the stylesheet is
        copied from that file; otherwise, SHEET is taken to be the
        name of a built-in stylesheet.  For a list of the built-in
        stylesheets, run "epydoc --help css".

    --help-file=FILE
        A file containing the body of the help page for the HTML
        output.  If no file is specified, then a default help file is
        used.

    --show-imports
        Include a list of the classes and functions that each module
        imports on the module documentation pages.
        
    --check
        Perform completeness checks on the documentation

    -p
        Check private objects (those that start with _)

    -v, --verbose
        Produce verbose output

    -vv, -vvv, -vvvv
        Produce successively more verbose output

    -q, --quiet
        Supress output of epytext warnings and errors.
"""

import sys, os.path, re, getopt

PROFILE=0

##################################################
## Command-Line Interface
##################################################

def _usage(exit_code=-1):
    """
    Display a usage message.

    @param exit_code: An exit status that will be passed to
        C{sys.exit}.
    @type exit_code: C{int}
    @rtype: C{None}
    """
    NAME = os.path.split(sys.argv[0])[-1]
    if NAME == '(imported)': NAME = 'epydoc'
    print '\nUsage:'
    print __doc__.split('Usage::\n')[-1].replace('epydoc', NAME)
    sys.exit(exit_code)

def _help(arg):
    """
    Display a speficied help message, and exit.

    @param arg: The name of the help message to display.  Currently,
        only C{"css"} and C{"usage"} are recognized.
    @type arg: C{string}
    @rtype: C{None}
    """
    if arg == 'css':
        from epydoc.css import STYLESHEETS
        print '\nThe following built-in stylesheets are available:'
        names = STYLESHEETS.keys()
        names.sort()
        maxlen = max(*[len(name) for name in names])
        format = '    %'+`-maxlen-1`+'s %s'
        for name in names:
            print format % (name, STYLESHEETS[name][1])
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

def _error(message):
    """
    Display a specified error string, and exit.

    @param message: The error message to display
    @type message: C{string}
    @rtype: C{None}
    """
    print "%s error: %s" % (os.path.split(sys.argv[0])[-1], message)
    sys.exit(-1)

def _parse_args():
    """
    Process the command line arguments; return a dictionary containing
    the relevant info.

    @return: A dictionary mapping from configuration parameters to
        values.  If a parameter is specified on the command line, then
        that value is used; otherwise, a default value is used.
        Currently, the following configuration parameters are set:
        C{target}; C{modules}; C{verbosity}; C{prj_name}; C{check};
        C{check_private}; and C{check_all}.
    @rtype: C{None}
    """
    # Default values.
    options = {'target':'html', 'modules':[], 'verbosity':0,
               'prj_name':'', 'check':0, 'check_private':0,
               'show_imports':0, 'frames':0, 'private':1,
               'quiet':0}

    # Get the command-line arguments, using getopts.
    shortopts = 'c:fh:n:o:u:Vvpq?:'
    longopts = ('check frames help= usage= helpfile= help-file= '+
                'help_file= name= output= target= url= version verbose ' +
                'private-css= private_css= quiet show-imports '+
                'show_imports css= no_private no-private').split()
    try:
        (opts, modules) = getopt.getopt(sys.argv[1:], shortopts, longopts)
    except getopt.GetoptError, e:
        if e.opt in ('h', '?', 'help', 'usage'): _usage(0)
        print ('%s; run "%s -h" for usage' %
               (e,os.path.basename(sys.argv[0])))
        sys.exit(-1)

    # Parse the arguments.
    for (opt, val) in opts:
        if opt in ('--check',): options['check'] = 1
        elif opt in ('--css', '-c'): options['css'] = val
        elif opt in ('--frames', '-f'): options['frames'] = 1
        elif opt in ('--help', '-?', '--usage', '-h'): _help(val)
        elif opt in ('--helpfile', '--help-file', '--help_file'):
            options['help'] = val
        elif opt in ('--name', '-n'): options['prj_name']=val
        elif opt in ('--no-private', '--no_private'): options['private']=0
        elif opt in ('--output', '--target', '-o'): options['target']=val
        elif opt in ('-p',): options['check_private'] = 1
        elif opt in ('--private-css', '--private_css'):
            options['private_css'] = val
        elif opt in ('--quiet', '-q'): options['quiet'] -= 3
        elif opt in ('--show-imports', '--show_imports'):
            options['show_imports'] = 1
        elif opt in ('--url', '-u'): options['prj_url']=val
        elif opt in ('--verbose', '-v'): options['verbosity'] += 1
        elif opt in ('--version', '-V'): _version()
        else:
            _usage()

    # Make sure we got some modules.
    if len(modules) == 0:
        print ('no modules specified; run "%s -h" for usage' %
               os.path.basename(sys.argv[0]))
        sys.exit(-1)
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

    if verbosity > 0: print 'Importing %s modules.' % len(module_names)
    modules = []
    mnum = 1
    TRACE_FORMAT = ("  [%%%dd/%d] Importing %%s" %
                    (len(`len(module_names)`), len(module_names)))
    for name in module_names:
        if verbosity > 2:
            print TRACE_FORMAT % (mnum, name)
            sys.stdout.flush()
            mnum += 1

        # Import the module, and add it to the list.
        try:
            module = import_module(name)
            if module not in modules:
                modules.append(module)
            elif verbosity > 3:
                print '  (duplicate)'
        except ImportError, e:
            if verbosity >= 0: 
                print '  Warning: %s' % e

    if verbosity > 1 and len(modules) > 20: print "Done importing"
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
    
    if options['verbosity'] > 0:
        print 'Building API documentation for %d modules.' % len(modules)
    TRACE_FORMAT = ("  [%%%dd/%d] Building docs for %%s" %
                    (len(`len(modules)`), len(modules)))
    mnum = 1
    for module in modules:
        if options['verbosity'] > 1:
            print TRACE_FORMAT % (mnum, module.__name__)
            sys.stdout.flush()
            mnum += 1
        d.add(module)

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
    from epydoc.html import HTML_Doc

    # Create the documenter, and figure out how many files it will
    # generate.
    htmldoc = HTML_Doc(docmap, **options)
    numfiles = htmldoc.num_files()
        
    # Produce pretty trace output.
    def progress_callback(file, doc, verbosity=options['verbosity'],
                          numfiles=numfiles, filenum=[1]):
        if verbosity==2:
            if filenum[0] == 1 and numfiles <= 70: sys.stdout.write('  [')
            if (filenum[0] % 60) == 1 and numfiles > 70:
                sys.stdout.write('  [%3d%%] ' % (100.0*filenum[0]/numfiles))
            sys.stdout.write('.')
            if (filenum[0] % 60) == 0 and numfiles > 70: print
            if filenum[0] == numfiles:
                if numfiles > 70: print
                else: print ']'
        elif verbosity>2:
            TRACE_FORMAT = (('  [%%%dd/%d]' % (len(`numfiles`), numfiles)) +
                            ' Writing docs for %s %s')
            if doc and doc.uid().is_module():
                print TRACE_FORMAT % (filenum[0], 'module:', `doc.uid()`)
            elif doc and doc.uid().is_class():
                print TRACE_FORMAT % (filenum[0], 'class: ', `doc.uid()`)
            else:
                print TRACE_FORMAT % (filenum[0], 'file:  ',
                                      os.path.basename(file))
        if verbosity > 1: sys.stdout.flush()
        filenum[0] += 1
        
    # Write documentation.
    if options['verbosity'] > 0:
        print ('Writing API documentation (%d files) to %s.' %
               (numfiles, options['target']))
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
    if options['verbosity'] > 0: print 'Performing completeness checks'
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
    
