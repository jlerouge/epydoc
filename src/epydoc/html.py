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

##################################################
## Constants
##################################################

WARN_MISSING = 0

CSS_FILE1 = """
/* Body color */ 
body              { background: #ffffff; color: #000000; } 
 
/* Tables */ 
table             { background: #ffffff; color: #000000; } 
tr.summary, tr.details, tr.index 
                  { background: #70b0f0; color: #000000;  
                    text-align: left; font-size: 120%; } 
 
/* Navigation bar */ 
table.navbar      { background: #a0c0ff; color: #000000;
                    border: 2px groove #c0d0d0; }
th.navbar         { background: #a0c0ff; color: #000000; font-size: 110%; } 
th.navselect      { background: #70b0ff; color: #000000; font-size: 110%; } 
 
/* Links */ 
a:link            { background: transparent; color: #0000ff; }  
a:visited         { background: transparent; color: #204080; }  
a.navbar:link     { background: transparent; color: #0000ff; }  
a.navbar:visited  { background: transparent; color: #204080; }  
"""

# An alternate CSS file.
CSS_FILE2 = """
/* Body color */ 
body              { background: #8098a0; color: #000000; } 
 
/* Tables */ 
table             { background: #ffffff; color: #000000; } 
tr.summary        { background: #c0d0d0; color: #000000;
                    text-align: left; font-size: 120%; } 
tr.details        { background: #c0d0d0; color: #000000;
                    text-align: center; font-size: 120%; }
tr.index          { background: #c0d0d0; color: #000000;
                    text-align: center; font-size: 120%; } 
 
/* Navigation bar */ 
table.navbar      { background: #607880; color: #b8d0d0;
                    border: 2px groove #c0d0d0; }
th.navbar         { background: #607880; color: #8098a0;
                    font-weight: normal; } 
th.navselect      { background: #8098a0; color: #000000;
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

# Expects (navbar, navbar):
HELP = """
    <H2> Help </H2>

    <p> (No help available) </p>
