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
in the form of HTML pages.  Epydoc can be used via a command-line
interface (L{epydoc.cli}) and a graphical interface (L{epydoc.gui}).
Both interfaces let the user specify a set of modules to document, and
produce API documentation using the following steps:

  1. Import the requested modules, using L{epydoc.imports}.
  2. Construct documentation for each object, using L{epydoc.objdoc}.
     L{epydoc.uid} is used to create unique identifiers for each
     object, and L{epydoc.epytext} is used to parse the objects'
     docstrings. 
  3. Produce HTML output, using L{epydoc.html}.  L{epydoc.css} and
     L{epydoc.help} are used to generate the CSS stylesheet and the
     help file.

@author: U{Edward Loper<mailto:edloper@gradient.cis.upenn.edu>}
"""

# General info
__version__ = '1.1'
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
__epydoc_sort__ = ['cli',
                   'gui',
                   'imports',
                   'objdoc',
                   'epytext',
                   'uid',
                   'html',
                   'css',
                   'checker',
                   ]

# To do:
#   - improve support for builtin functions/modules [90% done]
#   - frames [90% done]
#   - better doc inheritence?
#   - change epytext field syntax
#   - add escape characters to epytext
#   - support contained classes
#   - better checks for private/public in _extract_index
