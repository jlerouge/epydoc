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
    epydoc [-o DIR] [-n NAME] [-p] MODULE...
    epydoc --check [-p] [-a] MODULE...
    epydoc --usage
    epydoc --version

    MODULE...
        List of filenames containing modules to process.  When
        documenting packages, the filename must include the package
        directory (i.e., you can't run epydoc within the package
        directory, using relative filenames).
        
    --check
        Perform completeness checks on the documentation

    --usage, --help, -h, -?
        Display this usage message.

    --version, -V
        Print the version of Epydoc.

    -o DIR, --output DIR, --target DIR
        Output directory for HTML files
        
    -n NAME, --name NAME
        Package name (for HTML header/footer)

    --url, -u
        Package URL (for HTML header/footer)

    -p
        Show private objects (those that start with _)

    -a
        Run all checks.

    -v, --verbose
        Produce verbose output

    -vv, -vvv, -vvvv
        Produce successively more verbose output

    -css2
        Use alternate CSS file (for HTML)
"""

import sys, os.path, re

##################################################
## Command-Line Interface
##################################################

def _usage(exit_code=-1):
    NAME = os.path.split(sys.argv[0])[-1]
    print __doc__[36:].replace('epydoc', NAME)
    sys.exit(exit_code)

def _version():
    import epydoc
    print "Epydoc version %s" % epydoc.__version__
    sys.exit(0)

def _error(str):
    print "%s Error: %s" % (os.path.split(sys.argv[0])[-1], str)
    sys.exit(-1)

def _parse_args():
    """
    Process the command line arguments; return a dictionary containing
    the relevant info.
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
                _usage(0)
            elif arg in ('--check',):
                argvals['check'] = 1
            elif arg in ('-p',):
                argvals['show_private'] = 1
            elif arg in ('-a', '-check_all'):
                argvals['check_all'] = 1
            elif arg in ('-css2',):
                argvals['css'] = 2
            else:
                _usage()
        else:
            argvals['modules'].append(arg)

    if argvals['modules'] == []: _usage()
    return argvals

def _find_module_from_filename(filename,verbosity):
    """
    Given a filename, import the corresponding module.
    """
    old_cwd = os.getcwd()

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
            if verbosity == 1: print 'Importing', module
            if basedir: os.chdir(basedir)
            exec('import %s' % module)
            exec('rv = %s' % module)
            return rv
        finally:
            os.chdir(old_cwd)
    except ImportError, e:
        if re.match(r'^.*__init__\.py?$', filename):
            _error("Run epydoc from the parent directory (%r):\n%s" %
                   (filename, e))
        _error("Could not find module %r:\n%s" % (filename, e))

def _find_modules(module_names, verbosity):
    """
    Given a list of module names, return a list of modules.  Don't
    include duplicates.  
    """
    modules = []
    for name in module_names:
        if verbosity > 1: print 'Importing', name
        if '/' in name or name[-3:] == '.py' or name[-4:-1] == '.py':
            module = _find_module_from_filename(name, verbosity)
            if module not in modules:
                modules.append(module)
            elif verbosity > 3: print "  (duplicate)"
        else:
            try:
                if verbosity == 1: print 'Importing', name
                # Otherwise, try importing it.
                exec('import %s' % name)
                exec('module = %s' % name)
                if module not in modules:
                    modules.append(module)
                elif verbosity > 3: print "  (duplicate)"
            except ImportError:
                _error("Could not import %s" % name)

    return modules

def cli():
    """
    Command line interface for epydoc.
    """
    param = _parse_args()

    modules = _find_modules(param['modules'], param['verbosity'])

    # Wait to do imports, to make --usage faster.
    from epydoc.html import HTML_Doc, CSS_FILE2
    from epydoc.objdoc import Documentation
    from epydoc.checker import DocChecker

    # Create dest directory, if necessary
    if not os.path.isdir(param['target']):
        if not os.path.exists(param['target']):
            try: os.mkdir(param['target'])
            except: _error("Could not create %r" % param['target'])
        else:
            _error("%r is not a directory" % param['target'])

    # Build the documentation.
    d = Documentation()
    for module in modules:
        if param['verbosity'] > 0: print 'Building docs for', module.__name__
        d.add(module)

    if param['check']:
        # Run completeness checks.
        if param['verbosity'] > 0: print 'Performing completeness checks'
        checker = DocChecker(d)
        if param['show_private']:
            checker.check(DocChecker.MODULE | DocChecker.CLASS |
                          DocChecker.FUNC | DocChecker.DESCR_LAZY |
                          DocChecker.PUBLIC | DocChecker.PRIVATE)
            checker.check(DocChecker.PARAM | DocChecker.VAR |
                          DocChecker.IVAR | DocChecker.CVAR |
                          DocChecker.RETURN | DocChecker.DESCR |
                          DocChecker.TYPE | DocChecker.PUBLIC |
                          DocChecker.PRIVATE)
        else:
            checker.check(DocChecker.MODULE | DocChecker.CLASS |
                          DocChecker.FUNC | DocChecker.DESCR_LAZY |
                          DocChecker.PUBLIC)
            checker.check(DocChecker.PARAM | DocChecker.VAR |
                          DocChecker.IVAR | DocChecker.CVAR |
                          DocChecker.RETURN | DocChecker.DESCR |
                          DocChecker.TYPE | DocChecker.PUBLIC)
    else:
        # Write documentation.
        if param['verbosity'] == 2: print 'Writing docs to', param['target'],
        elif param['verbosity'] > 0: print 'Writing docs to', param['target']
        if param.get('css', None) == 2: param['css'] = CSS_FILE2
        else: css=None
        htmldoc = HTML_Doc(d, **param)
        htmldoc.write(param['target'], param['verbosity']-1)
        if param['verbosity'] > 1: print
    
if __name__ == '__main__':
    # This seems to help:
    sys.path.append('.')
    
    cli()
    
