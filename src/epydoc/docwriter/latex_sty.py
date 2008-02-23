# -*- latex -*-
#
# epydoc.css: LaTeX stylesheets (*.sty) for epydoc's LaTeX writer
#
# $Id: html_css.py 1717 2008-02-14 22:21:41Z edloper $
#

"""
LaTeX stylesheets (*.sty) for epydoc's LaTeX writer.
"""

#: A disclaimer that is appended to the bottom of the BASE and
#: BOXES stylesheets.
NIST_DISCLAIMER = r"""
% This style file is a derivative work, based on a public domain style
% file that was originally developed at the National Institute of
% Standards and Technology by employees of the Federal Government in the
% course of their official duties.  NIST assumes no responsibility
% whatsoever for its use by other parties, and makes no guarantees,
% expressed or implied, about its quality, reliability, or any other
% characteristic.
"""

######################################################################
######################################################################
BASE = r"""
% epydoc-base.sty
%
% Authors: Jonathan Guyer <guyer@nist.gov>
%          Edward Loper <edloper@seas.upenn.edu>
% URL: <http://epydoc.sf.net>
%
% This LaTeX stylesheet defines the basic commands that are used by
% epydoc's latex writer (epydoc.docwriter.latex).  For more
% information, see the epydoc webpage.  This stylesheet accepts the
% following options:
%
%   - index: Include an index of defined objects.
%   - hyperlink: Create hyperlinks with the hyperref package.
%
% $Id:$

\NeedsTeXFormat{LaTeX2e}%
\ProvidesClass{epydoc}[2007/04/06 v3.0beta1 Epydoc Python Documentation]

% ======================================================================
% Basic Package Requirements

\RequirePackage{alltt, boxedminipage}
\RequirePackage{multirow, longtable, amssymb}
\RequirePackage[headings]{fullpage}
\RequirePackage[usenames]{color}
\RequirePackage{ifthen}

% ======================================================================
% Options

\newif\if@doIndex
\@doIndexfalse
\DeclareOption{index}{\@doIndextrue}

\newif\if@doHyperlink
\@doHyperlinkfalse
\DeclareOption{hyperlink}{\@doHyperlinktrue}

\ProcessOptions\relax

\@ifclassloaded{memoir}{%
    \RequirePackage[other,notbib]{tocbibind}
}{%
    \if@doIndex
        \RequirePackage{makeidx}
    \fi
    \RequirePackage{parskip}
    \RequirePackage{fancyhdr}
    \RequirePackage[other]{tocbibind}
    \pagestyle{fancy}
}

\if@doIndex
    \makeindex
\fi

% ======================================================================
% General Formatting

% Separate paragraphs by a blank line (do not indent them).  We define
% a new length variable. \EpydocParskip, for the paragraph-skip length.
% This needs to be assigned to \parskip here as well as inside several
% environments that reset \parskip (such as minipages).
\newlength{\EpydocParskip}
\newlength{\EpydocMetadataLongListParskip}
\setlength{\EpydocParskip}{0.6\baselineskip}
\setlength{\EpydocMetadataLongListParskip}{0.4\baselineskip}
\setlength{\parskip}{\EpydocParskip}
\setlength{\parindent}{0ex}

% Fix the heading position -- without this, the headings generated
% by the fancyheadings package sometimes overlap the text.
\setlength{\headheight}{16pt}
\setlength{\headsep}{24pt}
\setlength{\topmargin}{-\headsep}

% Display the section & subsection names in a header.
\renewcommand{\sectionmark}[1]{\markboth{#1}{}}
\renewcommand{\subsectionmark}[1]{\markright{#1}}

% Create a 'base class' length named EpydocBCL for use in base trees.
\newlength{\EpydocBCL} % base class length, for base trees.

% ======================================================================
% Hyperlinks & Crossreferences

% The \EpydocHypertarget command is used to mark targets that hyperlinks
% may point to.  It takes two arguments: a target label, and text
% contents.  (In some cases, the text contents will be empty.)  Target
% labels are formed by replacing '.'s in the name with ':'s.  The
% default stylesheet creates a \label for the target label, and displays
% the text.
\newcommand{\EpydocHypertarget}[2]{\label{#1}#2}

% The \EpydocHyperlink command is used to create a link to a given target.
% It takes two arguments: a target label, and text contents.  The
% default stylesheet just displays the text contents.
\newcommand{\EpydocHyperlink}[2]{#2}

% The \CrossRef command creates a cross-reference to a given target,
% including a pageref.  It takes one argument, a target label.
\newcommand{\CrossRef}[1]{\textit{(Section \ref{#1}, p.~\pageref{#1})}}

% If the [hyperlink] option is turned on, then enable hyperlinking.
\if@doHyperlink
  \renewcommand{\EpydocHyperlink}[2]{\hyperlink{#1}{#2}}
  \renewcommand{\EpydocHypertarget}[2]{\label{#1}\hypertarget{#1}{#2}}
\fi

% ======================================================================
% Index Terms

% The \EpydocIndex command is used to mark items that should be included
% in the index.  It takes one optional argument, specifying the 'kind'
% of the object, and one required argument, the term that should be
% included in the index.  (This command is used inside the \index
% command.)  kind can be Package, Script, Module, Class, Class Method,
% Static Method, Method, Function, or Variable.
\newcommand{\EpydocIndex}[2][]{%
    #2 %
    \ifthenelse{\equal{#1}{}}{}{\textit{(\MakeLowercase{#1})}}}
    
% ======================================================================
% Descriptions (docstring contents)

% All rendered markup derived from a docstring is wrapped in this
% environment.  By default, it simply sets the \parskip length
% to \EpydocParskip (in case an enclosing environment had reset
% it to its default value).
\newenvironment{EpydocDescription}{%
    \setlength{\parskip}{\EpydocParskip}%
  }{}

% This environment is used to mark the description for a class
% (which comes from the function's docstring).
\newenvironment{EpydocClassDescription}{%
  }{}

% This environment is used to mark the description for a module
% (which comes from the function's docstring).
\newenvironment{EpydocModuleDescription}{%
  }{}

% ======================================================================
% Python Source Code Syntax Highlighting.

% Color constants.
\definecolor{py@keywordcolor}{rgb}{1,0.45882,0}
\definecolor{py@stringcolor}{rgb}{0,0.666666,0}
\definecolor{py@commentcolor}{rgb}{1,0,0}
\definecolor{py@ps1color}{rgb}{0.60784,0,0}
\definecolor{py@ps2color}{rgb}{0.60784,0,1}
\definecolor{py@inputcolor}{rgb}{0,0,0}
\definecolor{py@outputcolor}{rgb}{0,0,1}
\definecolor{py@exceptcolor}{rgb}{1,0,0}
\definecolor{py@defnamecolor}{rgb}{1,0.5,0.5}
\definecolor{py@builtincolor}{rgb}{0.58039,0,0.58039}
\definecolor{py@identifiercolor}{rgb}{0,0,0}
\definecolor{py@linenumcolor}{rgb}{0.4,0.4,0.4}
\definecolor{py@inputcolor}{rgb}{0,0,0}

% Syntax Highlighting Commands
\newcommand{\pysrcprompt}[1]{\textcolor{py@ps1color}{\small\textbf{#1}}}
\newcommand{\pysrcmore}[1]{\textcolor{py@ps2color}{\small\textbf{#1}}}
\newcommand{\pysrckeyword}[1]{\textcolor{py@keywordcolor}{\small\textbf{#1}}}
\newcommand{\pysrcbuiltin}[1]{\textcolor{py@builtincolor}{\small\textbf{#1}}}
\newcommand{\pysrcstring}[1]{\textcolor{py@stringcolor}{\small\textbf{#1}}}
\newcommand{\pysrcdefname}[1]{\textcolor{py@defnamecolor}{\small\textbf{#1}}}
\newcommand{\pysrcother}[1]{\small\textbf{#1}}
\newcommand{\pysrccomment}[1]{\textcolor{py@commentcolor}{\small\textbf{#1}}}
\newcommand{\pysrcoutput}[1]{\textcolor{py@outputcolor}{\small\textbf{#1}}}
\newcommand{\pysrcexcept}[1]{\textcolor{py@exceptcolor}{\small\textbf{#1}}}

% ======================================================================
% Grouping

% This command is used to display group headers for objects that are in
% the same group (as specified by the epydoc @group field).  It is used
% within the Epydoc*List environments.  The definition provided here is
% the default definition, but several of the Epydoc*List environments
% use \renewcommand to provide definitions that are appropriate for the
% style of that environment.
\newcommand{\EpydocGroup}[1]{

    {\large #1}
    
    }

% ======================================================================
% Inheritance

% This command is used to display a list of objects that were inherited
% from a base class.  It expects two arguments: the base class name,
% and the list of inherited objects.  The definition provided here is
% the default definition, but several of the Epydoc*List environments
% use \renewcommand to provide definitions that are appropriate for the
% style of that environment.
\newcommand{\EpydocInheritanceList}[2]{%
    \textbf{Inherited from {#1}:} #2}
    
% ======================================================================
% Submodule List

% This list environment is used to list the submodules that are defined
% by a module.  Nested submodules are displayed using nested
% EpydocModuleList environments.  If the modules are divided into
% groups (with the epydoc @group field), then groups are displayed
% using the \EpydocModuleGroup command, followed by a nested
% EpydocModuleList.
\newenvironment{EpydocModuleList}{%
    \renewcommand{\EpydocGroup}[1]{\item[##1] \
    }
    \begin{itemize}
        \renewcommand{\makelabel}[1]{\textbf{##1}:} %
    \setlength{\parskip}{0ex}%
    }
    {\end{itemize}}

% ======================================================================
% Class List
%
% These environments are *only* used if the --list-classes-separately
% option is used.

% This list environment is used to list the classes that are defined 
% by a module.
\newenvironment{EpydocClassList}{%
    \renewcommand{\EpydocGroup}[1]{\item[##1] \
    }
    \begin{itemize}
        \renewcommand{\makelabel}[1]{\textbf{##1:}}
    \setlength{\parskip}{0ex}}
    {\end{itemize}}

% ======================================================================
% Function Lists

% The EpydocFunctionList environment is used to describe functions
% and methods.  It contains one \EpydocFunction command for each
% function or method.  This command takes eight required arguments:
%
%   - The function's signature: an EpydocFunctionSignature environment
%     specifying the signature for the function.
%
%   - The function's description (from the docstring)
% 
%   - The function's parameters: An EpydocFunctionParameters list 
%     environment providing descriptions of the function's parameters.
%     (from the epydoc @param, @arg, @kwarg, @vararg, @type fields)
%
%   - The function's return description (from the epydoc @rerturns field)
%
%   - The function's return type (from the epydoc @rtype field)
%
%   - The function's exceptions: An EpydocFunctionRaises list
%     environment describing exceptions that the function may raise
%     (from the epydoc @raises field)
%
%   - The function's override: An EpydocFunctionOverrides command
%     describing the method that this function overrides (if any)
%
%   - The function's metadata: Zero or more EpydocMetadata*
%     commands/environments, taken from metadata fields (eg @author)
%
% All arguments except for the first (the signature) may be empty.
%
\newenvironment{EpydocFunctionList}{%
    \newcommand{\EpydocFunction}[8]{
        \gdef\@EpydocFunctionSignature{##1}%
        \gdef\@EpydocFunctionDescription{##2}%
        \gdef\@EpydocFunctionParameters{##3}%
        \gdef\@EpydocFunctionReturnDescr{##4}%
        \gdef\@EpydocFunctionReturnType{##5}%
        \gdef\@EpydocFunctionRaises{##6}%
        \gdef\@EpydocFunctionOverrides{##7}%
        \gdef\@EpydocFunctionMetadata{##8}%
    {\Large\raggedright\@EpydocFunctionSignature}

    \begin{quote}%
        \setlength{\parskip}{\EpydocParskip}%
        \ifx\@EpydocFunctionDescription\empty\else

            \@EpydocFunctionDescription\fi%
        \ifx\@EpydocFunctionParameters\empty\else

            \@EpydocFunctionParameters\fi%
        \ifx\@EpydocFunctionReturnDescr\empty

            \@EpydocFunctionReturnDescr\fi%
        \ifx\@EpydocFunctionReturnType\empty

            \@EpydocFunctionReturnType\fi%
        \ifx\@EpydocFunctionRaises\empty\else

            \@EpydocFunctionRaises\fi%
        \ifx\@EpydocFunctionOverrides\empty\else

            \@EpydocFunctionOverrides\fi%
        \ifx\@EpydocFunctionMetadata\empty\else

            \@EpydocFunctionMetadata\fi%
    \end{quote}

  }}
  {}

% The EpydocFunctionSignature environment is used to display a
% function's signature.  It expects one argument, the function's
% name.  The body of the environment contains the parameter list.
% The following commands are used in the parameter list, to mark
% individual parameters:
%
%   - \Param: Takes one required argument (the parameter name) and
%     one optional argument (the defaultt value).
%   - \VarArg: Takes one argument (the varargs parameter name)
%   - \KWArg: Takes one argument (the keyword parameter name)
%   - \GenericArg: Takes no arguments (this is used for '...', e.g.
%     when the signature is unknown).
%   - \TupleArg: Used inside of the \Param command, to mark
%     argument tuples.  Individual elements of the argument tuple
%     are separated by the \and command.
% 
% Parameters are separated by the \and command.
\newenvironment{EpydocFunctionSignature}[1]{%
    \newcommand{\and}{, }%
    \newcommand{\VarArg}[1]{*\textit{##1}}%
    \newcommand{\GenericArg}{\textit{\ldots}}%
    \newcommand{\KWArg}[1]{**\textit{##1}}%
    \newcommand{\TupleArg}[1]{(##1)}%
    \newcommand{\Param}[2][]{%
        \textit{##2}%
        \ifthenelse{\equal{##1}{}}{}{=\texttt{##1}}}%
    \textbf{#1}(%
    }{)}

% The EpydocFunctionParameters environment is used to display 
% descriptions for the parameters that a function can take.
% (From epydoc fields: @param, @arg, @kwarg, @vararg, @type)
\newenvironment{EpydocFunctionParameters}[1]{%
    \textbf{Parameters}
    \vspace{-\EpydocParskip}
    \begin{quote}
    \begin{list}{}{%
      \renewcommand{\makelabel}[1]{\texttt{##1:}\hfil}%
      \settowidth{\labelwidth}{\texttt{#1:}}%
      \setlength{\leftmargin}{\labelsep}%
      \addtolength{\leftmargin}{\labelwidth}}}%
    {\end{list}
    \end{quote}
    }

% This environment is used to display descriptions of exceptions
% that can be raised by a function.  (From epydoc field: @raise)
\newenvironment{EpydocFunctionRaises}{%
    \renewcommand*{\descriptionlabel}[1]{\hspace\labelsep
       \normalfont\itshape ##1}
    \textbf{Raises}
    \vspace{-\EpydocParskip}%
    \begin{quote}%
        \begin{description}%
    }
    {\end{description}
    \end{quote}
    }

% This environment is used when a method overrides a base class
% method, to display the name of the overridden method.
\newcommand{\EpydocFunctionOverrides}[2][0]{%
    \textbf{Overrides:} #2 %
    \ifthenelse{#1=1}{\textit{(inherited documentation)}{}}

    }

% ======================================================================
% Variable Lists
%
% There are three separate variable list environments:
%   - EpydocVariableList............ for a module's variables
%   - EpydocInstanceVariableList.... for a class's instance variables
%   - EpydocClassVariableList....... for a class's class variables

% The EpydocVariableList environment is used to describe module
% variables.  It contains one \EpydocVariable command for each
% variable.  This command takes four required arguments:
% 
%   - The variable's name
%   - The variable's description (from the docstring)
%   - The variable's type (from the epydoc @type field)
%   - The variable's value
%
% If any of these arguments is not available, then the empty
% string will be used.
%
% See EpydocGeneralList, above, for info about the commands
% \EpydocInternalHeader and \EpydocInheritanceItemList, which
% may be used inside the EpydocVariableList environment.
\newenvironment{EpydocVariableList}{%
    \newcommand{\EpydocVariable}[4]{%
        \gdef\@EpydocVariableName{##1}%
        \gdef\@EpydocVariableDescription{##2}%
        \gdef\@EpydocVariableType{##3}%
        \gdef\@EpydocVariableValue{##4}%
    {\Large\raggedright\@EpydocVariableName}

    \begin{quote}
        \setlength{\parskip}{\EpydocParskip}%
        \ifx\@EpydocVariableDescription\empty\else

            \@EpydocVariableDescription\fi%
        \ifx\@EpydocVariableType\empty\else

            \textbf{Type:} \@EpydocVariableType\fi%
        \ifx\@EpydocVariableValue\empty

            \textbf{Value:} \texttt{\@EpydocVariableValue}\fi%
    \end{quote}
  }}
  {}

% The EpydocClassVariableList environment is used the same way as
% the EpydocVariableList environment (shown above).
\newenvironment{EpydocClassVariableList}{%
    \begin{EpydocVariableList}}
    {\end{EpydocVariableList}}

% The EpydocClassVariableList environment is used the same way as
% the EpydocVariableList environment (shown above).
\newenvironment{EpydocInstanceVariableList}{%
    \begin{EpydocVariableList}}
    {\end{EpydocVariableList}}

% ======================================================================
% Property Lists

% The EpydocPropertyList environment is used to describe class
% properties.  It contains one \EpydocProperty command for each
% property.  This command takes six required arguments:
% 
%   - The property's name
%   - The property's description (from the docstring)
%   - The property's type (from the epydoc @type field)
%   - The property's fget function
%   - The property's fset function
%   - The property's fdel function
%
% If any of these arguments is not available, then the empty
% string will be used.
%
% See EpydocGeneralList, above, for info about the commands
% \EpydocInternalHeader and \EpydocInheritanceItemList, which
% may be used inside the EpydocVariableList environment.
%
% Implementation node: \@EpydocSeparator evaluates to nothing on
% the first use, and to a paragraph break on subsequent uses.
\newenvironment{EpydocPropertyList}{%
    \newcommand{\EpydocProperty}[6]{%
        \gdef\@EpydocPropertyName{##1}%
        \gdef\@EpydocPropertyDescription{##2}%
        \gdef\@EpydocPropertyType{##3}%
        \gdef\@EpydocPropertyGet{##4}%
        \gdef\@EpydocPropertySet{##5}%
        \gdef\@EpydocPropertyDel{##6}%
    {\Large\raggedright\@EpydocVariableName}

    \begin{quote}
        \setlength{\parskip}{\EpydocParskip}%
        \ifx\@EpydocVariableDescription\empty\else

            \@EpydocVariableDescription\fi%
        \ifx\@EpydocVariableType\empty\else

            \textbf{Type:} \@EpydocVariableType\fi%
        \ifx\@EpydocVariableGet\empty

            \textbf{Get:} \texttt{\@EpydocVariableGet}\fi%
        \ifx\@EpydocVariableSet\empty

            \textbf{Set:} \texttt{\@EpydocVariableSet}\fi%
        \ifx\@EpydocVariableDel\empty

            \textbf{Delete:} \texttt{\@EpydocVariableDel}\fi%
    \end{quote}
  }}
  {}

% ======================================================================
% Metadata

% This command is used to display a metadata field with a single value
\newcommand{\EpydocMetadataSingleValue}[2]{%
    \begin{list}{}{\itemindent-\leftmargin}
    \item \textbf{#1:} #2
    \end{list}
  }

% This environment is used to display a metadata field with multiple
% values when the field declares that short=True; i.e., that multiple
% values should be combined into a single comma-delimited list.
\newenvironment{EpydocMetadataShortList}[1]{%
    \newcommand{\and}{, }%
    \textbf{#1: }}
    {}

% This list environment is used to display a metadata field with
% multiple values when the field declares that short=False; i.e., that
% multiple values should be listed separately in a bulleted list.
\newenvironment{EpydocMetadataLongList}[1]{%
    \textbf{#1:}
    \setlength{\parskip}{0ex}
        \begin{itemize}
            \setlength{\parskip}{\EpydocMetadataLongListParskip}}
    {\end{itemize}}

% ======================================================================
% reStructuredText Admonitions

% This environment is used to display reStructuredText admonitions,
% such as ``..warning::'' and ``..note::''.
\newenvironment{reSTadmonition}[1][]{%
    \begin{center}\begin{sffamily}
        \begin{lrbox}{\@tempboxa}
            \begin{minipage}{\admonitionwidth}
                \textbf{\large #1}
                \vspace{2mm}
    }
    {
        \end{minipage}
    \end{lrbox}
    \fbox{\usebox{\@tempboxa}}
    \end{sffamily}
    \end{center}
    }

% ======================================================================
% Name Formatting    
%
% This section defines the EpydocDottedName command, which is used to
% display the names of Python objects.

% Allows non-hyphenated wrapping at the '.' module separators.  The
% rest is a simplified version of url.sty's tt style.
\RequirePackage{url}
\def\Url@pydo{% style assignments for tt fonts or T1 encoding
\def\UrlBreaks{\do\]\do\)\do\_}%
\def\UrlBigBreaks{\do@url@hyp\do\.}%
% \def\UrlNoBreaks{\do\(\do\[\do\{\do\<\do\_}% (unnecessary)
\def\UrlNoBreaks{\do\(\do\[\do\{\do\<}% (unnecessary)
\def\UrlSpecials{\do\ {\ }}%
\def\UrlOrds{\do\*\do\-\do\~}% any ordinary characters that aren't usually
}

\def\url@pystyle{%
\@ifundefined{selectfont}{\def\UrlFont{\rm}}{\def\UrlFont{\rmfamily}}\Url@pydo
}
\newcommand\pymodule{\begingroup \urlstyle{py}\Url}

% The \EpydocDottedName command is used to escape dotted names.  In
% particular, it escapes underscores (_) and allows non-hyphenated
% wrapping at '.' separator characters.
\newcommand\EpydocDottedName[1]{\texorpdfstring{\protect\pymodule{#1}}{#1}}
"""+NIST_DISCLAIMER
######################################################################
######################################################################

