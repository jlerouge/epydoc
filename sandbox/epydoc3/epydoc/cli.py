# epydoc -- Command line interface
#
# Copyright (C) 2005 Edward Loper
# Author: Edward Loper <edloper@loper.org>
# URL: <http://epydoc.sf.net>
#
# $Id$

"""
Command-line interface for epydoc.

[xx] this usage message is probably a little out-of-date.

Usage::

 epydoc [OPTIONS] MODULES...
 
     MODULES...                The Python modules to document.
     --html                    Generate HTML output (default).
     --latex                   Generate LaTeX output.
     --pdf                     Generate pdf output, via LaTeX.
     --check                   Run documentation completeness checks.
     -o DIR, --output DIR      The output directory.
     -n NAME, --name NAME      The documented project's name.
     -u URL, --url URL         The documented project's url.
     -t PAGE, --top PAGE       The top page for the HTML documentation.
     -c SHEET, --css SHEET     CSS stylesheet for HTML files.
     --private-css SHEET       CSS stylesheet for private objects.
     --inheritance STYLE       The format for showing inherited objects.
     --encoding ENCODING       Output encoding for HTML files (default: utf-8).
     -V, --version             Print the version of epydoc.
     -h, -?, --help, --usage   Display a usage message.
     -h TOPIC, --help TOPIC    Display information about TOPIC (docformat,
                               css, inheritance, usage, or version).

 Run \"epydoc --help\" for a complete option list.
 See the epydoc(1) man page for more information.

@todo: By default, don't list markup warnings as you find them; just
keep track of whether any occur, and if so, then tell the user that
they occured and that they can use some switch to view them.  Perhaps
just increase the verbosity level?  I.e., the default verbosity level
would hide them.  So verbosity levels would be...
               Progress    Markup warnings   Errors/other warnings
-2               none            no                 no
-1               none            no                 yes
 0 (default)     bar             no                 yes
 1               bar             yes                yes
 2               bars            yes                yes
 3               list            yes                yes


"""

import sys, os
from optparse import OptionParser, OptionGroup
import epydoc
from epydoc.driver import DocBuilder
from epydoc.docwriter.html import HTMLWriter
from epydoc import log
from epydoc.util import wordwrap
from epydoc.apidoc import UNKNOWN

######################################################################
## Argument Parsing
######################################################################

