#
# epydoc.css: default epydoc CSS stylesheets
# Edward Loper
#
# Created [01/30/01 05:18 PM]
# $Id$
#

"""
Predefined CSS stylesheets for the HTML outputter (L{epydoc.html}).

@type STYLESHEETS: C{dictionary} from C{string} to C{(string, string)}
@var STYLESHEETS: A dictionary mapping from stylesheet names to CSS
    stylesheets and descriptions.  A single stylesheet may have
    multiple names.  Currently, the following stylesheets are defined:
      - C{default}: The default stylesheet (synonym for C{white}).
      - C{white}: Black on white, with blue highlights (similar to
        javadoc).
      - C{blue}: Black on steel blue.
      - C{green}: Black on green.
      - C{black}: White on black, with blue highlights
      - C{grayscale}: Grayscale black on white.
      - C{none}: An empty stylesheet.
      - C{empty}: Synonym for C{none}.
"""

import re

############################################################
## Basic stylesheets
############################################################

# Black on white, with blue highlights.  This is similar to how
# javadoc looks.
_WHITE = """
/* Body color */ 
body              { background: #ffffff; color: #000000; } 
 
/* Tables */ 
table.summary, table.details, table.index
                  { background: #e8f0f8; color: #000000; } 
tr.summary, tr.details, tr.index 
                  { background: #70b0f0; color: #000000;  
                    text-align: left; font-size: 120%; } 
 
/* Headings */
h1.heading        { font-size: +140%; font-style: italic;
                    font-weight: bold; }
h2.heading        { font-size: +125%; font-style: italic;
                    font-weight: bold; }
h3.heading        { font-size: +110%; font-style: italic;
                    font-weight: normal; }
                    
/* Base tree */
pre.base-tree     { font-size: 80%; }

/* Details Sections */
table.func-details {  background: #e8f0f8; color: #000000;
                    border: 2px groove #c0d0d0;
                    padding: 0 1em 0 1em; margin: 0.4em 0 0 0; }
h3.func-detail    { background: transparent; color: #000000;
                    margin: 0 0 1em 0; }

table.var-details {  background: #e8f0f8; color: #000000;
                    border: 2px groove #c0d0d0;
                    padding: 0 1em 0 1em; margin: 0.4em 0 0 0; }
h3.var-details    { background: transparent; color: #000000;
                    margin: 0 0 1em 0; }

/* Function signatures */
.sig              { background: transparent; color: #000000;
                    font-weight: bold; }  
.sig-name         { background: transparent; color: #006080; }  
.sig-arg, .sig-kwarg, .sig-vararg
                  { background: transparent; color: #008060; }  
.sig-default      { background: transparent; color: #602000; }  
.summary-sig      { background: transparent; color: #000000; }  
.summary-sig-name { background: transparent; font-weight: bold; }  
.summary-sig-arg, .summary-sig-kwarg, .summary-sig-vararg
                  { background: transparent; color: #008060; }  

/* Navigation bar */ 
table.navbar      { background: #a0c0ff; color: #000000;
                    border: 2px groove #c0d0d0; }
th.navbar         { background: #a0c0ff; color: #6090d0; font-size: 110% } 
th.navselect      { background: #70b0ff; color: #000000; font-size: 110% } 

/* Links */ 
a:link            { background: transparent; color: #0000ff; }  
a:visited         { background: transparent; color: #204080; }  
a.navbar:link     { background: transparent; color: #0000ff; 
                    text-decoration: none; }  
a.navbar:visited  { background: transparent; color: #204080; 
                    text-decoration: none; }  
"""

