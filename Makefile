############################################################
##  epydoc Makefile
##
##  Edward Loper
############################################################

# Python source files
PY_SRC = src/epydoc/*.py

# The location of the webpage.
HOST = shell.sf.net
DIR = /home/groups/e/ep/epydoc/htdocs

# The local location to build the web materials
WEBDIR = html

############################################################

all: usage

usage:
	@echo "Usage:"
	@echo "  make web"
	@echo "  make refdocs"
	@echo "  make checkdoc"
	@echo "  make distributions"

distributions:
	$(MAKE) -C src distributions

web: xfer
webpage: xfer
xfer: refdocs
	rsync -arz -e ssh $(WEBDIR)/* $(HOST):$(DIR)

refdocs: 
	epydoc ${PY_SRC} -o ${WEBDIR} -n epydoc \
	       -u http://epydoc.sf.net -css blue
