#!/usr/local/bin/python
#
# Distutils setup script for the Natural Language
# Processing Toolkit
#
# Created [05/27/01 09:04 PM]
# Edward Loper
#

from distutils.core import setup

setup(name="epydoc",
      version="1.0",
      description="Edloper's Python Documentation Suite",
      author="Edward Loper",
      author_email="ed@loper.org",
      scripts=['scripts/epydoc'],
      packages=['epydoc'])

