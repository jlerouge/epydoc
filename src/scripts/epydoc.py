#!/usr/bin/python
#
# Call the command line interface for Epydoc.
#

# We have to do some path magic to prevent Python from getting
# confused about the difference between this epydoc module, and the
# real epydoc package.  So sys.path[0], which contains the directory
# of the script.
import sys
del sys[0]

from epydoc.cli import cli
cli()

