#!/usr/bin/python2.2
#
# epydoc.py: latex output
# Edward Loper
#
# Created [01/30/01 05:18 PM]
# $Id$
#

r"""

Documentation formatter that produces A single LaTeX document
containing the API documentation.

Individual classes and modules are documented in separate files, and
included via C{"\include"} directives.  This makes it easy to include
the documentation for specific classes and modules as chapters of
other LaTeX documents.

Files:
  - 

This module is under development.
"""
__docformat__ = 'epytext en'

##################################################
## Imports
##################################################

# system imports
import sys, xml.dom.minidom, os.path, time, types, re
import pprint

# epydoc imports
import epydoc
import epydoc.epytext as epytext
from epydoc.uid import UID, Link, findUID, make_uid
from epydoc.imports import import_module
from epydoc.objdoc import DocMap, ModuleDoc, FuncDoc
from epydoc.objdoc import ClassDoc, Var, Raise, ObjDoc

##################################################
## CONSTANTS
##################################################

# Once I'm done, check which pacakges I actually use.
_LATEX_HEADER = r"""
\documentclass{article}
\usepackage{fullpage, alltt, parskip, fancyheadings, boxedminipage}
\usepackage{makeidx, multirow}
\addtolength{\parskip}{0.5ex}
\setlength{\parindent}{0ex}
\setlength{\fboxrule}{2\fboxrule}
\newlength{\BCL} % base class length, for base trees.
\makeindex
\begin{document}

\pagestyle{fancy}
\renewcommand{\sectionmark}[1]{\markboth{#1}{}}
\renewcommand{\subsectionmark}[1]{\markright{#1}}

\newenvironment{Ventry}[1]%
  {\begin{list}{}{%
    \renewcommand{\makelabel}[1]{\texttt{##1:}\hfil}%
    \settowidth{\labelwidth}{\texttt{#1:}}%
    \setlength{\leftmargin}{\labelsep}%
    \addtolength{\leftmargin}{\labelwidth}}}%
  {\end{list}}
""".strip()

_HRULE = '\\rule{\\textwidth}{0.5\\fboxrule}\n\n'

_SECTIONS = ['\\part{%s}', '\\chapter{%s}', '\\section{%s}',
             '\\subsection{%s}', '\\subsubsection{%s}',
             '\\textbf{%s}']
_STARSECTIONS = ['\\part*{%s}', '\\chapter*{%s}', '\\section*{%s}',
                 '\\subsection*{%s}', '\\subsubsection*{%s}',
                 '\\textbf{%s}']

##################################################
## Documentation -> Latex Conversion
##################################################

