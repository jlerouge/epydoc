#!/usr/bin/python
#
# Call the command line interface for Epydoc.
#

# We have to do some path magic to prevent Python from getting
# confused about the difference between this epydoc module, and the
# real epydoc package.
import sys, os, os.path
cwd = os.path.abspath(os.curdir)
sys.path = [d for d in sys.path if os.path.abspath(d) != cwd]

from epydoc.cli import cli
cli()

