#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
"""Epydoc regression test.
"""

# Copyright (C) 2006 by Daniele Varrazzo
# $Id$
__version__ = "$Revision$"[11:-2]

import os, sys, shutil
import unittest

def get_test_script():
    return get_file("..", "..", "scripts", 'epydoc.py')

def get_file(*path):
    """Return a file name relative from this script path."""
    return os.path.normpath(os.path.join(os.path.split(__file__)[0],
        *path))
    
def spawn(*argv):
    """Run the application with given arguments and return exit value."""
    script = get_test_script()
    if os.name == "nt":
        cmd = [sys.executable, '"' + script + '"']
    else:
        cmd = [script]
        
    cmd += reduce(lambda a,b: a + b, [a.split(" ") for a in argv])
    
    print "\n>>>\n%s\n" % ' '.join(cmd)
    return os.spawnv(os.P_WAIT, cmd[0], cmd)
    
class HtmlEncodingTestCase(unittest.TestCase):
    """Perform a set of complete run of epydoc script.
    """
    def setUp(self):
        # clear output directory
        shutil.rmtree(get_file("output"))
        os.mkdir(get_file("output"))
        
    def spawn(self, *argv):
        """Run epydoc with a set of predefined values.
        
        The purpose of the --debug parameters is to exit from the scripts with
        a value > 0.
        """
        return spawn("--debug --html --output", get_file("output"), *argv)
        
    def test_cp1252_output(self):
        """Can generate cp1252-encoded API from reST docstrings"""
        self.assertEqual(0, self.spawn(
            "--docformat restructuredtext",
            "--encoding cp1252",
            get_file("input", "encoding_test_cp1252.py")))
        
    def test_utf8_output(self):
        """Can generate utf8-encoded API from reST docstring"""
        self.assertEqual(0, self.spawn(
            "--docformat restructuredtext",
            "--encoding utf8",
            get_file("input", "encoding_test_utf8.py")))
                  
    def test_unicode_in_field_arg(self):
        """Epydoc doesn't choke when fields receive unicode in a field arg."""
        self.assertEqual(0, self.spawn(
            "--docformat restructuredtext",
            "--encoding iso-8859-1",
            get_file("input", "editordine.py")))
                  
def testsuite():
    return unittest.TestSuite([ unittest.makeSuite(globals()[k])
        for k in globals().keys() if k.endswith('TestCase') ])

if __name__ == '__main__':
    import os.path
    unittest.main(module=os.path.splitext(os.path.basename(__file__))[0], 
                  defaultTest='suite')
