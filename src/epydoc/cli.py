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
    epydoc [-o DIR] [-n NAME] [-p] [--css SHEET] [-v] MODULE...
    epydoc --check [-p] [-a] [-v] MODULE...
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
        Print the version of Epydoc.

    -o DIR, --output DIR, --target DIR
        Output directory for HTML files
        
    -n NAME, --name NAME
        Package name (for HTML header/footer)

    -u URL, --url URL
        Package URL (for HTML header/footer)

    --css SHEET
        CSS stylesheet for HTML files.  If SHEET is a file, then the
        stylesheet is copied from that file; otherwise, SHEET is taken
        to be the name of a built-in stylesheet.  For a list of the
        built-in stylesheets, run "epydoc --help css".
        
    --check
        Perform completeness checks on the documentation

    -p
        Check private objects (those that start with _)

    -a
        Run all checks.

    -v, --verbose
        Produce verbose output

    -vv, -vvv, -vvvv
        Produce successively more verbose output
"""

import sys, os.path, re

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
        C{target}; C{modules}; C{verbosity}; C{pkg_name}; C{check};
        C{show_private}; and C{check_all}.
    @rtype: C{None}
    """
    # Default values.
    argvals = {'target':'html', 'modules':[], 'verbosity':0,
               'pkg_name':'', 'check':0, 'show_private':0,
               'check_all':0}
    
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
                try: argvals['pkg_name'] = args.pop()
                except: _usage()
            elif arg in ('-u', '--url'):
                try: argvals['pkg_url'] = args.pop()
                except: _usage()
            elif arg in ('-V', '--version'):
                _version()
            elif arg in ('-v', '--verbose'):
                argvals['verbosity'] += 1
            elif arg in ('-vv', '-vvv', '-vvvv'):
                argvals['verbosity'] += len(arg)-1
            elif arg in ('--help', '-?', '--usage', '-h'):
                if len(args) == 1: _help(args[0])
                elif len(args) == 0: _usage(0)
                else: _usage()
            elif arg in ('--check',):
                argvals['check'] = 1
            elif arg in ('-p',):
                argvals['show_private'] = 1
            elif arg in ('-a', '-check_all'):
                argvals['check_all'] = 1
            elif arg in ('--css',):
                argvals['css'] = args.pop()
                if argvals['css'] == 'help':
                    _csshelp()
            else:
                _usage()
        else:
            argvals['modules'].append(arg)

    if argvals['modules'] == []: _usage()
    return argvals

def _find_module_from_filename(filename,verbosity):
    """
    @return: The module contained in C{filename}.
    @rtype: C{module}
    @param filename: The filename that contains the module.
    @type filename: C{int}
    @param verbosity: Verbosity level for tracing output.
    @type verbosity: C{int}
    """
    old_cwd = os.getcwd()

    # Normalize the filename
    filename = os.path.normpath(os.path.abspath(filename))
    
    # Extract the module name and the base directory.
    name = re.sub(r'/?__init__\.py.?$', '', filename)
    name = re.sub(r'\.py.?$', '', name)
    name = re.sub(r'/$', '', name)
    (basedir, module) = os.path.split(name)
    
    # If there's a package, then find its base directory.
    if os.path.exists(os.path.join(basedir, '__init__.py')):
        # Otherwise, find the base package directory.
        package = []
        while os.path.exists(os.path.join(basedir, '__init__.py')):
            (basedir,dir) = os.path.split(basedir)
            if dir == '': break
            package.append(dir)
        package.reverse()
        module = '.'.join(package+[module])

    # Import the module.
    try:
        try:
            if verbosity > 1: print 'Importing', module
            if basedir: os.chdir(basedir)
            exec('import %s as rv' % module)
            #exec('import %s' % module)
            #exec('rv = %s' % module)
            return rv
        finally:
            os.chdir(old_cwd)
    except ImportError, e:
        if re.match(r'^.*__init__\.py?$', filename):
            raise ImportError("Run epydoc from the parent directory "+
                              "(%r):\n%s" % (filename, e))
        raise ImportError("Could not find module %r:\n%s" % (filename, e))

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
    modules = []
    for name in module_names:
        if '/' in name or name[-3:] == '.py' or name[-4:-1] == '.py':
            module = _find_module_from_filename(name, verbosity)
            if module not in modules:
                modules.append(module)
            elif verbosity > 3: print "  (duplicate)"
        else:
            try:
                if verbosity > 1: print 'Importing', name
                # Otherwise, try importing it.
                exec('import %s' % name)
                exec('module = %s' % name)
                if module not in modules:
                    modules.append(module)
                elif verbosity > 3: print "  (duplicate)"
            except ImportError:
                raise ImportError("Could not import %s" % name)

    return modules


def cli():
    """
    Command line interface for epydoc.
    
    @rtype: C{None}
    """
    sys.path.append('.')
    param = _parse_args()

    try:
        modules = _find_modules(param['modules'], param['verbosity'])
    except ImportError, e:
        if e.args: self._error(e.args[0])
        else: raise

    # Wait to do imports, to make --usage faster.
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
    d = DocMap(not param['check'])
    
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
    
