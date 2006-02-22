# TEMPY

import os, os.path, re

PY_SRC_EXTENSIONS = ['.py', '.pyw']
PY_BIN_EXTENSIONS = ['.pyc', '.so']

def is_module_file(path):
    (dir, filename) = os.path.split(path)
    (basename, extension) = os.path.splitext(filename)
    return (os.path.isfile(path) and
            re.match('\w+$', basename) and
            extension in PY_SRC_EXTENSIONS+PY_BIN_EXTENSIONS)
    
def is_package_dir(dirname):
    """
    Return true if the given directory is a valid package directory
    (i.e., it names a directory that contsains a valid __init__ file,
    and its name is a valid identifier).
    """
    # Make sure it's a directory.
    if not os.path.isdir(dirname):
        return False
    # Make sure it's a valid identifier.  (Special case for
    # "foo/", where os.path.split -> ("foo", "").)
    (parent, dir) = os.path.split(dirname)
    if dir == '': (parent, dir) = os.path.split(parent)
    if not re.match('\w+$', dir):
        return False
    
    for name in os.listdir(dirname):
        filename = os.path.join(dirname, name)
        if name.startswith('__init__.') and is_module_file(filename):
            return True
    else:
        return False

def is_pyname(name):
    return re.match(r"\w+(\.\w+)*$", name)

def py_src_filename(filename):
    basefile, extension = os.path.splitext(filename)
    if extension in PY_SRC_EXTENSIONS:
        return filename
    else:
        for ext in PY_SRC_EXTENSIONS:
            if os.path.isfile('%s%s' % (basefile, ext)):
                return '%s%s' % (basefile, ext)
        else:
            raise ValueError('Could not find a Python source file '
                             'for %s.' % filename)
            