def parse_arguments(args):
    # Construct the option parser.
    usage = '%prog ACTION [options] NAMES...'
    version = "Epydoc, version %s" % epydoc.__version__
    optparser = OptionParser(usage=usage, version=version)
    action_group = OptionGroup(optparser, 'Actions')
    options_group = OptionGroup(optparser, 'Options')

    # Add options -- Actions
    action_group.add_option(                                # --html
        "--html", action="store_const", dest="action", const="html",
        help="Write HTML output.")
    action_group.add_option(                                # --latex
        "--latex", action="store_const", dest="action", const="latex",
        help="Write LaTeX output. (not implemented yet)")
    action_group.add_option(                                # --dvi
        "--dvi", action="store_const", dest="action", const="dvi",
        help="Write DVI output. (not implemented yet)")
    action_group.add_option(                                # --ps
        "--ps", action="store_const", dest="action", const="ps",
        help="Write Postscript output. (not implemented yet)")
    action_group.add_option(                                # --pdf
        "--pdf", action="store_const", dest="action", const="pdf",
        help="Write PDF output. (not implemented yet)")
    action_group.add_option(                                # --check
        "--check", action="store_const", dest="action", const="check",
        help="Check completeness of docs. (not implemented yet)")

    # Options I haven't ported over yet are...
    # separate-classes (??) -- for latex only
    # command-line-order (??)
    # ignore-param-mismatch -- not implemented yet, but will be related
    #                          to DocInheriter
    # tests=...
    # --no-markup-warnings ?
    # --no-source, --incl-source?
    

    # Add options -- Options
    options_group.add_option(                                # --output
        "--output", "-o", dest="target", metavar="PATH",
        help="The output directory.  If PATH does not exist, then "
        "it will be created.")
    options_group.add_option(                                # --show-imports
        "--inheritance", dest="inheritance", metavar="STYLE",
        help="The format for showing inheritance objects.  STYLE "
        "should be \"grouped\", \"listed\", or \"inherited\".")
    options_group.add_option(                                # --output
        "--docformat", dest="docformat", metavar="NAME",
        help="The default markup language for docstrings.  Defaults "
        "to \"%default\".")
    options_group.add_option(                                # --css
        "--css", dest="css", metavar="STYLESHEET",
        help="The CSS stylesheet.  STYLESHEET can be either a "
        "builtin stylesheet or the name of a CSS file.")
    options_group.add_option(                                # --name
        "--name", dest="prj_name", metavar="NAME",
        help="The documented project's name (for the navigation bar).")
    options_group.add_option(                                # --url
        "--url", dest="prj_url", metavar="URL",
        help="The documented project's URL (for the navigation bar).")
    options_group.add_option(                                # --navlink
        "--navlink", dest="prj_link", metavar="HTML",
        help="HTML code for a navigation link to place in the "
        "navigation bar.")
    options_group.add_option(                                # --top
        "--top", dest="top_page", metavar="PAGE",
        help="The \"top\" page for the HTML documentation.  PAGE can "
        "be a URL, the name of a module or class, or one of the "
        "special names \"trees.html\", \"indices.html\", or \"help.html\"")
    # [XX] output encoding isnt' implemented yet!!
    options_group.add_option(                                # --encoding
        "--encoding", dest="encoding", metavar="NAME",
        help="The output encoding for generated HTML files.")
    options_group.add_option(                                # --help-file
        "--help-file", dest="help_file", metavar="FILE",
        help="An alternate help file.  FILE should contain the body "
        "of an HTML file -- navigation bars will be added to it.")
    options_group.add_option(                                # --frames
        "--show-frames", action="store_true", dest="show_frames",
        help="Include frames in the output.")
    options_group.add_option(                                # --no-frames
        "--no-frames", action="store_false", dest="show_frames",
        help="Do not include frames in the output.")
    options_group.add_option(                                # --private
        "--show-private", action="store_true", dest="show_private",
        help="Include private variables in the output.")
    options_group.add_option(                                # --no-private
        "--no-private", action="store_false", dest="show_private",
        help="Do not include private variables in the output.")
    options_group.add_option(                                # --show-imports
        "--show-imports", action="store_true", dest="show_imports",
        help="List each module's imports.")
    options_group.add_option(                                # --show-imports
        "--no-imports", action="store_false", dest="show_imports",
        help="Do not list each module's imports.")
    options_group.add_option(                                # --quiet
        "--quiet", "-q", action="count", dest="quiet",
        help="Decrease the verbosity.")
    options_group.add_option(                                # --verbose
        "--verbose", "-v", action="count", dest="verbose",
        help="Increase the verbosity.")
    options_group.add_option(                                # --debug
        "--debug", action="store_true", dest="debug",
        help="Show full tracebacks for internal errors.")
    options_group.add_option(                                # --parse-only
        "--parse-only", action="store_false", dest="inspect",
        help="Get all information from parsing (don't inspect)")
    options_group.add_option(                                # --inspect-only
        "--inspect-only", action="store_false", dest="parse",
        help="Get all information from inspecting (don't parse)")

    # Add the option groups.
    optparser.add_option_group(action_group)
    optparser.add_option_group(options_group)

    # Set the option parser's defaults.
    optparser.set_defaults(action="html", show_frames=True,
                           docformat='epytext', 
                           show_private=True, show_imports=False,
                           inheritance="grouped",
                           verbose=0, quiet=0,
                           parse=True, inspect=True,
                           debug=epydoc.DEBUG)

    # Parse the arguments.
    options, names = optparser.parse_args()
    
    # Check to make sure all options are valid.
    if len(names) == 0:
        optparser.error("No names specified.")
    if options.inheritance not in ('grouped', 'listed', 'included'):
        optparser.error("Bad inheritance style.  Valid options are "
                        "grouped, listed, and included.")
    if not options.parse and not options.inspect:
        optparser.error("Invalid option combination: --parse-only "
                        "and --inspect-only.")

    # Calculate verbosity.
    options.verbosity = options.verbose - options.quiet

    # The target default depends on the action.
    if options.target is None:
        options.target = options.action
    
    # Return parsed args.
    return options, names