######################################################################
######################################################################
BOXES = r"""
% epydoc-boxes.sty
%
% Authors: Jonathan Guyer <guyer@nist.gov>
%          Edward Loper <edloper@seas.upenn.edu>
% URL: <http://epydoc.sf.net>
%
% This LaTeX stylesheet (nearly) replicates the LaTeX output style
% generated by epydoc 3.0.  Function lists are displayed using
% a boxedminipage for each function.  Variable and Property lists
% are displayed using a longtable, with a row for each object.
%
% $Id:$
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{epydoc}[2007/04/06 v3.0beta1 Epydoc Python Documentation]
\DeclareOption{index}{\PassOptionsToPackage{index}{epydoc-default}}
\DeclareOption{hyperlink}{\PassOptionsToPackage{hyperlink}{epydoc-default}}
\ProcessOptions\relax

\RequirePackage{epydoc-default}

% Double the standard size boxedminipage outlines.
\setlength{\fboxrule}{2\fboxrule}

% ======================================================================
% Function Lists

% Put the function inside a boxedminipage.  Use a horizontal rule to
% separate the signature from the description elements.  Implementation
% note: the \@EpydocSeparator command adds a horizontal rule the first
% time it is called, and does nothing when called after that.
\renewenvironment{EpydocFunctionList}{%
    \def\@EpydocSeparator{%
       \vspace{-2\EpydocParskip}
       \rule{\dimexpr \textwidth-2\fboxsep \relax}{0.5\fboxrule}
       \aftergroup\def\aftergroup\@EpydocSeparator%
             \aftergroup{\aftergroup}}%
    \newcommand{\EpydocFunction}[8]{
        \gdef\@EpydocFunctionSignature{##1}%
        \gdef\@EpydocFunctionDescription{##2}%
        \gdef\@EpydocFunctionParameters{##3}%
        \gdef\@EpydocFunctionReturnDescr{##4}%
        \gdef\@EpydocFunctionReturnType{##5}%
        \gdef\@EpydocFunctionRaises{##6}%
        \gdef\@EpydocFunctionOverrides{##7}%
        \gdef\@EpydocFunctionMetadata{##8}%
    \begin{boxedminipage}{\dimexpr \textwidth-2\fboxsep \relax}
        {\Large \@EpydocFunctionSignature}
        \setlength{\parskip}{\EpydocParskip}%
        
        \ifx\@EpydocFunctionDescription\empty\else%
            {\@EpydocSeparator}%
            \@EpydocFunctionDescription %
        \fi%
        \ifx\@EpydocFunctionParameters\empty\else%
            {\@EpydocSeparator}%
            \@EpydocFunctionParameters %
        \fi%
        \ifx\@EpydocFunctionReturnType\empty%
            \ifx\@EpydocFunctionReturnDescr\empty\else%
                {\@EpydocSeparator}%
                \textbf{Return Value}%
                \vspace{-\EpydocParskip}%
                \begin{quote}\@EpydocFunctionReturnDescr\end{quote}%
            \fi%
        \else%
            {\@EpydocSeparator}%
            \textbf{Return Value}%
            \vspace{-\EpydocParskip}%
            \ifx\@EpydocFunctionReturnDescr\empty%
                \begin{quote}\it \@EpydocFunctionReturnType\end{quote}%
            \else%
                \begin{quote}\@EpydocFunctionReturnDescr%
                    \textit{(type=\@EpydocFunctionReturnType)}\end{quote}%
            \fi%
        \fi%
        \ifx\@EpydocFunctionRaises\empty\else%
            {\@EpydocSeparator}%
            \@EpydocFunctionRaises %
        \fi%
        \ifx\@EpydocFunctionOverrides\empty\else%
            {\@EpydocSeparator}%
            \@EpydocFunctionOverrides %
        \fi%
        \ifx\@EpydocFunctionMetadata\empty\else%
            {\@EpydocSeparator}%
            \@EpydocFunctionMetadata %
        \fi%
    \end{boxedminipage}

  }}
  {}

% ======================================================================
% Multi-Page List (used to define EpydocVariableList etc)

% [xx] \textwidth is not the right size for the multicolumn..

% Define a base environment that we will use to put variable &
% property lists in a longtable.  This environment sets up the
% longtable environment, and redefines the \EpydocGroup and
% \EpydocInheritanceList commands to add a row to the table.
\newenvironment{@EpydocGeneralList}{%
    \renewcommand{\EpydocGroup}[1]{%
        \multicolumn{2}{|l|}{\textbf{##1}} \\
         \hline}%
    \renewcommand{\EpydocInheritanceList}[2]{%
        \multicolumn{2}{|p{\dimexpr \textwidth -4\tabcolsep-3\arrayrulewidth}|}{%
            \raggedright\textbf{Inherited from {##1}:\\
            ##2}} \\
        \hline}
    \begin{longtable}{|p{.30\textwidth}|p{.62\textwidth}|}
    % Set up the headers & footer (this makes the table span
    % multiple pages in a happy way).
    \hline 
    \centering \textbf{Name} & \centering \textbf{Description} 
    \tabularnewline
    \hline
    \endhead\hline\multicolumn{2}{r}{%
        \small\textit{continued on next page}}\\\endfoot\hline
    \endlastfoot}
    {\end{longtable}}

% ======================================================================
% Variable Lists

\renewenvironment{EpydocVariableList}{%
    \newcommand{\EpydocVariable}[4]{%
        \gdef\@EpydocVariableName{##1}%
        \gdef\@EpydocVariableDescription{##2}%
        \gdef\@EpydocVariableType{##3}%
        \gdef\@EpydocVariableValue{##4}%
        \raggedright \@EpydocVariableName & %
        \setlength{\parskip}{\EpydocParskip}\raggedright%
        \@EpydocVariableDescription %
        \ifx\@EpydocVariableValue\empty\relax%
            \ifx\@EpydocVariableType\empty\else%
                \ifx\@EpydocVariableDescription\empty\else

                \fi%
                \textit{(type=\texttt{\@EpydocVariableType})}%
            \fi%
        \else\relax%
            \ifx\@EpydocVariableDescription\empty\else

            \fi%
            \textbf{Value:} \texttt{\@EpydocVariableValue}%
            \ifx\@EpydocVariableType\empty\else%
                \textit{(type=\texttt{\@EpydocVariableType})}%
            \fi%
        \fi%
        \tabularnewline
        \hline}
    \begin{@EpydocGeneralList}}
    {\end{@EpydocGeneralList}}

% By default, EpydocClassVariableList & EpydocInstanceVariableList are 
% just aliases for EpydocVaribleList.

% ======================================================================
% Property Lists

\renewenvironment{EpydocPropertyList}{%
    \def\@EpydocSeparator{%
       \aftergroup\def\aftergroup\@EpydocSeparator\aftergroup{%
       \aftergroup\\\aftergroup[\aftergroup\EpydocParskip\aftergroup]%
       \aftergroup}}%
    \newcommand{\EpydocProperty}[6]{%
        \gdef\@EpydocPropertyName{##1}%
        \gdef\@EpydocPropertyDescription{##2}%
        \gdef\@EpydocPropertyType{##3}%
        \gdef\@EpydocPropertyGet{##4}%
        \gdef\@EpydocPropertySet{##5}%
        \gdef\@EpydocPropertyDel{##6}%
        \raggedright \@EpydocPropertyName & %
        \setlength{\parskip}{\EpydocParskip}\raggedright%
        \ifx\@EpydocPropertyDescription\empty\else%
            {\@EpydocSeparator}%
            \@EpydocPropertyDescription %
        \fi%
        \ifx\@EpydocPropertyType\empty\else%
            {\@EpydocSeparator}%
            \textbf{Type:} \@EpydocPropertyType
        \fi%
        \ifx\@EpydocPropertyGet\empty\else%
            {\@EpydocSeparator}%
            \textbf{Get:} \@EpydocPropertyGet%
        \fi%
        \ifx\@EpydocPropertySet\empty\else%
            {\@EpydocSeparator}%
            \textbf{Set:} \@EpydocPropertySet%
        \fi%
        \ifx\@EpydocPropertyDel\empty\else%
            {\@EpydocSeparator}%
            \textbf{Delete:} \@EpydocPropertyDel%
        \fi%
        \tabularnewline
        \hline}
    \begin{@EpydocGeneralList}}
    {\end{@EpydocGeneralList}}
"""+NIST_DISCLAIMER
######################################################################
######################################################################


