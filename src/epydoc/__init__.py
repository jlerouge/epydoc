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

@author: U{Edward Loper<edloper@gradient.cis.upenn.edu>}
@requires: Python 2.1, or Python 2.0 with
    U{C{inspect.py}<http://lfw.org/python/inspect.html>}.
@version: 1.2
@see: U{The epydoc webpage<http://epydoc.sourceforge.net>}
@see: U{The epytext markup language
    manual<http://epydoc.sourceforge.net/epytext.html>}
"""
__docformat__ = 'epytext en'

# General info
__version__ = '1.2 prerelease'
__author__ = 'Edward Loper <edloper@gradient.cis.upenn.edu>'
__url__ = 'http://epydoc.sourceforge.net'

# Copyright/license info
__copyright__ = '(C) 2002 Edward Loper'
__license__ = 'IBM Open Source License'

# Contributors to epydoc (in alpha order by last name)
__contributors__ = ['Glyph Lefkowitz <glyph@twistedmatrix.com>',
                    'Edward Loper <edloper@gradient.cis.upenn.edu>',
                    'Bruce Mitchener <bruce@cubik.org>',
                    'Christian Reis <kiko@async.com.br>']

# Sort order
__epydoc_sort__ = ['cli', 'gui', 'imports', 
                   'objdoc', 'epytext', 'uid',
                   'html', 'css', 'help', 'colorize',
                   'checker']

# To do:
#   - add escape characters to epytext? (e.g. E{->})
#   - switch to turn on/off inherited methods in the method summary
#     list. (like the [frames/noframes] and [show/hide private] 
#     switches?)
#   - add @group (e.g. "@group accessors:")
#   - Add other field tags?
#   - better doc inheritence?
#     - refactor inheritance
#     - option to turn off function doc inheritance?
#     - add --check for doc inheritance?
#   - Change html to write directly to files, instead of building up strings
#      and then writing them.
#   - add option: don't include vars and cvars that have no descr?
#   - create a better default top_page than trees.html
#   - render package's module sublists as some kind of table?
#   - use <SPAN TITLE=""> for partially ellided var values?
#   - put var values in the summary table?
#   - options to --check (--check all, --check basic, etc)

# Other issues
#   - curses.wrapper names both a function and a module; how to
#     distinguish them?  Of course, we can't even *access* the module,
#     since "import curses.wrapper" gives us a function. :-/