######################################################################
## Interface
######################################################################

def cli(args):
    options, names = parse_arguments(args)

    # Set up the logger
    if options.verbosity > 0:
        logger = ConsoleLogger(options.verbosity)
    else:
        if options.parse and options.inspect:
            logger = UnifiedProgressConsoleLogger(options.verbosity+1, 6)
        else:
            logger = UnifiedProgressConsoleLogger(options.verbosity+1, 5)
    log.register_logger(logger)
    print

    # create the output directory.
    if os.path.exists(options.target):
        if not os.path.isdir(options.target):
            return log.error("%s is not a directory" % options.target)
    else:
        try:
            os.mkdir(options.target)
        except Exception, e:
            return log.error(e)

    # Build docs for the named values.
    docbuilder = DocBuilder(inspect=options.inspect, parse=options.parse)
    docindex = docbuilder.build_doc_index(*names)

    # Perform the specified action.
    if options.action == 'html':
        _sandbox(_html, docindex, options)
        print
    else:
        print >>sys.stderr, '\nUnsupported action %s!' % options.action

# this is useless [XXX] -- inline it.
_encountered_internal_error = 0
def _sandbox(func, docindex, options):
    error = None
    try:
        func(docindex, options)
    except Exception, e:
        if options.debug: raise # [XX] options isn't available here!!
        if isinstance(e, (OSError, IOError)):
            print >>sys.stderr, '\nFile error:\n%s\n' % e
        else:
            print >>sys.stderr, '\nINTERNAL ERROR:\n%s\n' % e
            _encountered_internal_error = 1
    except:
        if options.debug: raise
        print >>sys.stderr, '\nINTERNAL ERROR\n'
        _encountered_internal_error = 1

def _html(docindex, options):
    html_writer = HTMLWriter(docindex, **options.__dict__)
    if options.verbose > 0:
        log.start_progress('Writing HTML docs to %r' % options.target)
    else:
        log.start_progress('Writing HTML docs')
    html_writer.write(options.target)
    log.end_progress()
    
######################################################################
## Logging
######################################################################

import curses