######################################################################
######################################################################
SHADED = r"""
% epydoc-shaded.sty
%
% Authors: Jonathan Guyer <guyer@nist.gov>
%          Edward Loper <edloper@seas.upenn.edu>
% URL: <http://epydoc.sf.net>
%
% This LaTeX stylesheet for epydoc's output uses shaded boxes to
% display the function, variable, and property lists.  Each
% object's name (or signature) is displayed in a lightly shaded
% box, and is immediately followed by a shaded and indented box 
% containing a description of that object:
%
%         +-------------------------------------------+
%         | object's name                             |
%         +-------------------------------------------+
%             | description of the object             |
%             | ...                                   |
%             +---------------------------------------+
%
% $Id:$
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{epydoc}[2007/04/06 v3.0beta1 Epydoc Python Documentation]
\DeclareOption{index}{\PassOptionsToPackage{index}{epydoc-default}}
\DeclareOption{hyperlink}{\PassOptionsToPackage{hyperlink}{epydoc-default}}
\ProcessOptions\relax

\RequirePackage{epydoc-default}

\definecolor{gray95}{gray}{0.95}
\definecolor{gray90}{gray}{0.90}
\definecolor{gray85}{gray}{0.85}
\definecolor{gray80}{gray}{0.8}
\definecolor{gray55}{gray}{0.55}

% adapted from <http://www.texnik.de/color/color.phtml> for colored 
% paragraph boxes
\newcommand{\cmcolor}{}
\newenvironment{cminipage}[2][gray90]%
  {%
   \renewcommand{\cmcolor}{#1}%
   \begin{lrbox}{\@tempboxa}%
     \begin{minipage}{#2}}%
  {  \end{minipage}%
   \end{lrbox}%
   \colorbox{\cmcolor}{\usebox{\@tempboxa}}
   }%

\renewenvironment{EpydocFunctionList}{%
    \newcommand{\EpydocFunction}[8]{
        \gdef\@EpydocFunctionSignature{##1}%
        \gdef\@EpydocFunctionDescription{##2}%
        \gdef\@EpydocFunctionParameters{##3}%
        \gdef\@EpydocFunctionReturnDescr{##4}%
        \gdef\@EpydocFunctionReturnType{##5}%
        \gdef\@EpydocFunctionRaises{##6}%
        \gdef\@EpydocFunctionOverrides{##7}%
        \gdef\@EpydocFunctionMetadata{##8}%
    \newif\if@EpydocFunctionDetails%
    \@EpydocFunctionDetailsfalse%
    \ifx\@EpydocFunctionDescription\empty\else\@EpydocFunctionDetailstrue\fi%
    \ifx\@EpydocFunctionParameters\empty\else\@EpydocFunctionDetailstrue\fi%
    \ifx\@EpydocFunctionReturnDescr\empty\else\@EpydocFunctionDetailstrue\fi%
    \ifx\@EpydocFunctionReturnType\empty\else\@EpydocFunctionDetailstrue\fi%
    \ifx\@EpydocFunctionRaises\empty\else\@EpydocFunctionDetailstrue\fi%
    \ifx\@EpydocFunctionOverrides\empty\else\@EpydocFunctionDetailstrue\fi%
    \ifx\@EpydocFunctionMetadata\empty\else\@EpydocFunctionDetailstrue\fi%
    \vspace{0.5ex}
    \begin{minipage}{\textwidth}%
      \raggedleft%
      \begin{cminipage}[gray95]{\dimexpr \textwidth-2\fboxsep \relax}
        {\Large \@EpydocFunctionSignature}
      \end{cminipage}%
      \if@EpydocFunctionDetails
        \begin{cminipage}{\dimexpr 0.95\linewidth-2\fboxsep \relax}%
        \setlength{\parskip}{\EpydocParskip}%
          \setlength{\parskip}{\EpydocParskip}%
          
          \ifx\@EpydocFunctionDescription\empty\else%
              \@EpydocFunctionDescription %
          \fi%
          \ifx\@EpydocFunctionParameters\empty\else%
              \@EpydocFunctionParameters %
          \fi%
          \ifx\@EpydocFunctionReturnType\empty%
              \ifx\@EpydocFunctionReturnDescr\empty\else%
                  \textbf{Return Value}%
                  \vspace{-\EpydocParskip}%
                  \begin{quote}\@EpydocFunctionReturnDescr\end{quote}%
              \fi%
          \else%
              \textbf{Return Value}%
              \vspace{-\EpydocParskip}%
              \ifx\@EpydocFunctionReturnDescr\empty%
                  \begin{quote}\it \@EpydocFunctionReturnType\end{quote}%
              \else%
                  \begin{quote}\@EpydocFunctionReturnDescr%
                      \textit{(type=\@EpydocFunctionReturnType)}\end{quote}%
              \fi%
          \fi%
          \ifx\@EpydocFunctionRaises\empty\else%
              \@EpydocFunctionRaises %
          \fi%
          \ifx\@EpydocFunctionOverrides\empty\else%
              \@EpydocFunctionOverrides %
          \fi%
          \ifx\@EpydocFunctionMetadata\empty\else%
              \@EpydocFunctionMetadata %
          \fi%
        \end{cminipage}%
      \fi%
    \end{minipage}

  }}
  {}
    
\newenvironment{@EpydocGeneralList}{%
  \renewcommand{\EpydocGroup}[1]{
  
    \begin{cminipage}[gray80]{\dimexpr \linewidth-2\fboxsep \relax}
      {\Large\bf\center ##1\\}
    \end{cminipage}

  }%
  \renewcommand{\EpydocInheritanceList}[2]{%
    \begin{cminipage}[gray95]{\dimexpr \textwidth-2\fboxsep \relax}
    Inherited from {##1}: ##2%
    \end{cminipage}%
  
  }}{}
  
\newlength{\EpydocValueWidth}

\renewenvironment{EpydocVariableList}{%
  \newcommand{\EpydocVariable}[4]{
    \gdef\@EpydocVariableName{##1}%
    \gdef\@EpydocVariableDescription{##2}%
    \gdef\@EpydocVariableType{##3}%
    \gdef\@EpydocVariableValue{##4}%
    \begin{minipage}{\linewidth}%
    \raggedleft%
    \begin{cminipage}[gray95]{\dimexpr \textwidth-2\fboxsep \relax}
      {\Large \@EpydocVariableName}%
    \end{cminipage}%
    \newif\if@EpydocVariableDetails
    \@EpydocVariableDetailsfalse
    \ifx\@EpydocVariableDescription\empty\else \@EpydocVariableDetailstrue\fi%
    \ifx\@EpydocVariableType\empty\else \@EpydocVariableDetailstrue\fi%
    \ifx\@EpydocVariableValue\empty\else \@EpydocVariableDetailstrue\fi%
    \if@EpydocVariableDetails
      \begin{cminipage}{\dimexpr 0.95\linewidth-2\fboxsep \relax}
        \ifx\@EpydocVariableDescription\empty\else
        
            \@EpydocVariableDescription
        \fi%
        \ifx\@EpydocVariableType\empty\else
        
            \textbf{Type:} \texttt{\@EpydocVariableType}
        \fi%
        \ifx\@EpydocVariableValue\empty\else
        
          \settowidth{\EpydocValueWidth}{Value:w}%
          Value:
          \begin{cminipage}[gray85]{\dimexpr \textwidth-2\fboxsep-\EpydocValueWidth \relax}
            \texttt{\@EpydocVariableValue}
          \end{cminipage}%
        \fi%
      \end{cminipage}%
    \fi%
    \end{minipage}%

    }
    \begin{@EpydocGeneralList}}
    {\end{@EpydocGeneralList}}

\renewenvironment{EpydocPropertyList}{%
  \newcommand{\EpydocProperty}[6]{%
    \gdef\@EpydocPropertyName{##1}%
    \gdef\@EpydocPropertyDescription{##2}%
    \gdef\@EpydocPropertyType{##3}%
    \gdef\@EpydocPropertyGet{##4}%
    \gdef\@EpydocPropertySet{##5}%
    \gdef\@EpydocPropertyDel{##6}%
    \begin{minipage}{\linewidth}%
    \raggedleft%
    \begin{cminipage}[gray95]{\dimexpr \textwidth-2\fboxsep \relax}
      {\Large \@EpydocPropertyName}%
    \end{cminipage}%
    \newif\if@EpydocPropertyDetails
    \@EpydocPropertyDetailsfalse
    \ifx\@EpydocPropertyDescription\empty\else \@EpydocPropertyDetailstrue\fi%
    \ifx\@EpydocPropertyType\empty\else \@EpydocPropertyDetailstrue\fi%
    \ifx\@EpydocPropertyGet\empty\else \@EpydocPropertyDetailstrue\fi%
    \ifx\@EpydocPropertySet\empty\else \@EpydocPropertyDetailstrue\fi%
    \ifx\@EpydocPropertyDel\empty\else \@EpydocPropertyDetailstrue\fi%
    \if@EpydocPropertyDetails
      \begin{cminipage}{\dimexpr 0.95\linewidth-2\fboxsep \relax}
        \ifx\@EpydocPropertyDescription\empty\else%
        
            \@EpydocPropertyDescription
        \fi%
        \ifx\@EpydocPropertyType\empty\else
        
            \textbf{Type:} \@EpydocPropertyType
        \fi%
        \ifx\@EpydocPropertyGet\empty\else
        
            \textbf{Get:} \@EpydocPropertyGet%
        \fi%
        \ifx\@EpydocPropertySet\empty\else
        
            \textbf{Set:} \@EpydocPropertySet%
        \fi%
        \ifx\@EpydocPropertyDel\empty\else
        
            \textbf{Delete:} \@EpydocPropertyDel%
        \fi%
      \end{cminipage}%
      \fi%
    \end{minipage}%

    }
    \begin{@EpydocGeneralList}}
    {\end{@EpydocGeneralList}}

\renewcommand{\EpydocGroup}[1]{

  \begin{cminipage}[gray80]{\dimexpr \linewidth-2\fboxsep \relax}
    {\Large\bf\center #1\\}
  \end{cminipage}

  }

% This is just like the default definitions, except that we use
% \raggedright, and dedent by \EpydocSectionHeaderDedent
\newlength{\EpydocSectionHeaderDedent}
\setlength{\EpydocSectionHeaderDedent}{1cm}
\renewcommand\section{\@startsection {section}{1}%
              {-\EpydocSectionHeaderDedent}%
              {-3.5ex \@plus -1ex \@minus -.2ex}%
              {2.3ex \@plus.2ex}%
              {\raggedright\normalfont\Large\bfseries}}
\renewcommand\subsection{\@startsection{subsection}{2}%
              {-\EpydocSectionHeaderDedent}%
              {-3.25ex\@plus -1ex \@minus -.2ex}%
              {1.5ex \@plus .2ex}%
              {\raggedright\normalfont\large\bfseries}}
\renewcommand\subsubsection{\@startsection{subsubsection}{3}%
              {-\EpydocSectionHeaderDedent}%
              {-3.25ex\@plus -1ex \@minus -.2ex}%
              {1.5ex \@plus .2ex}%
              {\raggedright\normalfont\normalsize\bfseries}}
"""

############################################################
## Stylesheet table
############################################################

STYLESHEETS = {
    'base': BASE,
    'boxes': BOXES,
    'shaded': SHADED,
    'default': BOXES,
}
