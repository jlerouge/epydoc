#!/usr/local/bin/python
#
# Distutils setup script for the Natural Language
# Processing Toolkit
#
# Created [05/27/01 09:04 PM]
# Edward Loper
#

from distutils.core import setup
import re, epydoc

VERSION = str(epydoc.__version__)
(AUTHOR, EMAIL) = re.match('^(.*?)\s*<(.*)>$', epydoc.__author__).groups()
URL = epydoc.__url__

setup(name="epydoc",
      description="Edloper's Python Documentation Suite",
      version=VERSION,
      author=AUTHOR,
      author_email=EMAIL,
      url=URL,
      scripts=['scripts/epydoc'],
      packages=['epydoc'])

