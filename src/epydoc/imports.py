#!/usr/bin/env python
#
# import: module import support for epydoc
# Edward Loper
#
# Created [10/06/02 02:14 AM]
# $Id$
#

"""
Module import support for epydoc.  C{imports} defines a single public
function, C{import_module}, which finds and imports a module, given
its module name or its file name.
"""

import sys, re, types, os.path

def _find_module_from_filename(filename):
    """
    Break a module/package filename into a base directory and a module
    name.  C{_find_module_from_filename} checks directories in the
    filename to see if they contain C{"__init__.py"} files; if they
    do, then it assumes that the module is part of a package, and
    returns the full module name.  For example, if C{filename} is
    C{"/tmp/epydoc/imports.py"}, and the file
    C{"/tmp/epydoc/__init__.py"} exists, then the base directory will
    be C{"/tmp/"} and the module name will be C{"epydoc.imports"}.
    
    @return: A pair C{(basedir, module)}, where C{basedir} is the base
        directory from which the module can be imported; and C{module}
        is the name of the module itself.    
    @rtype: C{(string, string)}

    @param filename: The filename that contains the module.
        C{filename} can be a directory (for a package); a C{.py} file;
        a C{.pyc} file; a C{.pyo} file; or an C{.so} file.
    @type filename: C{string}
    """
    # Normalize the filename
    filename = os.path.normpath(os.path.abspath(filename))
    
    # Extract the module name and the base directory.
    name = re.sub(r'/?__init__\.py.?$', '', filename)
    name = re.sub(r'\.py.?$', '', name)
    name = re.sub(r'\.so$', '', name)
    name = re.sub(r'/$', '', name)
    (basedir, module) = os.path.split(name)
    
    # If there's a package, then find its base directory.
    if os.path.exists(os.path.join(basedir, '__init__.py')):
        package = []
        while os.path.exists(os.path.join(basedir, '__init__.py')):
            (basedir,dir) = os.path.split(basedir)
            if dir == '': break
            package.append(dir)
        package.reverse()
        module = '.'.join(package+[module])

    return (basedir, module)

def import_module(name):
    """    
    Return the module identified by the given name.  C{import_module}
    makes some attempts to prevent the imported module from modifying
    C{sys} and C{__builtins__}.  In the future, more sandboxing might
    be added (e.g., using the C{rexec} module).

    @return: The module with the given name.
    @rtype: C{module}
    @param name: The name of the module to import.  C{name} can
        either be a module name (such as C{os.path}); a filename (such
        as C{epytext.py} or C{multiarray.so}); or a directory name
        (such as C{site-packages/distutils}).
    @type name: C{string}
    @raise ImportError: If there was any problem importing the given
        object.  In particular, an C{ImportError} is raised if the
        given file does not exist; if the given file name does not
        name a valid module; or if importing the module causes an
        exception to be raised.
    """
    # If we've already imported it, then just return it.
    if sys.modules.has_key(name):
        return sys.modules[name]

    # Save some important values.  This helps prevent the module that
    # we import from breaking things *too* badly.  Also, save sys.path, 
    # because we will modify if we're importing from a filename.
    old_sys = sys.__dict__.copy()
    old_sys_path = sys.path[:]
    if type(__builtins__) == types.DictionaryType:
        old_builtins = __builtins__.copy()
    else:
        old_builtins = __builtins__.__dict__.copy()
    #old_sys_modules = sys.modules.copy()

    try:
        # If they gave us a file name, then convert it to a module
        # name, and update the path appropriately.
        if '/' in name or re.match('\.py[cow]?$|\.so$', name):
            if not os.path.exists(name):
                raise ImportError('%r does not exist' % name)
                return None
            (basedir, name) = _find_module_from_filename(name)
            sys.path = [basedir] + sys.path

        # Make sure that we have a valid name
        if not re.match(r'^[a-zA-Z_]\w*(\.[a-zA-Z_]\w*)*$', name):
            raise ImportError('Bad module name %r' % name)
            
        # Import the module.  Note that if "name" has a package
        # component, then this just gives us the top-level object.
        try:
            topLevel = __import__(name)
        except Exception, e:
            raise ImportError('Could not import %r -- %r' % (name, e))
        except SystemExit, e:
            raise ImportError('Could not import %r -- %r' % (name, e))
        except:
            raise ImportError('Could not import %r')
        
        # If "name" has a package component, then we have to manually
        # go down the package tree.
        pieces = name.split(".")[1:]
        m = topLevel
        for p in pieces:
            m = getattr(m, p)
            
        return m
    finally:
        # Restore the important values that we saved.
        if type(__builtins__) == types.DictionaryType:
            __builtins__.update(old_builtins)
        else:
            __builtins__.__dict__.update(old_builtins)
        sys.__dict__.update(old_sys)
        sys.path = old_sys_path
        #sys.modules = old_sys_modules

if __name__ == '__main__':
    # A few quick tests.
    print import_module('os.path')
    print import_module('/usr/lib/python2.1/linecache.py')
    print import_module('/usr/lib/python2.1/distutils/cmd.py')
    print import_module('/usr/lib/python2.1/distutils/__init__.py')
    print import_module('/usr/lib/python2.1/distutils/')
    print import_module('/usr/lib/python2.1/site-packages/'+
                        'Numeric/multiarray.so')
    
    
