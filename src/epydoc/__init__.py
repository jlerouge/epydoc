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

@order: cli, gui, uid, objdoc, imports, epytext, html, css, help,
       colorize, latex, man

@author: U{Edward Loper<edloper@gradient.cis.upenn.edu>}
@requires: Python 2.1, or Python 2.0 with
    U{C{inspect.py}<http://lfw.org/python/inspect.html>}.
@version: 1.2 alpha
@see: U{The epydoc webpage<http://epydoc.sourceforge.net>}
@see: U{The epytext markup language
    manual<http://epydoc.sourceforge.net/epytext.html>}

@todo 1.2: Add support for Docutils/ReST?
@todo 1.2: Add support for escape characters & groups to the latex
    outputter.
@todo 1.2: Finish the man-page style outputter.
@todo 1.2: Create a better default top_page than trees.html
@todo 1.2: More options for --check (--check all, --check basic)
@todo 1.2: Add more symbols (like E{E}{->}).
@todo 1.2: Add --no-inheritance?
@todo 1.2: Add --check for doc inheritance? (??)

@todo 1.3: Modify L{epydoc.html} to write directly to streams,
    rather than building up strings.
    
@todo 2.0: Refactor L{epydoc.objdoc.ObjDoc}: ObjDoc will just
    contain info about objects, but not gather it.  An 'inspection' 
    module will be responsible for gathering the info.
@todo 2.0: Add an alternative 'parsing' module that can gather
    info by parsing python files, instead of using inspection.

@var __license__: The license governing the use and distribution of
    epydoc.
@var __contributors__: Contributors to epydoc, in alphabetical
    order by last name.
"""
__docformat__ = 'epytext en'

# General info
__version__ = '1.2 alpha'
__author__ = 'Edward Loper <edloper@gradient.cis.upenn.edu>'
__url__ = 'http://epydoc.sourceforge.net'

# Copyright/license info
__copyright__ = '(C) 2003 Edward Loper'
__license__ = 'IBM Open Source License'

# Contributors to epydoc (in alpha order by last name)
__contributors__ = ['Glyph Lefkowitz <glyph@twistedmatrix.com>',
                    'Edward Loper <edloper@gradient.cis.upenn.edu>',
                    'Bruce Mitchener <bruce@cubik.org>',
                    'Christian Reis <kiko@async.com.br>']

# To do:
#   - Change html to write directly to files, instead of building up strings
#      and then writing them?

# Issues
#   - curses.wrapper names both a function and a module; how to
#     distinguish them?  Of course, we can't even *access* the module,
#     since "import curses.wrapper" gives us a function. :-/

# Changes needed for docs:
#   - document the method for deciding what's public/private
#   - fields are defined slightly differently (@group)
#   - new fields (@group: order is significant; @sort)
#   - depreciated __epydoc_sort__
#   - staticmethod/classmethod
#   - document __extra_epydoc_fields__ and @newfield
#   - Add a faq?
