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
     - L{epydoc.uid} is used to create unique identifiers for each
       object.
     - L{epydoc.epytext} is used to parse the objects' documentation
       strings.
  3. Produce HTML output, using L{epydoc.html}.
     - L{epydoc.css} is used to generate the CSS stylehseet.
     - L{epydoc.help} is used to generate the help page.
     - L{epydoc.colorize} is used to colorize doctest blocks and
       regular expressions variable values.

@author: U{Edward Loper<mailto:edloper@gradient.cis.upenn.edu>}
@requires: Python 2.1, or Python 2.0 with
    U{C{inspect.py}<http://lfw.org/python/inspect.html>}.
@version: 1.1
@see: U{The epydoc webpage<http://epydoc.sourceforge.net>}
@see: U{The epytext markup language
    manual<http://epydoc.sourceforge.net/epytext.html>}
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
__epydoc_sort__ = ['cli', 'gui', 'imports', 
                   'objdoc', 'epytext', 'uid',
                   'html', 'css', 'help', 'colorize',
                   'checker']

# To do for release 1.1:
#   - add an option to specify the "top" object
#   - add escape characters to epytext??
#   - add option: don't include vars and cvars that have no descr?
#   - update gui to reflect changes in epydoc.
#     - Add real argument processing, fix manpage
#     - Add options: frames; private; imports; private css; help file
#   - Add @note?  other tags?  look at doxygen?
#   - Add "--docformat=?".  "=auto" will check the __docformat__
#     option, defaulting to "plaintext."  Currently recognized doc
#     formats are epytext and plaintext.  This comes from the module
#     that defines the object, not the one that imports it!
#   - html should write to files, rather than building up strings, esp
#     for index and trees?
#   - Support L{foo()}??

# To do after release 1.1:
#   - better doc inheritence?
#     - refactor inheritance
#     - option to turn off function doc inheritance?
#     - add --check for doc inheritance?

# Other issues
#   - curses.wrapper names both a function and a module; how to
#     distinguish them?  Use html names like module-curses.wrapper
#     vs. function-curses.wrapper?  Ick.  Or just ignore it... :)
    