class LatexFormatter:
    def __init__(self, docmap, **kwargs):
        self._docmap = docmap

        # Process keyword arguments
        self._show_private = kwargs.get('private', 0)
        self._prj_name = kwargs.get('prj_name', 0)
        self._top_section = 2
        self._list_classes_separately = 1
        self._index_functions = 1
        
    def dvi(self, directory):
        self.write(directory)
        oldpath = os.path.abspath(os.curdir)
        os.chdir(directory)
        ## DEBUG
        #return
        print 'RUNNING LaTeX'
        os.system('latex api.tex')
        #os.system('makeindex api.idx')
        #os.system('latex api.tex')
        os.chdir(oldpath)

    def write(self, directory):
        # Create dest directory, if necessary
        if not os.path.isdir(directory):
            if os.path.exists(directory):
                raise OSError('%r is not a directory' % directory)
            os.mkdir(directory)

        # Write the module & class files.
        for uid in self._filtersort_uids(self._docmap.keys()):
            if uid.is_module():
                filename = os.path.join(directory, ('%s-module.tex' %
                                                    uid.name()))
                open(filename, 'w').write(self._module_to_latex(uid))
            elif uid.is_class() and self._list_classes_separately:
                filename = os.path.join(directory, ('%s-class.tex' %
                                                    uid.name()))
                open(filename, 'w').write(self._class_to_latex(uid))

        # Write the top-level file.
        filename = os.path.join(directory, 'api.tex')
        open(filename, 'w').write(self._topfile())
        
    #////////////////////////////////////////////////////////////
    # Main Doc File
    #////////////////////////////////////////////////////////////

    def _topfile(self):
        str = self._header('Inclue File')

        str += self._start_of('Header')
        str += _LATEX_HEADER + '\n'

        str += self._start_of('Includes')
        for uid in self._filtersort_uids(self._docmap.keys()):
            if uid.is_module():
                str += '\\include{%s-module}\n' % uid.name()
            elif uid.is_class() and self._list_classes_separately:
                str += '\\include{%s-class}\n' % uid.name()

        str += self._start_of('Index')
        str += '\\printindex\n\n'
        str += self._start_of('Footer')
        str += '\\end{document}\n\n'
        return str

    #////////////////////////////////////////////////////////////
    # Chapters
    #////////////////////////////////////////////////////////////

    def _module_to_latex(self, uid):
        # Get the module's documentation.
        doc = self._docmap[uid]

        # Start the chapter.
        str = self._header(uid)
        str += self._start_of('Module Description')
        str += '    ' + self._index(uid, 'start')
        str += '    \\label{%s}\n' % uid.name().replace('_', '-')
        if uid.is_package():
            str += self._section('Package %s' % uid.name(), 0)
        else:
            str += self._section('Module %s' % uid.name(), 0)

        # The module's description.
        if doc.descr():
            str += self._dom_to_latex(doc.descr())

        # Version
        if doc.version():
            str += self._version(doc.version(), uid)
                
        # Author
        if doc.authors():
            str += self._author(doc.authors(), uid)
            
        # Requirements
        if doc.requires():
            str += self._requires(doc.requires(), uid)
            
        # Warnings
        if doc.warnings():
            str += self._warnings(doc.warnings(), uid)
            
        # See also
        if doc.seealsos():
            str += self._seealso(doc.seealsos(), uid)

        # If it's a package, list the sub-modules.
        if doc.ispackage() and doc.modules():
            str += self._module_list(doc.modules(), doc.sortorder())

        # Class list. !! add summaries !!
        if self._list_classes_separately:
            classes = self._filtersort_vars(doc.classes(), doc.sortorder())
            if classes:
                str += self._start_of('Classes')
                str += self._section('Classes', 1)
                str += '\\begin{itemize}'
                str += '  \\setlength{\\parskip}{0.6ex}'
                for cls in doc.classes():
                    str += ('\\item %s (Section~\\ref{%s})\n' %
                            (self._text_to_latex(cls.target().name()),
                             cls.target().name().replace('_', '-')))
                str += '\\end{itemize}'
                
        # Function List
        str += self._func_list(doc.functions(), None)

        # !! variable list !!
        if doc.variables():
            str += self._var_list(doc.variables())

        # Class list.
        if not self._list_classes_separately:
            for cls in doc.classes():
                str += self._class_to_latex(cls.target())
        
        str += '    ' + self._index(uid, 'end')
        return str
                
    def _class_to_latex(self, uid):
        # Get the module's documentation.
        doc = self._docmap[uid]

        # Start the chapter.
        str = ''
        if self._list_classes_separately: str += self._header(uid)
        str += '    ' + self._index(uid, 'start')
        str += '    \\label{%s}\n' % uid.name().replace('_', '-')
        str += self._start_of('Class Description')
        if self._list_classes_separately:
            seclevel = 0
            str += self._section('Class %s' % uid.name(), seclevel)
        else:
            seclevel = 1
            str += self._section('Class %s' % uid.shortname(), seclevel)

        # The class base tree.
        if doc.bases():
            str += self._base_tree(uid)

        # The class's known subclasses.
        if doc.subclasses():
            str += self._subclasses(doc.subclasses(), uid)

        # The class's description
        if doc.descr():
            str += self._dom_to_latex(doc.descr())
        
        # Version
        if doc.version():
            str += self._version(doc.version(), uid)
                
        # Author
        if doc.authors():
            str += self._author(doc.authors(), uid)
            
        # Requirements
        if doc.requires():
            str += self._requires(doc.requires(), uid)
            
        # Warnings
        if doc.warnings():
            str += self._warnings(doc.warnings(), uid)
            
        # See also
        if doc.seealsos():
            str += self._seealso(doc.seealsos(), uid)

        # Methods.
        str += self._func_list(doc.methods(), doc,
                               'Methods', seclevel+1)
        str += self._func_list(doc.staticmethods(), doc,
                               'Static Methods', seclevel+1)
        str += self._func_list(doc.classmethods(), doc,
                               'Class Methods', seclevel+1)

        if doc.ivariables():
            str += self._var_list(doc.ivariables(),
                                  'Instance Variables', seclevel+1)
        if doc.cvariables():
            str += self._var_list(doc.cvariables(),
                                  'Class Variables', seclevel+1)

        # End mark for the class's index entry.
        str += '    ' + self._index(uid, 'end')
        
        return str

    #////////////////////////////////////////////////////////////
    # Variable List
    #////////////////////////////////////////////////////////////

    def _var_list(self, variables, heading='Variables', seclevel=1):
        variables = self._filtersort_vars(variables)
        if len(variables) == 0: return ''
        
        str = self._start_of(heading)
        str += '  '+self._section(heading, seclevel)

        str += '\\begin{tabular}{|p{.15\\textwidth}|p{.25\\textwidth}|'
        str += 'p{.5\\textwidth}|l}\n'
        str += '\\cline{1-3}\n'
        str += '\\centering \\textbf{Type}& '
        str += '\\centering \\textbf{Name} & '
        str += '\\centering \\textbf{Description/Value}& \\\\\n'
        str += '\\cline{1-3}\n'

        for var in variables:
            if var.type():
                typ = self._dom_to_latex(var.type(), 10).strip()
                str += '\\raggedleft ' + typ.replace('.', '.\-')
            str += ' & \\centering '

            str += self._text_to_latex(var.name()) + ' & '

            if var.descr():
                str += self._dom_to_latex(var.descr(), 10).strip()
            elif var.has_value():
                val = self._pprint_var_value(var)
                str += '%s' % val
            str += '\\\\\n'
            str += '\\cline{1-3}\n'

        str += '\\end{tabular}\n\n'
        return str
    
    def _pprint_var_value(self, var):
        val = var.uid().value()
        
        #if type(val) == type(''):
        #    val = self._text_to_latex(`val`)
        #    latex_nl = self._text_to_latex(r'\n')
        #    if val.find(latex_nl) >= 0:
        #        val = val[1:-1].replace(latex_nl, '\n')
        #elif type(val) in (type(()), type([]), type({})):
        #    pp = pprint.PrettyPrinter(width=50)
        #    val = self._text_to_latex(pp.pformat(val)) 
        #else:
        #    try: val = self._text_to_latex(`val`)
        #    except: val = '...'
        
        try:
            val = `val`
            if len(val) > 40: val = val[:37] + '...'
            val = self._text_to_latex(val)
        except: val = '...'

        if val.count('\n') > 6:
            val = '\n'.join(val.split('\n')[:6])+'\n\\textbf{...}\n'

        # Add an alltt around it.
        if val.count('\n') > 0:
            val = '\\begin{alltt}\n%s\\end{alltt}\n' % val
        else:
            val = '\\texttt{%s}' % val
            
        return val
    
    #////////////////////////////////////////////////////////////
    # Function List
    #////////////////////////////////////////////////////////////
    
    def _func_list(self, functions, cls, heading='Functions', seclevel=1):
        
        functions = self._filtersort_links(functions)
        if len(functions) == 0: return ''

        str = self._start_of(heading)
        str += '  '+self._section(heading, seclevel)

        numfuncs = 0
        for link in functions:
            fname = link.name()
            func = link.target()
            if func.is_method() or func.is_builtin_method():
                container = func.cls()
                # (If container==ClassType, it's (probably) a class method.)
                inherit = (container != cls.uid() and
                           container.value() is not types.ClassType)
            else:
                inherit = 0
                try: container = func.module()
                except TypeError: container = None

            # If we don't have documentation for the function, then we
            # can't say anything about it.
            if not self._docmap.has_key(func): continue
            fdoc = self._docmap[func]

            # What does this method override?
            foverrides = fdoc.overrides()

            # Try to find a documented ancestor.
            inhdoc = fdoc
            inherit_docs = 0
            while (not inhdoc.documented() and inhdoc.overrides() and
                   self._docmap.has_key(inhdoc.overrides())):
                inherit_docs = 1
                inhdoc = self._docmap[inhdoc.overrides()]

            if not inherit:
                str += '    \\label{%s}\n' % func.name().replace('_', '-')
            
            numfuncs += 1
            fsig = self._func_signature(fname, fdoc)
            str += '    ' + self._index(func)
            str += '    \\vspace{0.5ex}\n\n'
            str += '    \\begin{boxedminipage}{\\textwidth}\n\n'
            str += '    %s\n\n' % fsig

            # Use the inherited docs for everything but the signature.
            fdoc = inhdoc

            if fdoc.documented():
                str += '    \\vspace{-1.5ex}\n\n'
                str += '    \\rule{\\textwidth}{0.5\\fboxrule}\n'
            
            fdescr=fdoc.descr()
            fparam = fdoc.parameter_list()[:]
            if fdoc.vararg(): fparam.append(fdoc.vararg())
            if fdoc.kwarg(): fparam.append(fdoc.kwarg())
            freturn = fdoc.returns()
            fraises = fdoc.raises()
            
            # Don't list parameters that don't have any extra info.
            f = lambda p:p.descr() or p.type()
            fparam = filter(f, fparam)

            # Description
            if fdescr:
                str += self._dom_to_latex(fdescr, 4)
                str += '    \\vspace{1ex}\n\n'

            # Parameters
            if fparam:
                longest = max([len(p.name()) for p in fparam])
                str += ' '*6+'\\textbf{Parameters}\n'
                str += ' '*6+'\\begin{quote}\n'
                str += '        \\begin{Ventry}{%s}\n\n' % (longest*'x')
                for param in fparam:
                    pname = self._text_to_latex(param.name())
                    str += (' '*10+'\\item[' + pname + ']\n\n')
                    if param.descr():
                        str += self._dom_to_latex(param.descr(), 10)
                    if param.type():
                        ptype = self._dom_to_latex(param.type(), 12).strip()
                        str += ' '*12+'\\textit{(type=%s)}\n\n' % ptype
                str += '        \\end{Ventry}\n\n'
                str += ' '*6+'\\end{quote}\n\n'
                str += '    \\vspace{1ex}\n\n'

            # Returns
            if freturn.descr() or freturn.type():
                str += ' '*6+'\\textbf{Return Value}\n'
                str += ' '*6+'\\begin{quote}\n'
                if freturn.descr():
                    str += self._dom_to_latex(freturn.descr(), 6)
                    if freturn.type():
                        rtype = self._dom_to_latex(freturn.type(), 6).strip()
                        str += ' '*6+'\\textit{(type=%s)}\n\n' % rtype
                elif freturn.type():
                    str += self._dom_to_latex(freturn.type(), 6)
                str += ' '*6+'\\end{quote}\n\n'
                str += '    \\vspace{1ex}\n\n'

            # Raises
            if fraises:
                str += ' '*6+'\\textbf{Raises}\n'
                str += ' '*6+'\\begin{quote}\n'
                str += '        \\begin{description}\n\n'
                for fraise in fraises:
                    str += '          '
                    str += '\\item[\\texttt{'+fraise.name()+'}]\n\n'
                    str += self._dom_to_latex(fraise.descr(), 10)
                str += '        \\end{description}\n\n'
                str += ' '*6+'\\end{quote}\n\n'
                str += '    \\vspace{1ex}\n\n'

            ## Overrides
            #if foverrides:
            #    str += '      Overrides: %s' % foverrides
            #    if inherit_docs:
            #        str += ' \textit{(inherited documentation)}'
            #    str += '\n\n'
            #
            # Version
            if fdoc.version():
                str += self._version(fdoc.version(), func.parent())
                
            # Author
            if fdoc.authors():
                str += self._author(fdoc.authors(), func.parent())
                
            # Requirements
            if fdoc.requires():
                str += self._requires(fdoc.requires(), func.parent())
                
            # Warnings
            if fdoc.warnings():
                str += self._warnings(fdoc.warnings(), func.parent())
                
            # See also
            if fdoc.seealsos():
                str += self._seealso(fdoc.seealsos(), func.parent())

            str += '    \\end{boxedminipage}\n\n'

        if numfuncs == 0: return ''

        return str
    
    def _func_signature(self, fname, fdoc, show_defaults=1):
        str = '\\textbf{%s}' % self._text_to_latex(fname)
        str += '('
        str += self._params_to_latex(fdoc.parameters(), show_defaults)
        
        if fdoc.vararg():
            vararg_name = self._text_to_latex(fdoc.vararg().name())
            vararg_name = '\\textit{%s}' % vararg_name
            if vararg_name != '\\textit{...}':
                vararg_name = '*%s' % vararg_name
            str += '%s, ' % vararg_name
        if fdoc.kwarg():
            str += ('**\\textit{%s}, ' %
                    self._text_to_latex(fdoc.kwarg().name()))
        if str[-1] != '(': str = str[:-2]

        return str + ')'
    
    def _params_to_latex(self, parameters, show_defaults):
        str = ''
        for param in parameters:
            if type(param) in (type([]), type(())):
                sublist = self._params_to_latex(param, show_defaults)
                str += '(%s), ' % sublist[:-2]
            else:
                str += '\\textit{%s}' % self._text_to_latex(param.name())
                if show_defaults and param.default() is not None:
                    default = param.default()
                    if len(default) > 60:
                        default = default[:57]+'...'
                    str += '=\\texttt{%s}' % self._text_to_latex(default)
                str += ', '
        return str

    #////////////////////////////////////////////////////////////
    # Docstring -> LaTeX Conversion
    #////////////////////////////////////////////////////////////
    
    def _dom_to_latex(self, tree, indent=0):
        if isinstance(tree, xml.dom.minidom.Document):
            tree = tree.childNodes[0]
        return self._dom_to_latex_helper(tree, indent, 0)

    def _dom_to_latex_helper(self, tree, indent, seclevel):
        if isinstance(tree, xml.dom.minidom.Text):
            return self._text_to_latex(tree.data)

        if tree.tagName == 'section': seclevel += 1
    
        # Figure out the child indent level.
        if tree.tagName == 'epytext': cindent = indent
        cindent = indent + 2
        children = [self._dom_to_latex_helper(c, cindent, seclevel)
                    for c in tree.childNodes]
        childstr = ''.join(children)
    
        if tree.tagName == 'para':
            return epytext.wordwrap(childstr, indent)+'\n'
        elif tree.tagName == 'code':
            return '\\texttt{%s}' % childstr
        elif tree.tagName == 'uri':
            if len(children) != 2: raise ValueError('Bad URI ')
            elif children[0] == children[1]:
                return '\\textit{%s}' % children[1]
            else:
                return '%s\\footnote{%s}' % (children[0], children[1])
        elif tree.tagName == 'link':
            if len(children) != 2: raise ValueError('Bad Link')
            return '\\texttt{%s}' % children[1]
        elif tree.tagName == 'italic':
            return '\\textit{%s}' % childstr
        elif tree.tagName == 'math':
            return '\\textit{%s}' % childstr
        elif tree.tagName == 'indexed':
            # Quote characters for makeindex.
            indexstr = re.sub(r'["!|@]', r'"\1', childstr)
            return ('\\index{%s}\\textit{%s}' % (indexstr, childstr))
        elif tree.tagName == 'bold':
            return '\\textbf{%s}' % childstr
        
        elif tree.tagName == 'li':
            return indent*' ' + '\\item ' + childstr.lstrip()
        elif tree.tagName == 'heading':
            return ' '*(indent-2) + '(section) %s\n\n' % childstr
        elif tree.tagName == 'doctestblock':
            return '\\begin{alltt}\n%s\n\\end{alltt}\n\n' % childstr
        elif tree.tagName == 'literalblock':
            # BUT: escaping!!
            return '\\begin{alltt}\n%s\n\\end{alltt}\n\n' % childstr
        elif tree.tagName == 'fieldlist':
            return indent*' '+'{omitted fieldlist}\n'
        elif tree.tagName == 'olist':
            return (' '*indent + '\\begin{enumerate}\n\n' + 
                    ' '*indent + '\\setlength{\\parskip}{0.5ex}' +
                    childstr +
                    ' '*indent + '\\end{enumerate}\n\n')
        elif tree.tagName == 'ulist':
            return (' '*indent + '\\begin{itemize}\n' +
                    ' '*indent + '\\setlength{\\parskip}{0.6ex}' +
                    childstr +
                    ' '*indent + '\\end{itemize}\n\n')
        else:
            # Assume that anything else can be passed through.
            return childstr

    #////////////////////////////////////////////////////////////
    # Base class trees
    #////////////////////////////////////////////////////////////

    def _find_tree_width(self, uid):
        width = 2
        if self._docmap.has_key(uid):
            for base in self._docmap[uid].bases():
                width = max(width, self._find_tree_width(base.target())+2)

        return width

    def _base_tree(self, uid, width=None, linespec=None):
        if width is None:
            width = self._find_tree_width(uid)+2
            linespec = []
            str = ('&'*(width-4)+'\\multicolumn{2}{l}{\\textbf{%s}}\n' %
                   self._text_to_latex(uid.shortname()))
            str += '\\end{tabular}\n\n'
            top = 1
        else:
            str = self._base_tree_line(uid, width, linespec)
            top = 0
        
        bases = self._docmap[uid].bases()
        
        for i in range(len(bases)-1, -1, -1):
            base = bases[i].target()
            spec = (i > 0)
            str = self._base_tree(base, width, [spec]+linespec) + str

        if top:
            str = '\\begin{tabular}{%s}\n' % (width*'c') + str

        return str

    def _base_tree_line(self, uid, width, linespec):
        # linespec is a list of booleans.

        str = '%% Line for %s, linespec=%s\n' % (uid.name(), linespec)

        labelwidth = width-2*len(linespec)-2

        # The base class name.
        shortname = self._text_to_latex(uid.name())
        str += ('\\multicolumn{%s}{r}{' % labelwidth)
        str += '\\settowidth{\\BCL}{%s}' % shortname
        str += '\\multirow{2}{\\BCL}{%s}}\n' % shortname
        #str += '\\hline\n'
        #shortname = `labelwidth`
        #str += ('\\multicolumn{%s}{|r|}{\\multirow{2}{%sex}{%s}}\n' %
        #        (labelwidth, len(uid.shortname()), shortname))

        # The vertical bars for other base classes (top half)
        for vbar in linespec:
            if vbar: str += '&&\\multicolumn{1}{|c}{}\n'
            else: str += '&&\n'

        # The horizontal line.
        str += '  \\\\\\cline{%s-%s}\n' % (labelwidth+1, labelwidth+1)

        # The vertical bar for this base class.
        str += '  ' + '&'*labelwidth
        str += '\\multicolumn{1}{c|}{}\n'

        # The vertical bars for other base classes (bottom half)
        for vbar in linespec:
            if vbar: str += '&\\multicolumn{1}{|c}{}&\n'
            else: str += '&&\n'
        str += '  \\\\\n'

        return str
        
    #////////////////////////////////////////////////////////////
    # Module hierarchy trees
    #////////////////////////////////////////////////////////////
    
    def _module_tree_item(self, uid=None, depth=0):
        """
        Helper function for L{_module_tree} and L{_module_list}.
        
        @rtype: C{string}
        """
        if uid is None: return ''

        doc = self._docmap.get(uid, None)
        str = ' '*depth + '\\item \\textbf{'
        str += uid.shortname()+'}'
        if doc and doc.descr():
            str += ': \\textit{' + self._summary(doc, uid) + '}'
        str += '\n'
        if doc and doc.ispackage() and doc.modules():
            str += ' '*depth + '  \\begin{itemize}\n'
            str += ' '*depth + '\\setlength{\\parskip}{0.6ex}'
            modules = [l.target() for l in 
                       self._filtersort_links(doc.modules(), doc.sortorder())]
            for module in modules:
                str += self._module_tree_item(module, depth+4)
            str += ' '*depth + '  \\end{itemize}\n'
        return str

    def _module_tree(self, sortorder=None):
        """
        @return: The HTML code for the module hierarchy tree.  This is
            used by L{_trees_to_html} to construct the hiearchy page.
        @rtype: C{string}
        """
        str = '\\begin{itemize}\n'
        str += '\\setlength{\\parskip}{0.6ex}'
        uids = self._filtersort_uids(self._docmap.keys())
        #docs.sort(lambda a,b: cmp(a[0], b[0]))
        # Find all top-level packages. (what about top-level
        # modules?)
        for uid in uids:
            doc = self._docmap[uid]
            if not isinstance(doc, ModuleDoc): continue
            if not doc.package():
                str += self._module_tree_item(uid)
        return str +'\\end{itemize}\n'

    def _module_list(self, modules, sortorder):
        """
        @return: The HTML code for the module hierarchy tree,
            containing the given modules.  This is used by
            L{_module_to_html} to list the submodules of a package.
        @rtype: C{string}
        """
        if len(modules) == 0: return ''
        str = '\\textbf{Modules}\n'
        str += '\\begin{itemize}\n'
        str += '\\setlength{\\parskip}{0.6ex}'
        modules = self._filtersort_links(modules, sortorder)
        
        for link in modules:
            str += self._module_tree_item(link.target())
        return str + '\\end{itemize}\n\n'

    #////////////////////////////////////////////////////////////
    # Helpers
    #////////////////////////////////////////////////////////////

    def _index(self, uid, pos='only'):
        if uid.is_routine() and not self._index_functions: return ''

        str = ''
        u = uid
        while (u.is_routine() or u.is_class()):
            str = '!%s \\textit{(%s)}%s' % (self._text_to_latex(u.shortname()),
                               self._kind(u).lower(), str)
            u = u.parent()

        str = '%s \\textit{(%s)}%s' % (self._text_to_latex(u.name()),
                          self._kind(u).lower(), str)

        if pos == 'only': return '\\index{%s}\n' % str
        elif pos == 'start': return '\\index{%s|(}\n' % str
        elif pos == 'end': return '\\index{%s|)}\n' % str
        else:
            raise AssertionError('Bad index position %s' % pos)

    def _text_to_latex(self, str):
        # These get converted to \textbackslash later.
        str = str.replace('\\', '\0')
        
        # These elements need to be backslashed.
        str = re.sub(r'([#$&%_\${}])', r'\\\1', str)

        # These elements need to be in math mode.
        str = re.sub('([<>|])', r'\\(\1\\)', str)

        # These elements have special names.
        str = str.replace('^', '{\\textasciicircum}')
        str = str.replace('~', '{\\textasciitilde}')
        str = str.replace('\0', r'{\textbackslash}')
        
        return str

    def _header(self, where):
        str = '%\n% API Documentation'
        if self._prj_name: str += ' for %s' % self._prj_name
        if isinstance(where, UID):
            str += '\n%% %s %s' % (self._kind(where), where.name())
        else:
            str += '\n%% %s' % where
        str += '\n%%\n%% Generated by epydoc %s\n' % epydoc.__version__
        str += '%% [%s]\n%%\n' % time.asctime(time.localtime(time.time()))
        return str

    def _kind(self, uid):
        if uid.is_package(): return 'Package'
        elif uid.is_module(): return 'Module'
        elif uid.is_class(): return 'Class'
        elif uid.is_method() or uid.is_builtin_method(): return 'Method'
        elif uid.is_routine(): return 'Function'
        elif uid.is_variable(): return 'Variable'
        else: raise AssertionError, 'Bad UID type for _name'

    def _section(self, title, depth):
        sec = _SECTIONS[depth+self._top_section]
        return (('%s\n\n' % sec) % self._text_to_latex(title))                
    
    def _sectionstar(self, title, depth):
        sec = _STARSECTIONS[depth+self._top_section]
        return (('%s\n\n' % sec) % self._text_to_latex(title))

    def _start_of(self, section_name):
        str = '\n' + 75*'%' + '\n'
        str += '%%' + ((71-len(section_name))/2)*' '
        str += section_name
        str += ((72-len(section_name))/2)*' ' + '%%\n'
        str += 75*'%' + '\n\n'
        return str
                
    def _cmp_name(self, name1, name2):
        """
        Compare uid1 and uid2 by their names, using the following rules: 
          - C{'__init__'} < anything.
          - public < private.
          - otherwise, sort alphabetically by name (ignoring case)
    
        @return: -1 if C{uid1<uid2}; 0 if C{uid1==uid2}; and 1 if
            C{uid1>uid2}.
        @rtype: C{int}
        """
        if (name2 == '__init__'): return 1
        if (name1 == '__init__'): return -1
        if name1 == name2: return 0
        if self._is_private(name1) and not self._is_private(name2): return 1
        if self._is_private(name2) and not self._is_private(name1): return -1
        return cmp(name1.lower(), name2.lower())
    
    def _is_private(self, str):
        """
        @return: true if C{str} is the name of a private Python object.
        @rtype: C{boolean}
        """
        if str == '...': return 0
        for piece in str.split('.'):
            if piece[:1] == '_' and piece[-1:] != '_': return 1
        return 0

    def _filtersort_links(self, links, sortorder=None):
        """
        Sort and filter a list of C{Link}s.  If L{_show_private} is
        false, then filter out all private objects; otherwise, perform
        no filtering.

        @param links: The list of C{Link}s to be sorted and filtered.
        @type links: C{list} of L{Link}
        @param sortorder: A list of link names, typically generated
            from C{__epydoc__sort__}, and returned by
            L{ObjDoc.sortorder}.  Links whose name are in C{sortorder}
            are placed at the beginning of the sorted list, in the
            order that they appear in C{sortorder}.
        @type sortorder: C{list} of C{string}
        @return: The sorted list of links.
        @rtype: C{list} of L{Link}
        """
        # Filter out private objects.
        if not self._show_private:
            links = [l for l in links if not l.target().is_private()]
        else:
            links = list(links)

        # Check the sortorder.  If available, then use it to sort the
        # objects.
        if (type(sortorder) not in (type(()), type([]))):
            so_links = []
        else:
            if type(sortorder) == type(()): sortorder = list(sortorder)
            so_links = sortorder[:]
            for link in links:
                try: so_links[sortorder.index(link.name())] = link 
                except ValueError: continue
            so_links = [l for l in so_links if type(l) != type('')]
            for link in so_links: links.remove(link)

        # Sort any links not contained in sortorder.
        links.sort(lambda x,y,c=self._cmp_name: c(x.name(), y.name()))
        
        return so_links + links

    def _filtersort_uids(self, uids):
        """
        Sort and filter a list of C{UID}s.  If L{_show_private} is
        false, then filter out all private objects; otherwise, perform
        no filtering.

        @param uids: The list of C{UID}s to be sorted and filtered.
        @type uids: C{list} of L{UID}
        @return: The sorted list of UIDs.
        @rtype: C{list} of L{UID}
        """
        # Filter out private objects
        if not self._show_private:
            uids = [u for u in uids if not u.is_private()]

        # Sort and return the UIDs.
        uids.sort(lambda x,y,c=self._cmp_name: c(x.name(), y.name()))
        return uids

    def _filtersort_vars(self, vars, sortorder=None):
        """
        Sort and filter a list of C{Var}s.  If L{_show_private} is
        false, then filter out all private objects; otherwise, perform
        no filtering.

        @param vars: The list of C{Var}s to be sorted and filtered.
        @type vars: C{list} of L{Var}
        @param sortorder: A list of variable names, typically generated
            from C{__epydoc__sort__}, and returned by
            L{ObjDoc.sortorder}.  Vars whose name are in C{sortorder}
            are placed at the beginning of the sorted list, in the
            order that they appear in C{sortorder}.
        @type sortorder: C{list} of C{string}
        @return: The sorted list of variables.
        @rtype: C{list} of L{Var}
        """
        # Filter out private objects.
        if not self._show_private:
            vars = [v for v in vars if not v.uid().is_private()]
        else:
            vars = list(vars)

        # Check the sortorder.  If available, then use it to sort the
        # objects.
        if (type(sortorder) not in (type(()), type([]))):
            so_vars = []
        else:
            if type(sortorder) == type(()): sortorder = list(sortorder)
            so_vars = sortorder[:]
            for var in vars:
                try: so_vars[sortorder.index(var.name())] = var
                except ValueError: continue
            so_vars = [v for v in so_vars if type(v) != type('')]
            for var in so_vars: vars.remove(var)

        # Sort any variables not contained in sortorder.
        vars.sort(lambda x,y,c=self._cmp_name: c(x.name(), y.name()))
        
        return so_vars + vars

    def _descrlist(self, items, singular, plural=None, short=0):
        if plural is None: plural = singular
        if len(items) == 0: return ''
        if len(items) == 1:
            return '\\textbf{%s:} %s\n\n' % (singular, items[0])
        if short:
            str = '\\textbf{%s:}\n' % plural
            items = [item.strip() for item in items]
            return str + ',\n    '.join(items) + '\n\n'
        else:
            str = '\\textbf{%s:}\n' % plural
            str += '\\begin{quote}\n'
            str += '  \\begin{itemize}\n\n  \item '
            str += '    \\setlength{\\parskip}{0.6ex}'
            str += '\n\n  \item '.join(items)
            return str + '\n\n\\end{itemize}\n\n\\end{quote}\n\n'

    def _seealso(self, seealso, container):
        """
        @return: The LaTeX code for the see-also fields.
        """
        items = [self._dom_to_latex(s) for s in seealso]
        return self._descrlist(items, 'See also', short=1)
        
    def _author(self, authors, container):
        """
        @return: The LaTeX code for the author fields.
        """
        items = [self._dom_to_latex(a) for a in authors]
        return self._descrlist(items, 'Author', 'Authors', short=1)

    def _requires(self, requires, container):
        """
        @return: The LaTeX code for the requires field.
        """
        items = [self._dom_to_latex(r) for r in requires]
        return self._descrlist(items, 'Requires')
         
    def _warnings(self, warnings, container):
        """
        @return: The LaTeX code for the warnings field.
        """
        items = [self._dom_to_latex(r) for r in warnings]
        return self._descrlist(items, 'Warning', 'Warnings')

    def _subclasses(self, subclasses, container):
        """
        @return: The LaTeX code for the subclasses field.
        """
        items = [self._text_to_latex(sc.name()) for sc in subclasses]
        return self._descrlist(items, 'Known Subclasses', short=1)

    def _version(self, version, container):
        items = [self._dom_to_latex(version)]
        return self._descrlist(items, 'Version')
        
    def _summary(self, doc, container=None):
        """
        @return: The LATEX code for the summary description of the
            object documented by C{doc}.  A summary description is the
            first sentence of the C{doc}'s 'description' field.  If the
            C{doc} has no 'description' field, but does have a
            'return' field, then the summary is taken from the return
            field instead.
        @rtype: C{string}
        @param doc: The documentation for the object whose summary
            should be returned.
        @type doc: L{objdoc.ObjDoc}
        @param container: The container object for C{doc}, or C{None}
            if there is none.  This container object is used to
            resolve links (E{L}{...}) in the epytext.
        @type container: L{uid.UID}
        """
        descr = doc.descr()

        # Try to find a documented ancestor.
        if isinstance(doc, FuncDoc):
            while (not doc.documented() and doc.overrides() and
                   self._docmap.has_key(doc.overrides())):
                doc = self._docmap[doc.overrides()]

        if descr != None:
            str = self._dom_to_latex(epytext.summary(descr)).strip()
            #if str == '': str = '&nbsp;'
            return str
        elif (isinstance(doc, FuncDoc) and
              doc.returns().descr() is not None):
            summary = epytext.summary(doc.returns().descr())
            summary = self._dom_to_latex(summary).strip()
            summary = summary[:1].lower() + summary[1:]
            return ('Return '+ summary)
        else:
            return ''
            #return '&nbsp;'

if __name__ == '__main__':
    docmap = DocMap(document_bases=1)

    uids = [findUID(name) for name in sys.argv[1:]]
    uids = [uid for uid in uids if uid is not None]
    for uid in uids:
        print 'add', uid
        docmap.add(uid.value())

    formatter = LatexFormatter(docmap)
    formatter.dvi('latex_test')

