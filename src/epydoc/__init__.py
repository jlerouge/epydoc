#
# epydoc package file
#
# A python documentation Module
# Edward Loper
#
# Created [01/30/01 05:18 PM]
# $Id$
#
# Compatable with Python 2.0 and up.
# Requires inspect.py (which is standard for Python 2.1 and up)
#

"""
Automatic Python reference documentation generator.  Epydoc processes
Python modules and docstrings to generate formatted API documentation,
in the form of HTML pages.

@author: U{Edward Loper<mailto:edloper@gradient.cis.upenn.edu>}
"""

# General info
__version__ = '1.0'
__author__ = 'Edward Loper <edloper@gradient.cis.upenn.edu>'
__url__ = 'http://epydoc.sourceforge.net'

# Copyright/license info
__copyright__ = '(C) 2002 Edward Loper'
__license__ = 'IBM Open Source License'

# Contributors to epydoc (in alpha order by last name)
__contributors__ = ['Glyph Lefkowitz <glyph@twistedmatrix.com>',
                    'Edward Loper <edloper@gradient.cis.upenn.edu>',
                    'Bruce Mitchener <bruce@cubik.org>']

# Sort order
__epydoc_sort__ = ['objdoc',
                   'epytext',
                   'uid',
                   'html',
                   'css',
                   'checker',
                   'cli',
                   'gui']

# To do:
#   - improve support for builtin functions
#   - check for builtin modules
#   - when to inherit documentation?
#   - change epytext field syntax
#   - add escape characters