# Black on steel blue.
_BLUE = """
/* Body color */ 
body              { background: #88a0a8; color: #000000; } 
 
/* Tables */ 
table.summary, table.details, table.index
                  { background: #a8c0c8; color: #000000; } 
tr.summary        { background: #c0e0e0; color: #000000;
                    text-align: left; font-size: 120%; } 
tr.details, tr.index
                  { background: #c0e0e0; color: #000000;
                    text-align: center; font-size: 120%; }

/* Headings */
h1.heading        { font-size: +140%; font-style: italic;
                    font-weight: bold; color: #002040; }
h2.heading        { font-size: +125%; font-style: italic;
                    font-weight: bold; color: #002040; }
h3.heading        { font-size: +110%; font-style: italic;
                    font-weight: normal; color: #002040; }

/* Base tree */
pre.base-tree     { font-size: 80%; }

/* Details Sections */
table.func-details { background: #a8c0c8; color: #000000;
                    border: 2px groove #c0d0d0;
                    padding: 0 1em 0 1em; margin: 0.4em 0 0 0; }
h3.func-detail    { background: transparent; color: #000000;
                    margin: 0 0 1em 0; }

table.var-details { background: #a8c0c8; color: #000000;
                    border: 2px groove #c0d0d0;
                    padding: 0 1em 0 1em; margin: 0.4em 0 0 0; }
h3.var-details    { background: transparent; color: #000000;
                    margin: 0 0 1em 0; }

/* Function signatures */
.sig              { background: transparent; color: #000000;
                    font-weight: bold; }  
.sig-name         { background: transparent; color: #006080; }  
.sig-arg, .sig-kwarg, .sig-vararg
                  { background: transparent; color: #008060; }  
.sig-default      { background: transparent; color: #602000; }  
.summary-sig      { background: transparent; color: #000000; }  
.summary-sig-name { background: transparent; font-weight: bold; }  
.summary-sig-arg, .summary-sig-kwarg, .summary-sig-vararg
                  { background: transparent; color: #008060; }  
 
/* Navigation bar */ 
table.navbar      { background: #607880; color: #b8d0d0;
                    border: 2px groove #c0d0d0; }
th.navbar         { background: #607880; color: #88a0a8;
                    font-weight: normal; } 
th.navselect      { background: #88a0a8; color: #000000;
                    font-weight: normal; } 
 
/* Links */ 
a:link            { background: transparent; color: #104060; }  
a:visited         { background: transparent; color: #082840; }  
a.navbar:link     { background: transparent; color: #b8d0d0;
                    text-decoration: none; }  
a.navbar:visited  { background: transparent; color: #b8d0d0;
                    text-decoration: none; }
"""

############################################################
## Derived stylesheets
############################################################
# Use some simple manipulations to produce a wide variety of color
# schemes.  In particular, use th _COLOR_RE regular expression to
# search for colors, and to transform them in various ways.

_COLOR_RE = re.compile(r'#(..)(..)(..)')

def _rv(match):
    """
    Given a regexp match for a color, return the reverse-video version
    of that color.

    @param match: A regular expression match.
    @type match: C{Match}
    @return: The reverse-video color.
    @rtype: C{string}
    """
    str = '#'
    for color in match.groups():
        str += '%02x' % (255-int(color, 16))
    return str

# Black-on-green
_GREEN = _COLOR_RE.sub(r'#\1\3\2', _BLUE)

# White-on-black, with blue highlights.
_BLACK = _COLOR_RE.sub(r'#\3\2\1', _COLOR_RE.sub(_rv, _WHITE))

# Grayscale
_GRAYSCALE = _COLOR_RE.sub(r'#\2\2\2', _WHITE)

############################################################
## Stylesheet table
############################################################

STYLESHEETS = {
    'white': (_WHITE, "Black on white, with blue highlights"),
    'blue': (_BLUE, "Black on steel blue"),
    'green': (_GREEN, "Black on green"),
    'black': (_BLACK, "White on black, with blue highlights"),
    'grayscale': (_GRAYSCALE, "Grayscale black on white"),
    'default': (_WHITE, "Default stylesheet (=white)"),
    'empty': ('', "An empty stylesheet"),
    'none': ('', "An empty stylesheet (=empty)"),
    }
