#
# epydoc package file
#
# A python documentation Module
# Edward Loper
#
# Created [01/30/01 05:18 PM]
# $Id$
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
     - The L{epydoc.markup} package is used to parse the objects'
       documentation strings.
  3. Generate output, using L{epydoc.html} or L{epydoc.latex}.
     - L{epydoc.css} is used to generate the CSS stylehseet for HTML output.
     - L{epydoc.help} is used to generate the help page for HTML output.
     - L{epydoc.colorize} is used to colorize doctest blocks and
       regular expressions variable values for HTML output.

@group Interface Modules: cli, gui
@group Inspection Modules: uid, objdoc, imports
@group Docstring Parsing Modules: markup
@group Documentation Output Modules: html, css, help, colorize,
       latex, man
@group Testing Modules: checker, test

@sort: cli, gui, uid, objdoc, imports, markup, html, css, help,
       colorize, latex, man

@author: U{Edward Loper<edloper@gradient.cis.upenn.edu>}
@requires: Python 2.1+, or Python 2.0 with
    U{C{inspect.py}<http://lfw.org/python/inspect.html>}.
@version: 2.0S{alpha}
@see: U{The epydoc webpage<http://epydoc.sourceforge.net>}
@see: U{The epytext markup language
    manual<http://epydoc.sourceforge.net/epytext.html>}

@todo 2.0: Add a '@kwarg' field for documenting **kwarg parameters?
  - synonyms: @kwarg, @kwargument, @kwparam, @kwparameter,
    @keywordarg, @keywordparam, etc.?  @keyword?
@todo 2.0: Improve ModuleDoc._find_imported_variables (params?)
@todo 2.0: Improve uid.findUID
@todo 2.0: Fix _find_override (A defines x, B inherits, C inherits,
    C overrides x?)
@todo 2.0: Optimization
  - optimize epytext?
@todo 2.0: check things like name of css file earlier (before
    building all objdocs?)

@todo 2.0?: regexps for @group and @sort? :)
    - so you could say '@group accessors: get_*'
    - or '@group accessors: get_.*' ??
  How to do this??
@todo 2.0?: Handle '@param a,b'?  (where should they be listed?)
@todo 2.0?: Other @param or @extraparm type things?
    
@todo 3.0: Create a better default top_page than trees.html.
@todo 3.0: Add the man-page style outputter. (epyman)
@todo 3.0: Refactor L{epydoc.objdoc.ObjDoc}:
    - C{ObjDoc}s will contain info about objects, but not gather it.
    - An C{inspection} module will gather info via inspection.
    - A new C{parsing} module will provide an alternative, gathering
      info by parsing python files.
    - C{Var} will be replaced by C{VarDoc}, a subclass of C{ObjDoc}.
    - Structure C{ObjDoc}s in a directed acyclic graph, rather than
      using a links and a dictionary?  Are non-directed cycles a
      problem?  Interaction of the access hierarchy (a.b.c) and
      the base class hierarchy?  What does pydoc do?
@todo 3.0: Docstring inheritance for overridden properties.

@license: IBM Open Source License
@copyright: (C) 2003 Edward Loper

@newfield contributor: Contributor, Contributors (Alphabetical Order)
@contributor: U{Glyph Lefkowitz <mailto:glyph@twistedmatrix.com>}
@contributor: U{Edward Loper <mailto:edloper@gradient.cis.upenn.edu>}
@contributor: U{Bruce Mitchener <mailto:bruce@cubik.org>}
@contributor: U{Christian Reis <mailto:kiko@async.com.br>}

@var __license__: The license governing the use and distribution of
    epydoc.
"""
__docformat__ = 'epytext en'

# General info
__version__ = '2.0 alpha'
__author__ = 'Edward Loper <edloper@gradient.cis.upenn.edu>'
__url__ = 'http://epydoc.sourceforge.net'

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
#   - new fields (@group: order is significant??; @sort)
#   - depreciated __epydoc_sort__
#   - staticmethod/classmethod
#   - document __extra_epydoc_fields__ and @newfield
#   - Add a faq?
#   - @summary
#   - @type a,b,c: ...
