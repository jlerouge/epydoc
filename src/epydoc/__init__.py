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
       strings, if they are written using the U{epytext markup
       language<http://epydoc.sourceforge.net/epytext.html>}.
  3. Produce HTML output, using L{epydoc.html}.
     - L{epydoc.css} is used to generate the CSS stylehseet.
     - L{epydoc.help} is used to generate the help page.
     - L{epydoc.colorize} is used to colorize doctest blocks and
       regular expressions variable values.

@group Interface Modules: cli, gui
@group Inspection Modules: uid, objdoc, imports
@group Docstring Parsing Modules: epytext
@group Documentation Output Modules: html, css, help, colorize,
       latex, man
@group Testing Modules: checker, test

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
__epydoc_sort__ = [
    # interfaces
    'cli', 'gui',

    # Inspection
    'imports', 'objdoc', 'epytext', 'uid',

    # HTML Formatter
    'html', 'css', 'help', 'colorize',

    # LaTeX Formatter
    'latex',

    # Manpage Formatter
    'man',

    # Documentation completeness checker
    'checker']

# To do:
#   - Add more escape characters?
#   - Add escape character & group support to latex
#   - finish man-page output
#   - Change html to write directly to files, instead of building up strings
#      and then writing them?
#   - add option: don't include vars and cvars that have no descr?
#   - create a better default top_page than trees.html
#   - options to --check (--check all, --check basic, etc)
#   - Improve error message "Unknown field tag 'ivar'" when they
#     try to use an ivar in the wrong context (etc.)
#   - Add support for properties

# To do: medium-term
#   - better doc inheritence?
#     - refactor inheritance
#     - option to turn off function doc inheritance?
#     - add --check for doc inheritance?

# To do: long-term
#   - Add support for getting docs from parsing?

# Other issues
#   - curses.wrapper names both a function and a module; how to
#     distinguish them?  Of course, we can't even *access* the module,
#     since "import curses.wrapper" gives us a function. :-/

# Changes needed for docs:
#   - document the method for deciding what's public/private
#   - fields are defined slightly differently (@group)
#   - new fields (@group: order is significant)
#   - staticmethod/classmethod
#   - document __extra_epydoc_fields__
