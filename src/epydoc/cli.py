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

    -o DIR, --output DIR, --target DIR
        Output directory for HTML files
        
    -n NAME, --name NAME
        Project name (for HTML header/footer)

    -u URL, --url URL
        Project URL (for HTML header/footer)

    -c SHEET, --css SHEET
        CSS stylesheet for HTML files.  If SHEET is a file, then the
        stylesheet is copied from that file; otherwise, SHEET is taken
        to be the name of a built-in stylesheet.  For a list of the
        built-in stylesheets, run "epydoc --help css".

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

import sys, os.path, re
from epydoc.imports import import_module

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
    elif arg == 'usage':
        _usage(0)
    else:
        _usage()
    print
    sys.exit(0)
    
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
    print "%s Error: %s" % (os.path.split(sys.argv[0])[-1], message)
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
        C{show_private}; and C{check_all}.
    @rtype: C{None}
    """
    # Default values.
    argvals = {'target':'html', 'modules':[], 'verbosity':0,
               'prj_name':'', 'check':0, 'show_private':0,
               'check_all':0, 'show_imports':0}
    
    # Get the args (backwards, since we will pop them)
    args = sys.argv[1:]
    args.reverse()

    while args:
        arg = args.pop()
        if arg[:1] == '-':
            if arg in ('-o', '--output', '--target'):
                try: argvals['target'] = args.pop()
                except: _usage()
            elif arg in ('-n', '--name'):
                try: argvals['prj_name'] = args.pop()
                except: _usage()
            elif arg in ('-u', '--url'):
                try: argvals['prj_url'] = args.pop()
                except: _usage()
            elif arg in ('-V', '--version'):
                _version()
            elif arg in ('-v', '--verbose'):
                argvals['verbosity'] += 1
            elif arg in ('-q', '--quiet'):
                argvals['verbosity'] -= 3
            elif re.match('^-v+$', arg):
                argvals['verbosity'] += len(arg)-1
            elif arg in ('--help', '-?', '--usage', '-h'):
                if len(args) == 1: _help(args.pop())
                elif len(args) == 0: _usage(0)
                else: _usage()
            elif arg in ('--check',):
                argvals['check'] = 1
            elif arg in ('--show-imports', '--show_imports'):
                argvals['show_imports'] = 1
            elif arg in ('-p',):
                argvals['show_private'] = 1
            elif arg in ('-a', '-check_all'):
                argvals['check_all'] = 1
            elif arg in ('--css', '-c'):
                try: argvals['css'] = args.pop()
                except: _usage()
                if argvals['css'] == 'help': _csshelp()
            else:
                _usage()
        else:
            argvals['modules'].append(arg)

    # This can prevent trouble sometimes when importing things.
    sys.argv[:] = ['(imported)']

    if argvals['modules'] == []: _usage()
    return argvals

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
    if verbosity > 0: print 'Importing %s modules...' % len(module_names)
    modules = []
    mnum = 0
    for name in module_names:
        if verbosity > 1:
            print ('[%d/%d] Importing %s' % (mnum+1, len(module_names), name))
            sys.stdout.flush()
            mnum += 1

        # Import the module, and add it to the list.
        try:
            module = import_module(name)
            if module not in modules:
                modules.append(module)
            elif verbosity > 3: print "  (duplicate)"
        except ImportError, e:
            if verbosity >= 0: print 'Warning: %s' % e

    if verbosity > 1 and len(modules) > 20: print "Done importing"
    return modules

def cli():
    """
    Command line interface for epydoc.
    
    @rtype: C{None}
    """
    param = _parse_args()

    # This can occasionally help when importing various modules.
    sys.stdin.close()

    try:
        modules = _find_modules(param['modules'], param['verbosity'])
    except ImportError, e:
        if e.args: _error(e.args[0])
        else: raise

    # Wait to do imports until now, to make "--help" faster.
    from epydoc.html import HTML_Doc
    from epydoc.objdoc import DocMap
    from epydoc.checker import DocChecker

    # Create dest directory, if necessary
    if not os.path.isdir(param['target']):
        if not os.path.exists(param['target']):
            try: os.mkdir(param['target'])
            except: _error("Could not create %r" % param['target'])
        else:
            _error("%r is not a directory" % param['target'])

    def progress_callback(file, doc, verbosity=param['verbosity']):
        if verbosity==2:
            sys.stdout.write('.')
            sys.stdout.flush()
        elif verbosity>2:
            if doc and doc.uid().is_module():
                print 'Writing docs for module:', `doc.uid()`
            elif doc and doc.uid().is_class():
                print 'Writing docs for class: ', `doc.uid()`
            else:
                print 'Writing docs for file:  ', file
        
    # Construct the docmap.  Don't bother documenting base classes if
    # we're just running checks.
    d = DocMap(param['verbosity'], not param['check'])
    
    # Build the documentation.
    for module in modules:
        if param['verbosity'] > 0: print 'Building docs for', module.__name__
        d.add(module)

    if param['check']:
        # Run completeness checks.
        if param['verbosity'] > 0: print 'Performing completeness checks'
        checker = DocChecker(d)
        if param['show_private']:
            checker.check(DocChecker.ALL_T | DocChecker.PUBLIC | 
                          DocChecker.PRIVATE | DocChecker.DESCR_LAZY | 
                          DocChecker.TYPE)
        else:
            checker.check(DocChecker.ALL_T | DocChecker.PUBLIC | 
                          DocChecker.DESCR_LAZY | DocChecker.TYPE)
    else:
        # Write documentation.
        if param['verbosity'] == 2: print 'Writing docs to', param['target'],
        elif param['verbosity'] > 0: print 'Writing docs to', param['target']

        htmldoc = HTML_Doc(d, **param)
        htmldoc.write(param['target'], progress_callback)
        if param['verbosity'] > 1: print
    
if __name__ == '__main__':
    cli()
    
