#
# objdoc: epydoc HTML output generator
# Edward Loper
#
# Created [01/30/01 05:18 PM]
# $Id$
#

"""
Documentation=>HTML converter.

This now uses CSS files.  If you want to use your own CSS file, just
overwrite the one produced by epydoc.
"""

# Improvements I'd like to make:
#    - Better CSS support
#    - List exceptions separately from other classes
#    - 


##################################################
## Constants
##################################################

WARN_MISSING = 0

CSS_FILE1 = """
/* Body color */ 
body              { background: #ffffff; color: #000000; } 
 
/* Tables */ 
table.summary, table.details, table.index
                  { background: #e8f0f8; color: #000000; } 
tr.summary, tr.details, tr.index 
                  { background: #70b0f0; color: #000000;  
                    text-align: left; font-size: 120%; } 
 
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
.sig              { background: transparent; color: #000000; }  
.sig-name         { background: transparent; color: #006080; }  
.sig-arg, .sig-kwarg, .sig-vararg
                  { background: transparent; color: #008060; }  
.sig-default      { background: transparent; color: #602000; }  

/* Links */ 
a:link            { background: transparent; color: #0000ff; }  
a:visited         { background: transparent; color: #204080; }  
a.navbar:link     { background: transparent; color: #0000ff; 
                    text-decoration: none; }  
a.navbar:visited  { background: transparent; color: #204080; 
                    text-decoration: none; }  

/* Navigation bar */ 
table.navbar      { background: #a0c0ff; color: #000000;
                    border: 2px groove #c0d0d0; }
th.navbar         { background: #a0c0ff; color: #6090d0; font-size: 110% } 
th.navselect      { background: #70b0ff; color: #000000; font-size: 110% } 

"""

# An alternate CSS file.
CSS_FILE2 = """
/* Body color */ 
body              { background: #88a0a8; color: #000000; } 
 
/* Tables */ 
table.summary, table.details, table.index
                  { background: #a8c0c8; color: #000000; } 
tr.summary        { background: #c0e0e0; color: #000000;
                    text-align: left; font-size: 120%; } 
tr.details, tr.index
                  { background: #d0f0f0; color: #000000;
                    text-align: center; font-size: 120%; }

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
.sig              { background: transparent; color: #000000; }  
.sig-name         { background: transparent; color: #006080; }  
.sig-arg          { background: transparent; color: #008060; }  
.sig-default      { background: transparent; color: #602000; }  
.sig-kwarg        { background: transparent; color: #008060; }  
.sig-vararg       { background: transparent; color: #008060; }  
 
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

CSS_FILE = CSS_FILE1

HELP = """
    <h2> Help </h2>

    <p> (No help available) </p>
