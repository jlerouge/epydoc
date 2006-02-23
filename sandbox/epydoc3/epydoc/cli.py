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
"""

import sys, os
from optparse import OptionParser, OptionGroup
import epydoc
from epydoc.driver import DocBuilder
from epydoc.docwriter.html import HTMLWriter
from epydoc import log

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
        "--css", "-c", dest="css", metavar="STYLESHEET",
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
    options_group.add_option(                                # --top
        "--encoding", dest="encoding", metavar="NAME",
        help="The output encoding for generated HTML files.")
    options_group.add_option(
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
    options_group.add_option(                             # --quiet
        "--quiet", "-q", action="count", dest="quiet",
        help="Decrease the verbosity.")
    options_group.add_option(                             # --verbose
        "--verbose", "-v", action="count", dest="verbose",
        help="Increase the verbosity.")
    options_group.add_option(                             # --denug
        "--debug", action="store_true", dest="debug",
        help="Show full tracebacks for internal errors.")

    # Add the option groups.
    optparser.add_option_group(action_group)
    optparser.add_option_group(options_group)

    # Set the option parser's defaults.
    optparser.set_defaults(action="html", show_frames=True,
                           docformat='epytext', 
                           show_private=True, show_imports=False,
                           debug=False, inheritance="grouped",
                           verbose=0, quiet=0)

    # Parse the arguments.
    options, names = optparser.parse_args()
    
    # Check to make sure all options are valid.
    if len(names) == 0:
        optparser.error("No names specified.")
    if options.inheritance not in ('grouped', 'listed', 'included'):
        optparser.error("Bad inheritance style.  Valid options are "
                        "grouped, listed, and included.")

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

    # figure these out from options..  add options.
    parse = True
    inspect = True

    # Set up the logger
    if options.verbosity > 0:
        logger = ConsoleLogger(options.verbosity)
    else:
        if parse and inspect:
            logger = UnifiedProgressConsoleLogger(options.verbosity+1, 5)
        else:
            logger = UnifiedProgressConsoleLogger(options.verbosity+1, 4)
    log.register_logger(logger)

    # Build docs for the named values.
    docbuilder = DocBuilder()
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
    num_files = 20 # HMM!

    log.start_progress('Writing HTML docs to %r.' % options.target)
    html_writer.write(options.target)
    log.end_progress()
    
######################################################################
## Logging
######################################################################

class ConsoleLogger(log.Logger):
    WIDTH = 75
    VT100_INV = '\033[1m'#'\033[7m'
    VT100_BLK = ''#'\033[8m'
    VT100_CLR = '\033[0m'
    VT100_CLEAR_TO_EOL = '\033[0K'
    
    def __init__(self, verbosity):
        self._verbosity = verbosity
        self._progress = None
        self._message_blocks = []
        
        # Set the progress bar mode.
        if verbosity >= 2: self._progress_mode = 'list'
        elif verbosity >= 1: self._progress_mode = 'bar'
        else: self._progress_mode = 'hide'
        
        # Can we use '\r' to return to the beginning of the line?
        if os.environ.get('TERM') in ['vt100', 'xterm']:
            self._advanced_term = True
        else:
            self._advanced_term = False

    def start_block(self, header):
        self._message_blocks.append( (header, []) )

    def end_block(self):
        header, messages = self._message_blocks.pop()
        if messages:
            width = self.WIDTH - 5*len(self._message_blocks)
            if self._advanced_term and False: # [xx] hmm
                inv = self.VT100_INV
                norm = self.VT100_CLR
                submessage = '\n'.join(['%s %s %s' % (inv, norm, l) for l in 
                                        '\n'.join(messages).split('\n')])
                message = (inv + header + ' '*(self.WIDTH-len(header)) + 
                           norm + '\n' + submessage + '\n')
            else:
                message = ('='*width + '\n' + header + '\n' +
                           '-'*width + '\n' + '\n'.join(messages))
            self._report(message+'\n', rstrip=False)

    def error(self, meessage):
        if self._verbosity >= -1:
            self._report(message)
        
    def warn(self, message):
        if self._verbosity >= 0:
            self._report(message)
        
    def info(self, message):
        if self._verbosity >= 3:
            self._report(message)

    def _report(self, message, rstrip=True):
        message = str(message)
        if rstrip: message = message.rstrip()
        
        if self._message_blocks:
            self._message_blocks[-1][-1].append(message)
        else:
            # If we're in the middle of displaying a progress bar,
            # then print a newline, and reset self._progress to None,
            # so we'll know to restart the progress bar on the next
            # call to progress().
            if self._progress is not None and self._progress_mode == 'bar':
                if self._advanced_term:
                    sys.stdout.write('\r'+self.VT100_CLEAR_TO_EOL)
                else:
                    print
                self._progress = None

            # shift message right? [xxx]
            message = '\n'.join(['  '+l for l in message.split('\n')])

            # Display the message message.
            print message

    def progress(self, percent, message=None):
        if self._progress_mode == 'list':
            if message is not None:
                print '[%3d%%] %s' % (100*percent, message)
                
        elif self._progress_mode == 'bar':
            if self._advanced_term:
                dots = int((self.WIDTH/2-5)*percent)
                
                if message is None: message = ''
                else: message = str(message)
                if len(message) > self.WIDTH/2:
                    message = message[:self.WIDTH/2-3]+'...'
                
                sys.stdout.write('\r  [' + self.VT100_INV + self.VT100_BLK +
                                 '='*dots + self.VT100_CLR +
                                 ' '*(self.WIDTH/2-5-dots) + '] ' + 
                                 message + self.VT100_CLEAR_TO_EOL)
                sys.stdout.flush()
                self._progress = percent
            else:
                dots = int((self.WIDTH-2)*percent)
                progress_dots = int((self.WIDTH-2)*self._progress)
                if dots > progress_dots:
                    sys.stdout.write('.'*(dots-progress_dots))
                    sys.stdout.flush()
                    self._progress = progress

    def start_progress(self, header):
        if self._progress is not None:
            raise ValueError
        if self._progress_mode == 'hide': return
        
        print header
        if self._progress_mode == 'bar':
            if not self._advanced_term:
                sys.stdout.write('  [')
        self._progress = 0.0

    def end_progress(self):
        self.progress(1.)
        if self._progress_mode == 'bar':
            if self._advanced_term:
                sys.stdout.write('\r'+self.VT100_CLEAR_TO_EOL)
            else:
                print ']'
        self._progress = None

class UnifiedProgressConsoleLogger(ConsoleLogger):
    def __init__(self, verbosity, stages=5):
        self.stage = 0
        self.stages = 5
        self.task = None
        ConsoleLogger.__init__(self, verbosity)
        
    def progress(self, percent, message=None):
        p = float(self.stage-1+percent)/self.stages
        ConsoleLogger.progress(self, p, self.task)

    def start_progress(self, message):
        self.task = message
        if self.stage == 0:
            ConsoleLogger.start_progress(self, 'Progress:')
        self.stage += 1

    def end_progress(self):
        if self.stages == self.stage:
            ConsoleLogger.end_progress(self)

######################################################################
## main
######################################################################

if __name__ == '__main__':
    cli(sys.argv[1:])
