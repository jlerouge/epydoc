############################################################
##  epydoc Makefile
##
##  Edward Loper
############################################################

# Python source files
PY_SRC = $(wildcard src/epydoc/*.py)
EXAMPLES_SRC = $(wildcard doc/*.py)
DOCS = $(wildcard doc/*.html) $(wildcard doc/*.css)

# The location of the webpage.
HOST = shell.sf.net
DIR = /home/groups/e/ep/epydoc/htdocs

# The local location to build the web materials
WEBDIR = html
API = api
EXAMPLES = examples

############################################################

.PHONY: all usage distributions web webpage xfer
.PHONY: refdocs verbose

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
xfer: refdocs examples
	rm -rf ${WEBDIR}
	mkdir -p ${WEBDIR}
	cp -r ${DOCS} ${WEBDIR}
	cp -r ${API} ${WEBDIR}
	cp -r ${EXAMPLES} ${WEBDIR}
	rsync -arz --size-only -v -e ssh ${WEBDIR}/* $(HOST):$(DIR)

examples: .up2date.examples
.up2date.examples: ${EXAMPLES_SRC}
	mkdir -p ${EXAMPLES}
	epydoc ${EXAMPLES_SRC} -o ${EXAMPLES} -n epydoc \
	       -u http://epydoc.sf.net --css blue
	touch .up2date.examples

local: refdocs
	rsync -arz -e ssh $(API)/* /var/www/epydoc

refdocs: .up2date.refdocs
.up2date.refdocs: ${PY_SRC}
	mkdir -p ${API}
	epydoc ${PY_SRC} -o ${API} -n epydoc \
	       -u http://epydoc.sf.net --css blue
	touch .up2date.refdocs

checkdocs:
	epydoc --check ${PY_SRC}

# This is basically just for testing..
verbose:
	epydoc ${PY_SRC} -o ${API} -n epydoc \
	       -u http://epydoc.sf.net --css blue -vvv
	touch .up2date.refdocs