class ConsoleLogger(log.Logger):
    TERM_WIDTH = 75
    """The width of the console terminal."""
    # Terminal control strings:
    _TERM_CR = _TERM_CLR_EOL = _TERM_UP = ''
    _TERM_HIDE_CURSOR = _TERM_HIDE_CURSOR = ''
    _TERM_NORM = _TERM_BOLD = ''
    _TERM_RED = _TERM_YELLOW = _TERM_GREEN = _TERM_CYAN = _TERM_BLUE = ''
    _DISABLE_COLOR = False
    
    def __init__(self, verbosity):
        self._verbosity = verbosity
        self._progress = None
        self._message_blocks = []
        
        # Examine the capabilities of our terminal.
        if sys.stdout.isatty():
            try:
                curses.setupterm()
                self._TERM_CR = curses.tigetstr('cr') or ''
                self.TERM_WIDTH = curses.tigetnum('cols')-1
                self._TERM_CLR_EOL = curses.tigetstr('el') or ''
                self._TERM_NORM =  curses.tigetstr('sgr0') or ''
                self._TERM_HIDE_CURSOR = curses.tigetstr('civis') or ''
                self._TERM_SHOW_CURSOR = curses.tigetstr('cnorm') or ''
                self._TERM_UP = curses.tigetstr('cuu1') or ''
                if self._TERM_NORM:
                    self._TERM_BOLD = curses.tigetstr('bold') or ''
                    term_setf = curses.tigetstr('setf')
                    if term_setf or self._DISABLE_COLOR:
                        self._TERM_RED = curses.tparm(term_setf, 4) or ''
                        self._TERM_YELLOW = curses.tparm(term_setf, 6) or ''
                        self._TERM_GREEN = curses.tparm(term_setf, 2) or ''
                        self._TERM_CYAN = curses.tparm(term_setf, 3) or ''
                        self._TERM_BLUE = curses.tparm(term_setf, 1) or ''
            except:
                pass

        # Set the progress bar mode.
        if verbosity >= 2: self._progress_mode = 'list'
        elif verbosity >= 1:
            if self._TERM_CR and self._TERM_CLR_EOL and self._TERM_UP:
                self._progress_mode = 'multiline-bar'
            elif self._TERM_CR and self._TERM_CLR_EOL:
                self._progress_mode = 'bar'
            else:
                self._progress_mode = 'simple-bar'
        else: self._progress_mode = 'hide'

    def start_block(self, header):
        self._message_blocks.append( (header, []) )

    def end_block(self):
        header, messages = self._message_blocks.pop()
        if messages:
            width = self.TERM_WIDTH - 5 - 2*len(self._message_blocks)
            prefix = self._TERM_CYAN+self._TERM_BOLD+"| "+self._TERM_NORM
            divider = self._TERM_CYAN + self._TERM_BOLD + '+' + '-'*(width-1)
            # Mark up the header:
            header = wordwrap(header, right=width-2).rstrip()
            header = '\n'.join([prefix+self._TERM_CYAN+l+self._TERM_NORM
                                for l in header.split('\n')])
            # Indent the body:
            body = '\n'.join(messages)
            body = '\n'.join([prefix+'  '+l for l in body.split('\n')])
            # Put it all together:
            message = divider + '\n' + header + '\n' + body + '\n'
            self._report(message, rstrip=False)
            
    def _format(self, prefix, message, color):
        """
        Rewrap the message; but preserve newlines, and don't touch any
        lines that begin with spaces.
        """
        message = '%s' % message
        lines = message.split('\n')
        startindex = indent = len(prefix)
        for i in range(len(lines)):
            if lines[i].startswith(' '):
                lines[i] = ' '*(indent-startindex) + lines[i] + '\n'
            else:
                width = self.TERM_WIDTH - 5 - 4*len(self._message_blocks)
                lines[i] = wordwrap(lines[i], indent, width, startindex)
            startindex = 0
        return color+prefix+self._TERM_NORM+''.join(lines)

    def error(self, message):
        message = '%s' % message
        if self._verbosity >= -1:
            message = self._format('  Error: ', message, self._TERM_RED)
            self._report(message)
        
    def warn(self, message):
        message = '%s' % message
        if self._verbosity >= 0:
            message = self._format('Warning: ', message, self._TERM_YELLOW)
            self._report(message)
        
    def info(self, message):
        message = '%s' % message
        if self._verbosity >= 3:
            message = self._format('   Info: ', message, self._TERM_NORM)
            self._report(message)

    def _report(self, message, rstrip=True):
        message = '%s' % message
        if rstrip: message = message.rstrip()
        
        if self._message_blocks:
            self._message_blocks[-1][-1].append(message)
        else:
            # If we're in the middle of displaying a progress bar,
            # then make room for the message.
            if self._progress_mode == 'simple-bar':
                if self._progress is not None:
                    print
                    self._progress = None
            if self._progress_mode == 'bar':
                sys.stdout.write(self._TERM_CR+self._TERM_CLR_EOL)
            if self._progress_mode == 'multiline-bar':
                sys.stdout.write((self._TERM_CLR_EOL + '\n')*2 +
                                 self._TERM_CLR_EOL + self._TERM_UP*2)

            # Display the message message.
            print message
            sys.stdout.flush()
                
    def progress(self, percent, message=''):
        percent = min(1.0, percent)
        message = '%s' % message
        
        if self._progress_mode == 'list':
            if message:
                print '[%3d%%] %s' % (100*percent, message)
                sys.stdout.flush()
                
        elif self._progress_mode == 'bar':
            dots = int((self.TERM_WIDTH/2-5)*percent)
            background = '-'*(self.TERM_WIDTH/2-5)
            
            if len(message) > self.TERM_WIDTH/2:
                message = message[:self.TERM_WIDTH/2-3]+'...'

            sys.stdout.write(self._TERM_CR + '  ' + self._TERM_GREEN + '[' +
                             self._TERM_BOLD + '='*dots + background[dots:] +
                             self._TERM_NORM + self._TERM_GREEN + '] ' +
                             self._TERM_NORM + message + self._TERM_CLR_EOL)
            sys.stdout.flush()
            self._progress = percent
        elif self._progress_mode == 'multiline-bar':
            dots = int((self.TERM_WIDTH-10)*percent)
            background = '-'*(self.TERM_WIDTH-10)
            
            if len(message) > self.TERM_WIDTH-10:
                message = message[:self.TERM_WIDTH-10-3]+'...'
            else:
                message = message.center(self.TERM_WIDTH-10)

            sys.stdout.write(
                # Line 1:
                self._TERM_CLR_EOL + '      ' + self._TERM_BOLD + 
                'Progress:'.center(self.TERM_WIDTH-10) + '\n' +
                self._TERM_NORM +
                # Line 2:
                self._TERM_CLR_EOL + ('%3d%% ' % (100*percent)) +
                self._TERM_GREEN + '[' +  self._TERM_BOLD + '='*dots +
                background[dots:] + self._TERM_NORM + self._TERM_GREEN +
                ']' + self._TERM_NORM + '\n' +
                # Line 3:
                self._TERM_CLR_EOL + '      ' + message + self._TERM_CR +
                self._TERM_UP + self._TERM_UP)
            
            sys.stdout.flush()
            self._progress = percent
        elif self._progress_mode == 'simple-bar':
            if self._progress is None: self._progress = 0.0
            dots = int((self.TERM_WIDTH-2)*percent)
            progress_dots = int((self.TERM_WIDTH-2)*self._progress)
            if dots > progress_dots:
                sys.stdout.write('.'*(dots-progress_dots))
                sys.stdout.flush()
                self._progress = percent

    def start_progress(self, header=None):
        if self._progress is not None:
            raise ValueError
        if self._progress_mode == 'hide':
            return
        if header:
            print self._TERM_BOLD + header + self._TERM_NORM
        if self._progress_mode == 'simple-bar':
            sys.stdout.write('  [')
            sys.stdout.flush()
        self._progress = 0.0

    def end_progress(self):
        self.progress(1.)
        if self._progress_mode == 'bar':
            sys.stdout.write(self._TERM_CR+self._TERM_CLR_EOL)
        if self._progress_mode == 'multiline-bar':
                sys.stdout.write((self._TERM_CLR_EOL + '\n')*2 +
                                 self._TERM_CLR_EOL + self._TERM_UP*2)
        if self._progress_mode == 'simple-bar':
            print ']'
        self._progress = None

class UnifiedProgressConsoleLogger(ConsoleLogger):
    def __init__(self, verbosity, stages=5):
        self.stage = 0
        self.stages = stages
        self.task = None
        ConsoleLogger.__init__(self, verbosity)
        
    def progress(self, percent, message=''):
        p = float(self.stage-1+percent)/self.stages
        if message == UNKNOWN: message = None
        if message: message = '%s: %s' % (self.task, message)
        ConsoleLogger.progress(self, p, message)

    def start_progress(self, message=None):
        self.task = message
        if self.stage == 0:
            ConsoleLogger.start_progress(self)
        self.stage += 1

    def end_progress(self):
        if self.stages == self.stage:
            ConsoleLogger.end_progress(self)

######################################################################
## main
######################################################################

if __name__ == '__main__':
    try:
        cli(sys.argv[1:])
    except:
        print
        raise