"""

# Expects: (name, css)
HEADER = '''
<?xml version="1.0" encoding="iso-8859-1"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
          "DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
  <head>
    <title> %s</title>
    <link rel="stylesheet" href="%s" type="text/css"></link>
  </head>
  <body bgcolor="white" text="black" link="blue" vlink="#204080"
        alink="#204080">
'''
# Expects: date
FOOTER = '''
<table border="0" cellpadding="0" cellspacing="0" width="100%%">
  <tr>
    <td align="left"><font size="-2">Generated by Epydoc on %s</font></td>
    <td align="right"><a href="http://epydoc.sf.net"
                      ><font size="-2">http://epydoc.sf.net</font></a></td>
  </tr>
</table>
</body>
</html>'''

##################################################
## Imports
##################################################

import re, sys, os.path, string, time
from xml.dom.minidom import Text as _Text

import epydoc.epytext as epytext
from epydoc.uid import UID, Link
from epydoc.objdoc import Documentation, ModuleDoc, FuncDoc
from epydoc.objdoc import ClassDoc, Var, Raise, ObjDoc

##################################################
## Utility functions for conversion
##################################################

def _is_private(str):
    str = string.split(str, '.')[-1]
    return (str and str[0]=='_' and str[-1]!='_')

def _cmp_name(uid1, uid2):
    """
    Order by names.
    __init__ < anything.
    public < private.
    otherwise, sorted alphabetically by name.
    """
    x = uid1.name()
    y = uid2.name()
    if (y == '__init__'): return 1
    if (x == '__init__'): return -1
    if x == y: return 0
    if _is_private(x) and not _is_private(y): return 1
    if _is_private(y) and not _is_private(x): return -1
    return cmp(x, y)

##################################################
## Documentation -> HTML Conversion
##################################################

class HTML_Doc:
    """
    Documentation=>HTML converter.

    For each module/package, create a file containing:
      - Navbar
      - Module Name
      - Description
      - See-also
      - Module list
      - Class summary
      - Function summary
      - Variable summary
      - Function details
      - Variable details
      - Navbar

    For each class, create a file containing:
      - Navbar
      - Module name
      - Class Name
      - Base tree
      - Known subclasses
      - Description
      - See-also
      - Method summary
      - Instance Variable summary
      - Class Variable summary
      - Method details
      - Instance Variable details
      - Class Variable details
      - Navbar

    Also, generate an index file, a help file, and a tree file.

    @cvar _SPECIAL_METHODS: A dictionary providing names for special
        methods, such as C{__init__} and C{__add__}.
    @type _SPECIAL_METHODS: C{dictionary} from C{string} to C{string}
    """
    
    def __init__(self, docmap, **kwargs):
        """
        Construct a new HTML outputter, using the given
        C{Documentation} object.
        
        @param docmap: The documentation to output.
        @type docmap: C{Documentation}
        """
        """
        @param pkg_name: The name of the package.  This is used in the 
            header.
        @type pkg_name: C{string}
        @param show_private: Whether to show private fields (fields
            starting with a single '_').
        @type show_private: C{boolean}
        """
        self._docmap = docmap
        self._show_private = kwargs.get('show_private', 0)
        self._pkg_name = kwargs.get('pkg_name', '')
        self._css = kwargs.get('css', CSS_FILE)
        self._cssfile = kwargs.get('cssfile', 'epydoc.css')
        self._pkg_url = kwargs.get('pkg_url', None)
        self._find_toplevel()

    def _find_toplevel(self):
        """
        Try to find a unique module/package for this set of docs.
        This is used by the navbar.
        """
        modules = []
        packages = []
        for (uid, doc) in self._docmap.items():
            if not isinstance(doc, ModuleDoc): continue
            modules.append(uid)
            if doc.ispackage():
                packages.append(uid)

        # Is there a unique module?
        if len(modules) == 0: self._module = None
        elif len(modules) == 1: self._module = modules[0]
        else: self._module = 'multiple'

        # Is there a unique (top-level) package?
        if len(packages) == 0: self._package = None
        else:
            self._package = 'multiple'
            for pkg in packages:
                toplevel = 1
                for p2 in packages:
                    if pkg != p2 and not p2.descendant_of(pkg):
                        toplevel = 0
                if toplevel:
                    self._package = pkg

    def write(self, directory, verbose=1):
        """Write the documentation to the given directory."""
        if directory in ('', None): directory = './'
        if directory[-1] != '/': directory = directory + '/'
        
        self._show_both = 0
        
        str = self._tree_to_html()
        open(directory+'epydoc-tree.html', 'w').write(str)

        str = self._index_to_html()
        open(directory+'epydoc-index.html', 'w').write(str)

        # This is getting very hack-ish.  Oh well. :)
        self._show_private = 'both'        
        if self._show_private == 'both':
            self._show_both = 1
            self._show_private = 0
            self._write_docs(directory, verbose)
            self._show_private = 1
            self._cssfile = '../'+self._cssfile
            self._write_docs(os.path.join(directory, 'private'), verbose)
        else:
            self._write_docs(directory, verbose)

        self._show_private = 0
        self._write_css(directory)
        self._write_help(directory)
        
    def _write_docs(self, directory, verbose):
        if directory[-1] != '/': directory = directory + '/'
        # Create dest directory, if necessary
        if not os.path.isdir(directory):
            if os.path.exists(directory):
                raise ValueError('%r is not a directory' % directory)
            os.mkdir(directory)

        for (n, d) in self._docmap.items():
            if isinstance(d, ModuleDoc):
                if verbose==1:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                elif verbose>1: print 'Writing docs for module: ', n
                str = self._module_to_html(n)
                open(directory+`n`+'.html', 'w').write(str)
            elif isinstance(d, ClassDoc):
                if verbose==1:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                elif verbose>1: print 'Writing docs for class:  ', n
                str = self._class_to_html(n)
                open(directory+`n`+'.html', 'w').write(str)

    def _write_css(self, directory):
        cssfile = open(os.path.join(directory, 'epydoc.css'), 'w')
        cssfile.write(self._css)
        cssfile.close()

    def _write_help(self, directory):
        helpfile = open(os.path.join(directory, 'epydoc-help.html'), 'w')
        navbar = self._navbar('help')
        helpfile.write(self._header('Help')+navbar+HELP+navbar+self._footer())
        helpfile.close()
        
    ##--------------------------
    ## INTERNALS
    ##--------------------------

    _SPECIAL_METHODS = {'__init__': 'Constructor',
                        '__del__': 'Destructor',
                        '__add__': 'Addition operator',
                        '__sub__': 'Subtraction operator',
                        '__and__': 'And operator',
                        '__or__': 'Or operator',
                        '__repr__': 'Representation operator',
                        '__call__': 'Call operator',
                        '__getattr__': 'Qualification operator',
                        '__getitem__': 'Indexing operator',
                        '__setitem__': 'Index assignment operator',
                        '__delitem__': 'Index deletion operator',
                        '__delslice__': 'Slice deletion operator',
                        '__setslice__': 'Slice assignment operator',
                        '__getslice__': 'Slicling operator',
                        '__len__': 'Length operator',
                        '__cmp__': 'Comparison operator',
                        '__eq__': 'Equality operator',
                        '__in__': 'Containership operator',
                        '__gt__': 'Greater-than operator',
                        '__lt__': 'Less-than operator',
                        '__ge__': 'Greater-than-or-equals operator',
                        '__le__': 'Less-than-or-equals operator',
                        '__radd__': 'Right-side addition operator',
                        '__hash__': 'Hashing function',
                        '__contains__': 'In operator',
                        '__str__': 'Informal representation operator'
                        }

    def _sort(self, docs):
        """
        Sort a list of C{ObjDoc}s.
        """
        docs = list(docs)
        docs.sort(lambda x,y: _cmp_name(x, y))
        if not self._show_private:
            docs = filter(lambda x:not _is_private(x.name()), docs)
        return docs

    def _header(self, name):
        'Return an HTML header with the given name.'
        return HEADER % (name, self._cssfile)
               
    def _footer(self):
        'Return an HTML footer'
        return FOOTER % time.asctime(time.localtime(time.time()))
    
    def _seealso(self, seealso):
        'Convert a SEEALSO node to HTML'
        #!!!!!!!!!!!!!!!!!!!!!!!!!!!! NO SEEALSO YET
        return ''
        if not seealso: return ''
        str = '<dl><dt><b>See also:</b>\n  </dt><dd>'
        for see in seealso:
            if self._docmap.has_key(see[0]):
                str += self._uid_to_href(see[0], see[1]) + ', '
            else:
                str += see[1] + ', '
        return str[:-2] + '</dd>\n</dl>\n\n'

    def _summary(self, doc):
        'Convert an descr to an HTML summary'
        descr = doc.descr()

        # Try to find a documented ancestor.
        if isinstance(doc, FuncDoc):
            while (not doc.documented() and
                   doc.overrides() and
                   self._docmap.has_key(doc.overrides())):
                doc = self._docmap[doc.overrides()]

        if descr != None:
            str = epytext.to_html(epytext.summary(descr)).strip()
            if str == '': str = '&nbsp;'
            return str
        elif (isinstance(doc, FuncDoc) and
              doc.returns().descr() is not None):
            summary = epytext.summary(doc.returns().descr())
            return ('Return '+epytext.to_html(summary).strip())
        else:
            return '&nbsp;'

    def _href_target(self, uid):
        anchor = ''
        if uid.is_function():
            anchor = '#'+uid.shortname()
            uid = uid.module()
        if uid.is_method():
            anchor = '#'+uid.shortname()
            uid = uid.cls()
        return '%s.html%s' % (uid, anchor)

    def _link_to_href(self, link):
        return self._uid_to_href(link.target(), link.name())

    def _uid_to_href(self, uid, label=None):
        'Add an HREF to a uid, when appropriate.'
        if label==None: label = `uid`
        if self._docmap.has_key(uid):
            str = ('<a href="' + self._href_target(uid) +
                   '">' + label + '</a>')
            if not isinstance(self._docmap[uid], ModuleDoc):
                str = '<code>'+str+'</code>'
        else:
            str = label
        return str

    def _descr(self, descr):
        ## PHASE THIS OUT EVENTUALLY???
        'Convert a description Node to HTML'
        if descr == None: return ''
        str = epytext.to_html(descr)
        open = '<b><i><center><font size='
        close = '</font></center></i></b>'
        str = re.sub('<h1>', open+'"+2">', str)
        str = re.sub('<h2>', open+'"+1">', str)
        str = re.sub('<h3>', open+'"+0">', str)
        str = re.sub('</h\d>', close, str)
        return str

    def _find_tree_width(self, uid):
        width = 2
        if self._docmap.has_key(uid):
            for base in self._docmap[uid].bases():
                width = max(width, len(base.name())+4)
                width = max(width, self._find_tree_width(base.target())+4)

        return width
        
    def _base_tree(self, uid, width=None, postfix=''):
        """
        Return an HTML picture showing a class's base tree,
        with multiple inheritance.

        Draw a right-justified picture..
        """
        if not self._docmap.has_key(uid): return ''
        if width == None:
            width = self._find_tree_width(uid)
        
        bases = self._docmap[uid].bases()
        
        if postfix == '':
            str = ' '*(width-2) + '<b>'+`uid`+'</b>\n'
        else: str = ''
        for i in range(len(bases)-1, -1, -1):
            base = bases[i]
            str = (' '*(width-4-len(base.name())) +
                   self._link_to_href(base)+' --+'+postfix+'\n' + 
                   ' '*(width-4) +
                   '   |'+postfix+'\n' +
                   str)
            (t,w) = (base.target(), width)
            if i != 0:
                str = (self._base_tree(t, w-4, '   |'+postfix)+str)
            else:
                str = (self._base_tree(t, w-4, '    '+postfix)+str)
        ss = re.sub('<[^<>]+>','',str)
        return str
                
    def _base_tree_old(self, uid, prefix='  '):
        """
        Return an HTML picture showing a class's base tree,
        with multiple inheritance.
        """
        if not self._docmap.has_key(uid): return ''
        
        bases = self._docmap[uid].bases()
        if prefix == '  ': str = '  +-- <b>'+`uid`+'</b>\n'
        else: str = ''
        for i in range(len(bases)):
            base = bases[i]
            str = (prefix + '+--' + self._link_to_href(base) + '\n' +
                   prefix + '|  \n' + str)
            if i < (len(bases)-1):
                str = self._base_tree_old(base.target(), prefix+'|  ') + str
            else:
                str = self._base_tree_old(base.target(), prefix+'   ') + str
        return str

    def _class_tree_item(self, uid=None, depth=0):
        if uid is not None:
            doc = self._docmap.get(uid, None)
            str = ' '*depth + '<li> <b>' + self._uid_to_href(uid)+'</b>'
            if doc and doc.descr():
                str += ': <i>' + self._summary(doc) + '</i>'
            str += '\n'
            if doc and doc.children():
                str += ' '*depth + '  <ul>\n'
                children = [l.target() for l in doc.children()]
                children.sort()
                for child in children:
                    str += self._class_tree_item(child, depth+4)
                str += ' '*depth + '  </ul>\n'
        return str

    def _class_tree(self):
        str = '<ul>\n'
        docs = self._docmap.items()
        docs.sort()
        for (uid, doc) in docs:
            if not isinstance(doc, ClassDoc): continue
            hasbase = 0
            for base in doc.bases():
                if self._docmap.has_key(base.target()):
                    hasbase = 1
            if not hasbase:
                str += self._class_tree_item(uid)
        return str +'</ul>\n'

    def _module_tree_item(self, uid=None, depth=0):
        if uid is None: return ''

        doc = self._docmap.get(uid, None)
        name = `uid`.split('.')[-1]
        str = ' '*depth + '<li> <b>'
        str += self._uid_to_href(uid, name)+'</b>'
        if doc and doc.descr():
            str += ': <i>' + self._summary(doc) + '</i>'
        str += '\n'
        if doc and doc.ispackage() and doc.modules():
            str += ' '*depth + '  <ul>\n'
            modules = [l.target() for l in doc.modules()]
            modules.sort()
            for module in modules:
                str += self._module_tree_item(module, depth+4)
            str += ' '*depth + '  </ul>\n'
        str += ' '*depth+'</li>'
        return str

    def _module_tree(self):
        str = '<ul>\n'
        docs = self._docmap.items()
        docs.sort()
        # Find all top-level packages. (what about top-level
        # modules?)
        for (uid, doc) in docs:
            if not isinstance(doc, ModuleDoc): continue
            if not doc.package():
                str += self._module_tree_item(uid)
        return str +'</ul>\n'

    def _start_of(self, heading):
        return '\n<!-- =========== START OF '+string.upper(heading)+\
               ' =========== -->\n'
    
    def _table_header(self, heading, css_class):
        'Return a header for an HTML table'
        return self._start_of(heading)+\
               '<table class="'+css_class+'" border="1" cellpadding="3"' +\
               ' cellspacing="0" width="100%" bgcolor="white">\n' +\
               '<tr bgcolor="#70b0f0" class="'+css_class+'">\n'+\
               '<th colspan="2">\n' + heading +\
               '</th></tr>\n'
    
    def _class_summary(self, classes, heading='Class Summary'):
        'Return a summary of the classes in a module'
        classes = self._sort(classes)
        if len(classes) == 0: return ''
        str = self._table_header(heading, 'summary')

        for link in classes:
            cname = link.name()
            cls = link.target()
            if not self._docmap.has_key(cls): continue
            cdoc = self._docmap[cls]
            csum = self._summary(cdoc)
            str += '<tr><td width="15%">\n'
            str += '  <b><i>'+self._link_to_href(link)
            str += '</i></b></td>\n  <td>' + csum + '</td></tr>\n'
        return str + '</table><br>\n\n'

    def _func_signature(self, fname, fdoc, cssclass="sig"):
        """
        Return HTML for a signature of the given function
        """
        str = '<b><code class=%s>' % cssclass
        str += '<span class=%s-name>%s</span>(' % (cssclass, fname)
        
        for param in fdoc.parameters():
            str += '<span class=%s-arg>%s</span>' % (cssclass, param.name())
            if param.default():
                default = param.default()
                if len(default) > 60:
                    default = default[:57]+'...'
                str += '=<span class=%s-default>%s</span>' % (cssclass,
                                                              default)
            str += ', '
        if fdoc.vararg():
            str += '<span class=%s-vararg>*%s</span>, ' % (cssclass,
                                                   fdoc.vararg().name())
        if fdoc.kwarg():
            str += '<span class=%s-kwarg>**%s</span>, ' % (cssclass,
                                                   fdoc.kwarg().name())
        if str[-1] != '(': str = str[:-2]

        return str + ')</code></b>'

    def _func_details(self, functions, cls,
                      heading='Function Details'):
        """Return a detailed description of the functions in a
        class or module."""
        functions = self._sort(functions)
        if len(functions) == 0: return ''
        str = self._table_header(heading, 'details')+'</table>'

        for link in functions:
            str += ('<table width="100%" class="func-details"'+
                    ' bgcolor="#e0e0e0">'+
                    '<tr><td>\n')
            fname = link.name()
            func = link.target()
            if not self._docmap.has_key(func):
                if WARN_MISSING:
                    print 'WARNING: MISSING', func
                continue
            
            fdoc = self._docmap[func]

            str += '<a name="'+fname+'"></a>\n'
            if HTML_Doc._SPECIAL_METHODS.has_key(fname):
                str += '<h3 class="func-details"><i>'
                str += HTML_Doc._SPECIAL_METHODS[fname]+'</i></h3>\n'
            else:
                str += '<h3 class="func-details">'+fname+'</h3>\n'

            str += self._func_signature(fname, fdoc)

            foverrides = fdoc.overrides()

            # Try to find a documented ancestor.
            inheritdoc = 0
            while (not fdoc.documented() and
                   fdoc.overrides() and
                   self._docmap.has_key(fdoc.overrides())):
                fdoc = self._docmap[fdoc.overrides()]
                inheritdoc = 1
                
            fdescr=fdoc.descr()
            fparam = fdoc.parameters()[:]
            if fdoc.vararg(): fparam.append(fdoc.vararg())
            if fdoc.kwarg(): fparam.append(fdoc.kwarg())
            freturn = fdoc.returns()
            fraises = fdoc.raises()
            
            # Don't list parameters that don't have any extra info.
            f = lambda p:p.descr() or p.type()
            fparam = filter(f, fparam)

            # Description
            if fdescr:
                str += '  <dd>'+epytext.to_html(fdescr, para=1)+'</dd>\n'
            str += '  <dt></dt><dd>\n'

            # Parameters
            if fparam:
                str += '    <dl><dt><b>Parameters:</b></dt>\n'
                for param in fparam:
                    pname = param.name()
                    str += '      <dd><code><b>' + pname +'</b></code>'
                    if param.descr():
                        str += ' - ' + epytext.to_html(param.descr())
                    if param.type():
                        str += ' <br>\n        <i>'+('&nbsp;'*10)
                        str += '(type=' + epytext.to_html(param.type()) 
                        str += ')</i>'
                    str += '</dd>\n'
                str += '    </dl>\n'

            # Returns
            if freturn.descr() or freturn.type():
                str += '    <dl><dt><b>Returns:</b></dt>\n      <dd>'
                if freturn.descr():
                    str += epytext.to_html(freturn.descr())
                    if freturn.type():
                        str += ' <br>' + '<i>'+('&nbsp;'*10)
                        str += '(type=' 
                        str += epytext.to_html(freturn.type()) 
                        str += ')</i>'
                elif freturn.type():
                    str += epytext.to_html(freturn.type())
                str += '</dd>\n    </dl>\n'

            # Raises
            if fraises:
                str += '    <dl><dt><b>Raises:</b></dt>\n'
                for fraise in fraises:
                    str += '      '
                    str += '<dd><code><b>'+fraise.name()+'</b></code> - '
                    str += epytext.to_html(fraise.descr())+'</dd>\n'
                str += '    </dl>\n'

            # Overrides
            if foverrides:
                cls = foverrides.cls()
                str += '    <dl><dt><b>Overrides:</b></dt>\n'
                if self._docmap.has_key(cls):
                    str += ('      <dd><code><a href="' +
                            self._href_target(cls) + '#' +
                            foverrides.shortname() +
                            '">' + `foverrides` + '</a></code>')
                else:
                    str += '      <dd><code>'+`func`+'</code>'
                if inheritdoc:
                    str += ' <i>(inherited documentation)</i>\n'
                str += '</dd>\n    </dl>\n'
                
            str += '  </dd>\n</dl>\n\n'
            str += '</td></tr></table>\n'

        str += '<br>\n'
        return str

    def _var_details(self, variables, heading='Variable Details'):
        """Return a detailed description of the variables in a
        class or module."""
        variables = self._sort(variables)
        if len(variables) == 0: return ''
        str = self._table_header(heading, 'details')+'</table>'

        numvars = 0
        for var in variables:
            # Don't bother if we don't know anything about it.
            if not (var.descr() or var.type()): continue
            numvars += 1
            
            str += ('<table width="100%" class="var-details"'+
                    ' bgcolor="#e0e0e0">'+
                    '<tr><td>\n')
            
            vname = var.name()

            str += '<a name="'+vname+'"></a>\n'
            str += '<h3>'+vname+'</h3>\n'
            str += '<dl>\n'

            if var.descr():
                str += '  <dd>'
                str += epytext.to_html(var.descr())+'<br>\n'
                
            if var.type():
                str += '  <dl><dt><b>Type:</b>\n' 
                str += '<code>'+epytext.to_html(var.type())
                str += '</code>'+'</dt></dl>\n'

            #if var.overrides():
            #    str += '  <dl><dt><b>Overrides:</b></dt>\n'
            #    for target in var.overrides():
            #        str += '    <dd>' +\
                  #        self._link_to_href(target.data[0]) + '\n'
            #    str += '  </dl>\n'
            
            str += '</dd></dl></td></tr></table>\n'

        # If we didn't get any variables, don't print anything.
        if numvars == 0: return ''
        return str+'<br>'

    def _func_summary(self, functions, heading='Function Summary'):
        'Return a summary of the functions in a class or module'
        functions = self._sort(functions)
        if len(functions) == 0: return ''
        str = self._table_header(heading, 'summary')
        
        for link in functions:
            func = link.target()
            fname = link.name()
            if not self._docmap.has_key(func):
                if WARN_MISSING:
                    print 'WARNING: MISSING', func
                continue
            
            fdoc = self._docmap[func]
            
            # Try to find a documented ancestor.
            inheritdoc = 0
            while (not fdoc.documented() and
                   fdoc.overrides() and
                   self._docmap.has_key(fdoc.overrides())):
                fdoc = self._docmap[fdoc.overrides()]
                inheritdoc = 1
                
            rval = fdoc.returns()
            if rval.type():
                rtype = epytext.to_html(rval.type())
            else: rtype = '&nbsp;'

            pstr = '('
            for param in fdoc.parameters():
                pstr += param.name()+', '
            if fdoc.vararg():
                pstr += '*'+fdoc.vararg().name()+', '
            if fdoc.kwarg():
                pstr += '**'+fdoc.kwarg().name()+', '
            if pstr == '(': pstr = '()'
            else: pstr = pstr[:-2]+')'

            descrstr = self._summary(fdoc)
            if descrstr != '&nbsp;':
                fsum = '<br>'+descrstr
            else: fsum = ''
            str += '<tr><td align="right" valign="top" '
            str += 'width="15%"><font size="-1">'
            str += rtype+'</font></td>\n'
            str += '  <td><code><b><a href="#'+fname+'">'
            str += fname+'</a>'
            str += '</b>'+pstr+'</code>\n  '
            str += fsum+'</td></tr>\n'
        return str + '</table><br>\n\n'
    
    def _var_summary(self, variables, heading='Variable Summary'):
        'Return a summary of the variables in a class or module'
        variables = self._sort(variables)
        if len(variables) == 0: return ''
        str = self._table_header(heading, 'summary')

        for var in variables:
            vname = var.name()
            if var.type(): vtype = epytext.to_html(var.type())
            else: vtype = '&nbsp;'
            if var.descr():
                vsum = '<br>'+self._summary(var)
            else: vsum = ''
            str += '<tr><td align="right" valign="top" '
            str += 'width="15%"><font size="-1">'+vtype+'</font></td>\n'
            str += '  <td><code><b><a href="#'+vname+'">'+vname
            str += '</a>'+'</b></code>\n  ' + vsum+'</td></tr>\n'
        return str + '</table><br>\n\n'

    def _module_list(self, modules):
        if len(modules) == 0: return ''
        str = '<h3>Modules</h3>\n<ul>\n'
        modules.sort(lambda l1,l2:cmp(l1.target(),l2.target()))
        for link in modules:
            str += self._module_tree_item(link.target())
        return str + '</ul>\n'

    def _navbar(self, where, uid=None):
        """
        @param where: What page the navbar is being displayed on..
        """
        str = self._start_of('Navbar')
        str += '<table class="navbar" border="0" width="100%"'
        str += ' cellpadding="0" bgcolor="#a0c0ff" cellspacing="0">\n'
        str += '  <tr>\n'
        str += '    <td width="100%">\n'
        str += '      <table border="0" cellpadding="0" cellspacing="0">\n'
        str += '        <tr valign="top">\n'

        I = '          ' # indentation
        # Go to Package
        if self._package is None: pass
        elif where in ('class', 'module'):
            pkg = uid.package()
            if pkg is not None:
                str += I+'<th class="navbar">&nbsp;&nbsp;&nbsp;'
                str += '<a class="navbar" href="'+`pkg`+'.html">'
                str += 'Package</a>&nbsp;&nbsp;&nbsp;</th>\n'
            else:
                str += I+'<th class="navbar">&nbsp;&nbsp;&nbsp;'
                str += 'Package&nbsp;&nbsp;&nbsp;</th>\n'
        elif where=='package':
            str += I+'<th bgcolor="#70b0f0" class="navselect">'
            str += '&nbsp;&nbsp;&nbsp;'
            str += 'Package&nbsp;&nbsp;&nbsp;</th>\n'
        elif isinstance(self._package, UID):
            str += I+'<th class="navbar">&nbsp;&nbsp;&nbsp;'
            str += '<a class="navbar" href="'+`self._package`+'.html">'
            str += 'Package</a>&nbsp;&nbsp;&nbsp;</th>\n'
        elif 'multiple' == self._package:
            str += I+'<th class="navbar">&nbsp;&nbsp;&nbsp;'
            str += 'Package&nbsp;&nbsp;&nbsp;</th></b>\n'
        
        # Go to Module
        if self._module is None: pass
        elif where=='class':
            str += I+'<th class="navbar">&nbsp;&nbsp;&nbsp;'
            str += '<a class="navbar" href="'+`uid.module()`+'.html">'
            str += 'Module</a>&nbsp;&nbsp;&nbsp;</th>\n'
        elif where=='module':
            str += I+'<th bgcolor="#70b0f0" class="navselect">&nbsp;' 
            str += '&nbsp;&nbsp;Module&nbsp;&nbsp;&nbsp;</th>\n'
        elif isinstance(self._module, UID):
            str += I+'<th class="navbar">&nbsp;&nbsp;&nbsp;'
            str += '<a class="navbar" href="'+`self._module`+'.html">'
            str += 'Module</a>&nbsp;&nbsp;&nbsp;</th>\n'
        elif 'multiple' == self._module:
            str += I+'<th class="navbar">&nbsp;&nbsp;&nbsp;'
            str += 'Module&nbsp;&nbsp;&nbsp;</th>\n'
        
        # Go to Class
        if where == 'class':
            str += I+'<th bgcolor="#70b0f0" class="navselect">&nbsp;'
            str += '&nbsp;&nbsp;Class&nbsp;&nbsp;&nbsp;</th>\n'
        else:
            str += I+'<th class="navbar">&nbsp;&nbsp;&nbsp;Class' 
            str += '&nbsp;&nbsp;&nbsp;</th>\n'

        # Go to Tree
        if where == 'tree':
            str += I+'<th bgcolor="#70b0f0" class="navselect">&nbsp;'
            str += '&nbsp;&nbsp;Trees&nbsp;&nbsp;&nbsp;</th>\n'
        else:
            str += I+'<th class="navbar">&nbsp;&nbsp;&nbsp;'
            str += '<a class="navbar" href="'
            if self._show_both and self._show_private: str += '../'
            str += 'epydoc-tree.html">Trees</a>'
            str += '&nbsp;&nbsp;&nbsp;</th>\n'

        # Go to Index
        if where == 'index':
            str += I+'<th bgcolor="#70b0f0" class="navselect">&nbsp;'
            str += '&nbsp;&nbsp;Index&nbsp;&nbsp;&nbsp;</th>\n'
        else:
            str += I+'<th class="navbar">&nbsp;&nbsp;&nbsp;'
            str += '<a class="navbar" href="'
            if self._show_both and self._show_private: str += '../'
            str += 'epydoc-index.html">Index</a>'
            str += '&nbsp;&nbsp;&nbsp;</th>\n'

        # Go to Help
        if where == 'help':
            str += I+'<th bgcolor="#70b0f0" class="navselect">&nbsp;'
            str += '&nbsp;&nbsp;Help&nbsp;&nbsp;&nbsp;</th>\n'
        else:
            str += I+'<th class="navbar">&nbsp;&nbsp;&nbsp;'
            str += '<a class="navbar" href="'
            if self._show_both and self._show_private: str += '../'
            str += 'epydoc-help.html">Help</a>'
            str += '&nbsp;&nbsp;&nbsp;</th>\n'

        str += '        </tr>\n      </table>\n    </td>\n'
        str += '    <td>\n'
        str += '      <table border="0" cellpadding="0" cellspacing="0">\n'
        str += '        <tr valign="top">\n'
        str += '          <th class="navbar">'
        if self._pkg_name:
            if self._pkg_url:
                str += ('<a class="navbar" href="%s">%s</a>' %
                          (self._pkg_url, self._pkg_name))
            else:
                str += I+self._pkg_name

        str += '</th>\n        </tr>\n'
        str += '      </table>\n    </td>\n  </tr>\n</table>\n'
        return str

    def _public_private_link(self, uid):
        """
        Create a link between the public & private copies of the
        documentation.
        """
        if self._show_private and _is_private(uid.name()):
            return ''

        str = '<table width="100%"><tr>\n  <td width="100%"></td>\n'
        if self._show_private:
            str += '  <td><font size="-2">[show&nbsp;private&nbsp;|'
            str += '&nbsp;<a href="../' + self._href_target(uid)
            str += '">hide&nbsp;private</a>]</font></td>\n'
        else:
            str += '  <td><font size="-2">[<a href="private/'
            str += self._href_target(uid) + '">show&nbsp;private</a>'
            str += '&nbsp;|&nbsp;hide&nbsp;private]</font></td>\n'
        return str + '</tr></table>\n'
    
    def _split_classes_and_excepts(self, doc):
        """
        Divide classes into exceptions & other classes
        """
        classes = []
        excepts = []
        for link in doc.classes():
            try:
                if (self._docmap.has_key(link.target()) and
                    self._docmap[link.target()].is_exception()):
                    excepts.append(link)
                else:
                    classes.append(link)
            except:
                classes.append(link)
        return (classes, excepts)
        
    def _module_to_html(self, uid):
        'Return an HTML page for a Module'
        doc = self._docmap[uid]
        descr = doc.descr()
        if uid.is_package(): moduletype = 'package'
        else: moduletype = 'module'
        
        str = self._header(`uid`)
        str += self._navbar(moduletype, uid)
        if self._show_both:
            str += self._public_private_link(uid)

        if moduletype == 'package':
            str += self._start_of('Package Description')
            str += '<h2>Package '+uid.name()+'</h2>\n\n'
        else:
            str += self._start_of('Module Description')
            str += '<h2>Module '+uid.name()+'</h2>\n\n'

        if descr:
            str += self._descr(descr) + '<hr/>\n'
        if doc.seealsos():
            str += self._seealso(doc.seealsos())

        if doc.ispackage():
            str += self._module_list(doc.modules())

        (classes,excepts) = self._split_classes_and_excepts(doc)
        str += self._class_summary(classes, 'Classes')
        str += self._class_summary(excepts, 'Exceptions')
        str += self._func_summary(doc.functions())
        str += self._var_summary(doc.variables())

        str += self._func_details(doc.functions(), None)
        str += self._var_details(doc.variables())
        
        str += self._navbar(moduletype, uid)
        return str + self._footer()

    def _class_to_html(self, uid):
        'Return an HTML page for a Class'
        doc = self._docmap[uid]
        modname = doc.uid().module().name()
        descr = doc.descr()
        
        # Name & summary
        str = self._header(`uid`)
        str += self._navbar('class', uid)
        if self._show_both:
            str += self._public_private_link(uid)
        str += self._start_of('Class Description')
        
        str += '<h2><font size="-1">\n'+modname+'</font><br>\n' 
        str += 'Class ' + `uid`+'</h2>\n\n'
        if doc.bases():
            str += '<pre class="base-tree">\n' 
            str += self._base_tree(uid) 
            str += '</pre><br>\n\n'
        children = doc.children()
        if children:
            str += '<dl><dt><b>Known Subclasses:</b></dt>\n<dd>'
            for cls in children:
                str += '    '+self._link_to_href(cls) + ',\n'
            str = str[:-2] + '</dd></dl>\n\n'
        if descr:
            str += '<hr/>\n' + self._descr(descr) 
            str += '\n\n'
        str += '<hr/>\n\n'

        str += self._seealso(doc.seealsos())

        str += self._func_summary(doc.methods(),
                                  'Method Summary')
        str += self._var_summary(doc.ivariables(),
                                 'Instance Variable Summary')
        str += self._var_summary(doc.cvariables(),
                                 'Class Variable Summary')
        
        str += self._func_details(doc.methods(), doc, 
                                  'Method Details')
        str += self._var_details(doc.ivariables(), 
                                 'Instance Variable Details')
        str += self._var_details(doc.cvariables(), 
                                 'Class Variable Details')
        
        str += self._navbar('class', uid)
        return str + self._footer()

    def _tree_to_html(self):
        str = self._header('Class Hierarchy')
        str += self._navbar('tree') 
        str += self._start_of('Class Hierarchy')
        str += '<h2>Module Hierarchy</h2>\n'
        str += self._module_tree()
        str += '<h2>Class Hierarchy</h2>\n'
        str += self._class_tree()
        str += self._navbar('tree')
        str += self._footer()
        return str

    def get_index_items(self, tree, base, dict=None):
        if dict == None: dict = {}
    
        if isinstance(tree, _Text): return dict
        elif tree.tagName != 'index':
            for child in tree.childNodes:
                self.get_index_items(child, base, dict)
        else:
            children = [epytext.to_html(c) for c in tree.childNodes]
            key = ''.join(children).lower().strip()
            if dict.has_key(key):
                dict[key].append(base)
            else:
                dict[key] = [base]
        return dict

    def _extract_index(self):
        """
        @return: A dictionary mapping from terms to lists of source
            documents. 
        """
        index = {}
        for (uid, doc) in self._docmap.items():
            if uid.is_function(): uid = uid.module()
            if uid.is_method(): uid = uid.cls()
            base = `uid`
            descr = doc.descr()
            if descr:
                self.get_index_items(descr, base, index)
        return index

    def _index_to_html(self):
        str = self._header('Index')
        str += self._navbar('index') + '<br>\n'
        str += self._start_of('Index')

        str += self._table_header('Index', 'index')
        index = self._extract_index().items()
        index.sort()
        for (term, sources) in index:
            str += '  <tr><td width="10%">'+term+'</td>\n    <td>'
            sources.sort()
            for source in sources:
                target = source+'.html#'+epytext.index_to_anchor(term)
                str += '<i><a href="' + target + '">'
                str += source + '</a></i>, '
            str = str[:-2] + '</tr></td>\n'
        str += '</table>\n' +  '<br>\n'
        
        str += self._navbar('index')
        str += self._footer()
        return str
