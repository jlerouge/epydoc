# epydoc -- Regression testing
#
# Copyright (C) 2005 Edward Loper
# Author: Edward Loper <edloper@loper.org>
# URL: <http://epydoc.sf.net>
#
# $Id$

"""
Regression testing.
"""
__docformat__ = 'epytext en'

import unittest, doctest, epydoc, os, os.path, re

def main():
    # Turn on debugging.
    epydoc.DEBUG = True
    
    # Options for doctest:
    options = doctest.ELLIPSIS
    doctest.set_unittest_reportflags(doctest.REPORT_UDIFF)

    # Find all test cases.
    tests = []
    testdir = os.path.join(os.path.split(__file__)[0])
    if testdir == '': testdir = '.'
    for filename in os.listdir(testdir):
        if (filename.endswith('.doctest') and
            check_requirements(os.path.join(testdir, filename))):
            tests.append(doctest.DocFileSuite(filename, optionflags=options))
            
    # Run all test cases.
    unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(tests))

def check_requirements(filename):
    """
    Search for strings of the form:
    
        [Require: <module>]

    If any are found, then try importing the module named <module>.
    If the import fails, then return False.  If all required modules
    are found, return True.  (This includes the case where no
    requirements are listed.)
    """
    s = open(filename).read()
    for m in re.finditer('(?mi)^[ ]*\:RequireModule:[ ]+(\w+)[ ]*$', s):
        module = m.group(1)
        try:
            __import__(module)
        except ImportError:
            print ('Skipping %r (required module %r not found)' %
                   (os.path.split(filename)[-1], module))
            return False
    return True
            

if __name__=='__main__':
    main()
