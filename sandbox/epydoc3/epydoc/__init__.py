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
Both interfaces let the user specify a set of modules or other objects
to document, and produce API documentation using the following steps:

  1. Extract basic information about the specified objects, and objects
     that are related to them (such as the values defined by a module).
     This can be done via introspection, parsing, or both:
  
       1.1. Use introspection to examine the objects directly.
   
       1.2. Parse the Python source files that define the objects,
            and extract information from those files.

  2. Combine and process that information.

       2.1. Merge the information obtained from introspection & parsing
            each object into a single structure.  (This step is
            skipped if information was extracted from only introspection
            or only parsing.)

       2.2. Replace any 'pointers' that were created for imported
            variables with the documentation that they point to (if
            it's available).

       2.3. Assign unique 'canonical names' to each of the specified
            objects, and any related objects.

       2.4. Parse the docstrings of each of the specified objects, and
            any related objects.

       2.5. Add variables to classes for any values that they inherit
            from their base classes.

  3. Generate output.  Output can be generated in a variety of
     formats:

        3.1. An HTML webpage

        3.2. other formats (under construction)

@author: U{Edward Loper<edloper@gradient.cis.upenn.edu>}
@requires: Python 2.1+, or Python 2.0 with
    U{C{introspect.py}<http://lfw.org/python/introspect.html>}.
@version: 2.1
@see: U{The epydoc webpage<http://epydoc.sourceforge.net>}
@see: U{The epytext markup language
    manual<http://epydoc.sourceforge.net/epytext.html>}

@todo: s/introspection/introspection/ ???
@todo: Create a better default top_page than trees.html.
@todo: Fix trees.html to work when documenting non-top-level
       modules/packages
@todo: Implement lots more of _inherit_info()
@todo: Implement @include
@todo: Optimize epytext
@todo: More doctests
@todo: When introspecting, limit how much introspection you do (eg,
       don't construct docs for imported modules' vars if it's
       not necessary)

@license: IBM Open Source License
@copyright: (C) 2003 Edward Loper

@newfield contributor: Contributor, Contributors (Alphabetical Order)
@contributor: U{Glyph Lefkowitz <mailto:glyph@twistedmatrix.com>}
@contributor: U{Edward Loper <mailto:edloper@gradient.cis.upenn.edu>}
@contributor: U{Bruce Mitchener <mailto:bruce@cubik.org>}
@contributor: U{Jeff O'Halloran <mailto:jeff@ohalloran.ca>}
@contributor: U{Simon Pamies <mailto:spamies@bipbap.de>}
@contributor: U{Christian Reis <mailto:kiko@async.com.br>}

@var __license__: The license governing the use and distribution of
    epydoc.
"""
__docformat__ = 'epytext en'

# General info
__version__ = '2.1'
__author__ = 'Edward Loper <edloper@gradient.cis.upenn.edu>'
__url__ = 'http://epydoc.sourceforge.net'
__license__ = 'IBM Open Source License'

# [xx] this should probably be a private variable:
DEBUG = True
"""True if debugging is turned on."""

# Changes needed for docs:
#   - document the method for deciding what's public/private
#   - epytext: fields are defined slightly differently (@group)
#   - new fields
#   - document __extra_epydoc_fields__ and @newfield
#   - Add a faq?
#   - @type a,b,c: ...
#   - new command line option: --command-line-order

