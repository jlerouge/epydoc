############################################################
##  epydoc Makefile
##
##  Edward Loper
############################################################

# Python source files
PY_SRC = $(wildcard src/epydoc/*.py)

# The location of the webpage.
HOST = shell.sf.net
DIR = /home/groups/e/ep/epydoc/htdocs

# The local location to build the web materials
WEBDIR = html

############################################################

.PHONY: all usage distributions web webpage xfer refdocs verbose

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

local: refdocs
	rsync -arz -e ssh $(WEBDIR)/* /var/www/epydoc

refdocs: .up2date.refdocs
.up2date.refdocs: ${PY_SRC}
	epydoc ${PY_SRC} -o ${WEBDIR} -n epydoc \
	       -u http://epydoc.sf.net --css blue
	touch .up2date.refdocs

checkdocs:
	epydoc --check ${PY_SRC}

# This is basically just for testing..
verbose:
	epydoc ${PY_SRC} -o ${WEBDIR} -n epydoc \
	       -u http://epydoc.sf.net --css blue -vvv
	touch .up2date.refdocs
