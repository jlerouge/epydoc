# epydoc
#
# Copyright (C) 2005 Edward Loper
# Author: Edward Loper <edloper@loper.org>
# URL: <http://epydoc.sf.net>
#
# $Id$

"""
Automatic Python reference documentation generator.  Epydoc processes
Python modules and docstrings to generate formatted API documentation,
in the form of HTML pages.  Epydoc can be used via a command-line
interface (L{epydoc.cli}) and a graphical interface (L{epydoc.gui}).
Both interfaces let the user specify a set of modules to document, and
produce API documentation using the following steps:

Architecture graph::

   Python object             Module source code
         |                           |
         V                           V
  +--------------+             +-----------+
  | DocInspector |             | DocParser |
  +--------------+             +-----------+
         |                           |
         +---------+     +-----------+
                   |     |
                   V     V
                +-----------+     Merges the output from DocParser
                | DocMerger |     into the output from DocInspector.
                +-----------+     
                      |
                      V
               +------------+     Creates an index for the ValueDoc
               | DocIndexer |     objects; and assigns canonical names
               +------------+     to any ValueDocs that don't have them.
                      |
                      V
             +-----------------+  Parses all docstrings, and
             | DocstringParser |  processes all docstring fields.
             +-----------------+
                      |
                      V
              +--------------+    Handles documentation inheritance?
              | DocInheriter |
              +--------------+
                      |
                      V
               +------------+     Outputs the APIDoc objects to
               | DocWriters |     appropriate formats
               +------------+


[XX] Out of date::

  1. Import the requested modules, using L{epydoc.imports}.
  2. Construct documentation for each object, using L{epydoc.objdoc}.
     - L{epydoc.uid} is used to create unique identifiers for each
       object.
     - The L{epydoc.markup} package is used to parse the objects'
       documentation strings.
  3. Generate output, using L{epydoc.html} or L{epydoc.latex}.
     - L{epydoc.css} is used to generate the CSS stylehseet for HTML output.
     - L{epydoc.help} is used to generate the help page for HTML output.
     - L{epydoc.colorize} is used to colorize doctest blocks and
       regular expressions variable values for HTML output.

[XX] Add groups later.

@author: U{Edward Loper<edloper@gradient.cis.upenn.edu>}
@requires: Python 2.1+, or Python 2.0 with
    U{C{inspect.py}<http://lfw.org/python/inspect.html>}.
@version: 2.1
@see: U{The epydoc webpage<http://epydoc.sourceforge.net>}
@see: U{The epytext markup language
    manual<http://epydoc.sourceforge.net/epytext.html>}

@todo: Consider other names for C{@undocumented}:
    C{@bypass}, C{@nodoc}, C{@exclude}, C{@omit}?

@todo 3.0: Support encodings.
@todo 3.0: Create a better default top_page than trees.html.
@todo 3.0: Add the man-page style outputter. (epyman)
@todo 3.0: Docstring inheritance for overridden properties.
@todo 3.0: Optimize epytext
    - Use classes instead of minidom nodes?
@todo 3.0: Rewrite C{epydoc.uid.findUID} to be more robust.

@license: IBM Open Source License
@copyright: (C) 2003 Edward Loper

@newfield contributor: Contributor, Contributors (Alphabetical Order)
@contributor: U{Glyph Lefkowitz <mailto:glyph@twistedmatrix.com>}
@contributor: U{Edward Loper <mailto:edloper@gradient.cis.upenn.edu>}
@contributor: U{Bruce Mitchener <mailto:bruce@cubik.org>}
@contributor: U{Simon Pamies <mailto:spamies@bipbap.de>}
@contributor: U{Christian Reis <mailto:kiko@async.com.br>}
@contributor: U{Jeff O'Halloran <mailto:jeff@ohalloran.ca>}

@var __license__: The license governing the use and distribution of
    epydoc.
"""
__docformat__ = 'epytext en'

# General info
__version__ = '2.1'
__author__ = 'Edward Loper <edloper@gradient.cis.upenn.edu>'
__url__ = 'http://epydoc.sourceforge.net'
__license__ = 'IBM Open Source License'

# Issues
#   - curses.wrapper names both a function and a module; how to
#     distinguish them?  Of course, we can't even *access* the module,
#     since "import curses.wrapper" gives us a function. :-/

# Changes needed for docs:
#   - document the method for deciding what's public/private
#   - epytext: fields are defined slightly differently (@group)
#   - new fields
#   - document __extra_epydoc_fields__ and @newfield
#   - Add a faq?
#   - @type a,b,c: ...
#   - new command line option: --command-line-order