"""

##################################################
## Imports
##################################################

import re, sys, os.path, string
from xml.dom.minidom import Text as _Text
from types import ModuleType as _ModuleType
from types import ClassType as _ClassType
from types import FunctionType as _FunctionType
from types import BuiltinFunctionType as _BuiltinFunctionType
from types import BuiltinMethodType as _BuiltinMethodType
from types import MethodType as _MethodType
from types import StringType as _StringType

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
        """## Write the documentation to the given directory."""
        if directory in ('', None): directory = './'
        if directory[-1] != '/': directory = directory + '/'

        str = self._tree_to_html()
        open(directory+'tree.html', 'w').write(str)

        str = self._index_to_html()
        open(directory+'term_index.html', 'w').write(str)
    
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

        # Write the CSS file & help file
        self._write_css(directory)
        self._write_help(directory)

    def _write_css(self, directory):
        cssfile = open(os.path.join(directory, 'epydoc.css'), 'w')
        cssfile.write(self._css)
        cssfile.close()

    def _write_help(self, directory):
        helpfile = open(os.path.join(directory, 'help.html'), 'w')
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
        if isinstance(name, UID):
            print 'Warning: use name, not uid'
            name = name.name()
        return """
<HTML>
  <HEAD>
    <TITLE> %s</TITLE>
    <link rel=\"stylesheet\" href=\"epydoc.css\" type=\"text/css\">
  </HEAD>
  <BODY bgcolor='white' text='black' link='blue' vlink='#204080'
        alink='#204080'>
""" % name
               
    def _footer(self):
        'Return an HTML footer'
        import time
        date = time.asctime(time.localtime(time.time()))
        return '<FONT SIZE=-2>'+\
               'Generated by Epydoc on '+date+'.<BR>\n'+\
               'Epydoc is currently under development.  For '+\
               'information on the status of Epydoc, contact '+\
               '<A HREF="mailto:edloper@gradient.cis.upenn.edu">'+\
               'edloper@gradient.cis.upenn.edu</A>.'+\
               '</FONT>\n\n</BODY>\n</HTML>\n'
    
    def _seealso(self, seealso):
        'Convert a SEEALSO node to HTML'
        #!!!!!!!!!!!!!!!!!!!!!!!!!!!! NO SEEALSO YET
        return ''
        if not seealso: return ''
        str = '<DL><DT><B>See also:</B>\n  <DD>'
        for see in seealso:
            if self._docmap.has_key(see[0]):
                str += self._uid_to_href(see[0], see[1]) + ', '
            else:
                str += see[1] + ', '
        return str[:-2] + '</DD>\n</DT></DL>\n\n'

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
        return `uid`+'.html'

    def _link_to_href(self, link):
        return self._uid_to_href(link.target(), link.name())
    #return ('<a href=' + self._href_target(link.target()) +
    #            '>' + link.name() + '</a>')

    def _uid_to_href(self, uid, label=None):
        'Add an HREF to a uid, when appropriate.'
        if label==None: label = `uid`
        if self._docmap.has_key(uid):
            str = ('<a href=' + self._href_target(uid) +
                   '>' + label + '</a>')
            if not isinstance(self._docmap[uid], ModuleDoc):
                str = '<CODE>'+str+'</CODE>'
        else:
            str = label
        return str

    def _descr(self, descr):
        ## PHASE THIS OUT EVENTUALLY???
        'Convert a description Node to HTML'
        if descr == None: return ''
        str = epytext.to_html(descr)
        open = '<B><I><CENTER><FONT SIZE='
        close = '</FONT></CENTER></I></B>'
        str = re.sub('<H1>', open+'"+2">', str)
        str = re.sub('<H2>', open+'"+1">', str)
        str = re.sub('<H3>', open+'"+0">', str)
        str = re.sub('</H\d>', close, str)
        return str

    #def _descr(self, descr):
    #    return re.sub('</?P>', '', self._descr(descr))
    
    def _heading(self, doc, descr):
        'Return a heading for the given Class or Module'
        uid = doc.uid()
        shortname = uid.name()
        if isinstance(doc, ClassDoc):
            modname = doc.module().name()
            str = '<H2><FONT SIZE="-1">\n'+modname+'</FONT></BR>\n' + \
                  'Class ' + shortname+'</H2>\n\n'
            if doc.bases:
                str += '<PRE>\n' + self._base_tree(uid) + \
                      '</PRE><p>\n\n'
            children = doc.children()
            if children:
                str += '<DL><DT><B>Known Subclasses:</B>\n<DD>'
                for cls in children:
                    str += '    '+self._link_to_href(cls) + ',\n'
                str = str[:-2] + '</DD></DT></DL>\n\n'
            if descr:
                str += '<HR>\n' + self._descr(descr) +\
                      '\n\n'
            return str + '<HR>\n\n'
        elif isinstance(doc, ModuleDoc): pass
        else: raise AssertionError('Unexpected arg to _heading')

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
            str = ' '*(width-2) + '<B>'+`uid`+'</B>\n'
        else: str = ''
        for i in range(len(bases)-1, -1, -1):
            base = bases[i]
            str = (' '*(width-4-len(base.name())) +
                   self._link_to_href(base)+' --+'+postfix+'\n' + 
                   ' '*(width-4) +
                   '   |'+postfix+'\n' +
                   str)
            (t,w) = (base.target(), width)
            if i < len(bases)-1:
                str = (self._base_tree(t, w-4, '   |'+postfix)+str)
            else:
                str = (self._base_tree(t, w-4, '    '+postfix)+str)
        return str
                
    def _base_tree_old(self, uid, prefix='  '):
        """
        Return an HTML picture showing a class's base tree,
        with multiple inheritance.
        """
        if not self._docmap.has_key(uid): return ''
        
        bases = self._docmap[uid].bases()
        if prefix == '  ': str = '  +-- <B>'+`uid`+'</B>\n'
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
            str = ' '*depth + '<LI> <B>' + self._uid_to_href(uid)+'</B>'
            if doc and doc.descr():
                str += ': <I>' + self._summary(doc) + '</I>'
            str += '\n'
            if doc and doc.children():
                str += ' '*depth + '  <UL>\n'
                children = [l.target() for l in doc.children()]
                children.sort()
                for child in children:
                    str += self._class_tree_item(child, depth+4)
                str += ' '*depth + '  </UL>\n'
        return str

    def _class_tree(self):
        str = '<UL>\n'
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
        return str +'</UL>\n'

    def _module_tree_item(self, uid=None, depth=0):
        if uid is not None:
            doc = self._docmap.get(uid, None)
            name = `uid`.split('.')[-1]
            str = ' '*depth + '<LI> <B>'
            str += self._uid_to_href(uid, name)+'</B>'
            if doc and doc.descr():
                str += ': <I>' + self._summary(doc) + '</I>'
            str += '\n'
            if doc and doc.ispackage() and doc.modules():
                str += ' '*depth + '  <UL>\n'
                modules = [l.target() for l in doc.modules()]
                modules.sort()
                for module in modules:
                    str += self._module_tree_item(module, depth+4)
                str += ' '*depth + '  </UL>\n'
        return str

    def _module_tree(self):
        str = '<UL>\n'
        docs = self._docmap.items()
        docs.sort()
        for (uid, doc) in docs:
            if not isinstance(doc, ModuleDoc): continue
            if not doc.package():
                str += self._module_tree_item(uid)
        return str +'</UL>\n'

    def _start_of(self, heading):
        return '\n<!-- =========== START OF '+string.upper(heading)+\
               ' =========== -->\n'
    
    def _table_header(self, heading, css_class):
        'Return a header for an HTML table'
        return self._start_of(heading)+\
               '<TABLE BORDER="1" CELLPADDING="3" ' +\
               'CELLSPACING="0" WIDTH="100%" BGCOLOR="white">\n' +\
               '<TR BGCOLOR="#70b0f0" CLASS="'+css_class+'">\n'+\
               '<TH COLSPAN=2>\n' + heading + \
               '</TH></TR>\n'
    
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
            str += '<TR><TD WIDTH="15%">\n'+\
                  '  <B><I>'+self._link_to_href(link)+\
                  '</I></B></TD>\n  <TD>' + csum + '</TD></TR>\n'
        return str + '</TABLE><p>\n\n'

    def _func_details(self, functions, cls,
                      heading='Function Details'):
        """## Return a detailed description of the functions in a
        class or module."""
        functions = self._sort(functions)
        if len(functions) == 0: return ''
        str = self._table_header(heading, 'details')+'</TABLE>'

        for link in functions:
            fname = link.name()
            func = link.target()
            if not self._docmap.has_key(func):
                if WARN_MISSING:
                    print 'WARNING: MISSING', func
                continue
            
            fdoc = self._docmap[func]

            rval = fdoc.returns()
            if rval.type():
                rtype = epytext.to_html(rval.type())
            else: rtype = '&nbsp;'
            
            pstr = '('
            for param in fdoc.parameters():
                pstr += param.name()
                if param.default():
                    default = param.default()
                    if len(default) > 60:
                        default = default[:57]+'...'
                    pstr += '='+default
                pstr += ', '
            if fdoc.vararg():
                pstr += '*'+fdoc.vararg().name()+', '
            if fdoc.kwarg():
                pstr += '**'+fdoc.kwarg().name()+', '
            if pstr == '(': pstr = '()'
            else: pstr = pstr[:-2]+')'
            
            str += '<A NAME="'+fname+'"/>\n'
            if HTML_Doc._SPECIAL_METHODS.has_key(fname):
                str += '<H3><I>'+\
                      HTML_Doc._SPECIAL_METHODS[fname]+'</I></H3>\n'
            else:
                str += '<H3>'+fname+'</H3>\n'
            str += '<CODE><B>' +fname + pstr + '</B></CODE><p>\n'
            str += '<DL>\n'

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
                str += '  <DT><DD>'+epytext.to_html(fdescr)+'</DD></DT>\n'
                str += '  <P></P>\n'
            str += '  <DT><DD>\n'

            # Parameters
            if fparam:
                str += '    <DL><DT><B>Parameters:</B>\n'
                for param in fparam:
                    pname = param.name()
                    str += '      <DD><CODE><B>' + pname +'</B></CODE>'
                    if param.descr():
                        str += ' - ' + epytext.to_html(param.descr())
                    if param.type():
                        str += ' </BR>\n        <I>'+('&nbsp;'*10)+\
                              '(type=' + \
                              epytext.to_html(param.type()) +\
                              ')</I>'
                    str += '</DD>\n'
                str += '    </DT></DL>\n'

            # Returns
            if freturn.descr() or freturn.type():
                str += '    <DL><DT><B>Returns:</B>\n      <DD>'
                if freturn.descr():
                    str += epytext.to_html(freturn.descr())
                    if freturn.type():
                        str += ' </BR>' + '<I>'+('&nbsp;'*10)+\
                              '(type=' + \
                              epytext.to_html(freturn.type()) +\
                              ')</I>'
                elif freturn.type():
                    str += epytext.to_html(freturn.type())
                str += '</DD>\n    </DT></DL>\n'

            # Raises
            if fraises:
                str += '    <DL><DT><B>Raises:</B>\n'
                for fraise in fraises:
                    str += '      '
                    str += '<DD><CODE><B>'+fraise.name()+'</B></CODE> - '
                    str += epytext.to_html(fraise.descr())+'</DD>\n'
                str += '    </DT></DL>\n'

            # Overrides
            if foverrides:
                cls = foverrides.cls()
                str += '    <DL><DT><B>Overrides:</B>\n'
                if self._docmap.has_key(cls):
                    str += ('      <DD><CODE><a href=' +
                            self._href_target(cls) + '#' +
                            foverrides.shortname() +
                            '>' + `foverrides` + '</a></CODE>')
                else:
                    str += '      <DD><CODE>'+`func`+'</CODE>'
                if inheritdoc:
                    str += ' <I>(inherited documentation)</I>\n'
                str += '</DD>\n    </DT></DL>\n'
                
            str += '  </DD>\n</DT></DL><hr>\n\n'
        return str

    def _var_details(self, variables, heading='Variable Details'):
        """## Return a detailed description of the variables in a
        class or module."""
        variables = self._sort(variables)
        if len(variables) == 0: return ''
        str = self._table_header(heading, 'details')+'</TABLE>'

        numvars = 0
        for var in variables:
            # Don't bother if we don't know anything about it.
            if not (var.descr() or var.type()): continue
            numvars += 1
            
            vname = var.name()

            str += '<A NAME="'+vname+'"/>\n'
            str += '<H3>'+vname+'</H3>\n'
            str += '<DL>\n'

            if var.descr():
                str += '  <DD>'+\
                      epytext.to_html(var.descr())+'<p>\n'
                
            if var.type():
                str += '  <DL><DT><B>Type:</B>\n' +\
                      '<CODE>'+epytext.to_html(var.type())+\
                      '</CODE>'+'</DL>\n'
                      

            #if var.overrides():
            #    str += '  <DL><DT><B>Overrides:</B>\n'
            #    for target in var.overrides():
            #        str += '    <DD>' + \
                  #        self._link_to_href(target.data[0]) + '\n'
            #    str += '  </DL>\n'
            
            str += '</DL><hr>\n'

        # If we didn't get any variables, don't print anything.
        if numvars == 0: return ''
        return str

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
                fsum = '</BR>'+descrstr
            else: fsum = ''
            str += '<TR><TD ALIGN="right" VALIGN="top" '+\
                  'WIDTH="15%"><FONT SIZE="-1">'+\
                  rtype+'</FONT></TD>\n'+\
                  '  <TD><CODE><B><A href="#'+fname+'">'+\
                  fname+'</A>'+\
                  '</B>'+pstr+'</CODE>\n  '+\
                  fsum+'</TD></TR>\n'
        return str + '</TABLE><p>\n\n'
    
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
                vsum = '</BR>'+self._summary(var)
            else: vsum = ''
            str += '<TR><TD ALIGN="right" VALIGN="top" '+\
                  'WIDTH="15%"><FONT SIZE="-1">'+vtype+'</TD>\n'+\
                  '  <TD><CODE><B><A href="#'+vname+'">'+vname+\
                  '</A>'+'</B></CODE>\n  ' + vsum+'</TD></TR>\n'
        return str + '</TABLE><p>\n\n'

    def _module_list(self, modules):
        if len(modules) == 0: return ''
        str = '<H3>Modules</H3>\n<UL>\n'
        for link in modules:
            str += self._module_tree_item(link.target())
            #str += '  <LI><A HREF="'+`link.target()`+'.html">'
            #str += link.name() + '</A>\n'
        return str + '</UL>\n'

    def _navbar(self, where, uid=None):
        """
        @param where: What page the navbar is being displayed on..
        """
        str = self._start_of('Navbar')
        str += '<TABLE CLASS="navbar" BORDER="0" WIDTH="100%"'
        str += ' CELLPADDING="0" BGCOLOR="#a0c0ff" CELLSPACING="0">\n'
        str += '  <TR>\n'
        str += '    <TD WIDTH="100%">\n'
        str += '      <TABLE BORDER="0" CELLPADDING="0" CELLSPACING="0">\n'
        str += '        <TR VALIGN="top">\n'

        I = '          ' # indentation
        # Go to Package
        if self._package is None: pass
        elif where in ('class', 'module'):
            pkg = uid.package()
            if pkg is not None:
                str += I+'<TH CLASS="navbar">&nbsp;&nbsp;&nbsp;'+\
                      '<A CLASS="navbar" HREF="'+`pkg`+'.html">'+\
                      'Package</A>&nbsp;&nbsp;&nbsp;</TH>\n'
            else:
                str += I+'<TH CLASS="navbar">&nbsp;&nbsp;&nbsp;'+\
                       'Package&nbsp;&nbsp;&nbsp;</TH>\n'
        elif where=='package':
            str += I+'<TH BGCOLOR="#70b0f0" CLASS="navselect">'+\
                   '&nbsp;&nbsp;&nbsp;'+\
                   'Package&nbsp;&nbsp;&nbsp;</TH>\n'
        elif isinstance(self._package, UID):
            str += I+'<TH CLASS="navbar">&nbsp;&nbsp;&nbsp;'+\
                   '<A CLASS="navbar" HREF="'+`self._package`+'.html">'+\
                   'Package</A>&nbsp;&nbsp;&nbsp;</TH>\n'
        elif 'multiple' == self._package:
            str += I+'<TH CLASS="navbar">&nbsp;&nbsp;&nbsp;'+\
                  'Package&nbsp;&nbsp;&nbsp;</TH></B>\n'
        
        # Go to Module
        if self._module is None: pass
        elif where=='class':
            str += I+'<TH CLASS="navbar">&nbsp;&nbsp;&nbsp;'+\
                  '<A CLASS="navbar" HREF="'+`uid.module()`+'.html">'+\
                  'Module</A>&nbsp;&nbsp;&nbsp;</TH>\n'
        elif where=='module':
            str += I+'<TH BGCOLOR="#70b0f0" CLASS="navselect">&nbsp;' +\
                   '&nbsp;&nbsp;Module&nbsp;&nbsp;&nbsp;</TH>\n'
        elif isinstance(self._module, UID):
            str += I+'<TH CLASS="navbar">&nbsp;&nbsp;&nbsp;'+\
                  '<A CLASS="navbar" HREF="'+`self._module`+'.html">'+\
                  'Module</A>&nbsp;&nbsp;&nbsp;</TH>\n'
        elif 'multiple' == self._module:
            str += I+'<TH CLASS="navbar">&nbsp;&nbsp;&nbsp;'+\
                  'Module&nbsp;&nbsp;&nbsp;</TH></B>\n'
        
        # Go to Class
        if where == 'class':
            str += I+'<TH BGCOLOR="#70b0f0" CLASS="navselect">&nbsp;'+\
                   '&nbsp;&nbsp;Class&nbsp;&nbsp;&nbsp;</TH>\n'
        else:
            str += I+'<TH CLASS="navbar">&nbsp;&nbsp;&nbsp;Class' +\
                   '&nbsp;&nbsp;&nbsp;</TH>\n'

        # Go to Tree
        if where == 'tree':
            str += I+'<TH BGCOLOR="#70b0f0" CLASS="navselect">&nbsp;'+\
                   '&nbsp;&nbsp;Trees&nbsp;&nbsp;&nbsp;</TH>\n'
        else:
            str += I+'<TH CLASS="navbar">&nbsp;&nbsp;&nbsp;'+\
                   '<A CLASS="navbar" HREF="tree.html">Trees</A>'+\
                   '&nbsp;&nbsp;&nbsp;</TH>\n'

        # Go to Index
        if where == 'index':
            str += I+'<TH BGCOLOR="#70b0f0" CLASS="navselect">&nbsp;'+\
                   '&nbsp;&nbsp;Index&nbsp;&nbsp;&nbsp;</TH>\n'
        else:
            str += I+'<TH CLASS="navbar">&nbsp;&nbsp;&nbsp;'+\
                   '<A CLASS="navbar" HREF="term_index.html">Index</A>'+\
                   '&nbsp;&nbsp;&nbsp;</TH>\n'

        # Go to Help
        if where == 'help':
            str += I+'<TH BGCOLOR="#70b0f0" CLASS="navselect">&nbsp;'+\
                   '&nbsp;&nbsp;Help&nbsp;&nbsp;&nbsp;</TH>\n'
        else:
            str += I+'<TH CLASS="navbar">&nbsp;&nbsp;&nbsp;'+\
                   '<A CLASS="navbar" HREF="help.html">Help</A>'+\
                   '&nbsp;&nbsp;&nbsp;</TH>\n'

        str += '        </TR>\n      </TABLE>\n    </TD>\n'
        str += '    <TD>\n'
        str += '      <TABLE BORDER="0" CELLPADDING="0" CELLSPACING="0">\n'
        str += '        <TR VALIGN="top">\n'
        str += '          <TH CLASS="navbar">'
        if self._pkg_name:
            if self._pkg_url:
                str += ('<A CLASS="navbar" HREF="%s">%s</A>' %
                          (self._pkg_url, self._pkg_name))
            else:
                str += I+self._pkg_name

        str += '</TH>\n        </TR>\n'
        str += '      </TABLE>\n    </TD>\n  </TR>\n</TABLE>\n'
        return str

    def _module_to_html(self, uid):
        'Return an HTML page for a Module'
        doc = self._docmap[uid]
        descr = doc.descr()
        if uid.is_package(): moduletype = 'package'
        else: moduletype = 'module'
        
        str = self._header(`uid`)
        str += self._navbar(moduletype, uid)

        if moduletype == 'package':
            str += self._start_of('Package Description')
            str += '<H2>Package '+uid.name()+'</H2>\n\n'
        else:
            str += self._start_of('Module Description')
            str += '<H2>Module '+uid.name()+'</H2>\n\n'

        if descr:
            str += self._descr(descr) + '<HR>\n'
        if doc.seealsos():
            str += self._seealso(doc.seealsos())

        if doc.ispackage():
            str += self._module_list(doc.modules())
        
        str += self._class_summary(doc.classes())
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
        str += self._start_of('Class Description')
        
        str += '<H2><FONT SIZE="-1">\n'+modname+'</FONT></BR>\n' + \
               'Class ' + `uid`+'</H2>\n\n'
        if doc.bases():
            str += '<PRE>\n' + self._base_tree(uid) + \
                   '</PRE><p>\n\n'
        children = doc.children()
        if children:
            str += '<DL><DT><B>Known Subclasses:</B>\n<DD>'
            for cls in children:
                str += '    '+self._link_to_href(cls) + ',\n'
            str = str[:-2] + '</DD></DT></DL>\n\n'
        if descr:
            str += '<HR>\n' + self._descr(descr) +\
                   '\n\n'
        str += '<HR>\n\n'

        str += self._seealso(doc.seealsos())

        str += self._func_summary(doc.methods(),\
                                       'Method Summary')
        str += self._var_summary(doc.ivariables(),\
                                      'Instance Variable Summary')
        str += self._var_summary(doc.cvariables(),\
                                      'Class Variable Summary')
        
        str += self._func_details(doc.methods(), doc, \
                                       'Method Details')
        str += self._var_details(doc.ivariables(), \
                                      'Instance Variable Details')
        str += self._var_details(doc.cvariables(), \
                                      'Class Variable Details')
        
        str += self._navbar('class', uid)
        return str + self._footer()

    def _tree_to_html(self):
        str = self._header('Class Hierarchy')
        str += self._navbar('tree') 
        str += self._start_of('Class Hierarchy')
        str += '<H2>Module Hierarchy</H2>\n'
        str += self._module_tree()
        str += '<H2>Class Hierarchy</H2>\n'
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
            base = `uid`
            descr = doc.descr()
            if descr:
                self.get_index_items(descr, base, index)
        return index

    def _index_to_html(self):
        str = self._header('Index')
        str += self._navbar('index') + '<br/>\n'
        str += self._start_of('Index')

        str += self._table_header('Index', 'index')
        index = self._extract_index().items()
        index.sort()
        for (term, sources) in index:
            str += '  <TR><TD>'+term+'</TD>\n    <TD>'
            sources.sort()
            for source in sources:
                target = source+'.html#'+epytext.index_to_anchor(term)
                str += '<I><A href="' + target + '">'
                str += source + '</A></I>, '
            str = str[:-2] + '</TR></TD>\n'
        str += '</TABLE>\n' +  '<br/>\n'
        
        str += self._navbar('index')
        str += self._footer()
        return str
