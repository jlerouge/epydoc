############################################################
##  epydoc Makefile
##
##  Edward Loper
############################################################

# Python source files
PY_SRC = $(wildcard src/epydoc/*.py)
EXAMPLES_SRC = $(wildcard doc/*.py)
DOCS = $(wildcard doc/*.html) $(wildcard doc/*.css) $(wildcard doc/*.png)

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
	@echo "  make webpage -- build the webpage and copy it to sourceforge"
	@echo "  make refdocs -- build the API reference docs"
	@echo "  make checkdoc -- check the documentation completeness"
	@echo "  make distributions -- build the distributions"
	@echo "  make clean -- remove all built files"

clean:
	$(MAKE) -C src clean
	rm -rf ${WEBDIR} ${API} ${EXAMPLES}

distributions: src/dist/.up2date
src/dist/.up2date: $(PY_SRC)
	$(MAKE) -C src distributions

web: xfer
webpage: xfer
xfer: .html.up2date
	rsync -arzv -e ssh ${WEBDIR}/* $(HOST):$(DIR)

local: .html.up2date
	cp -r ${WEBDIR}/* /var/www/epydoc

checkdocs:
	epydoc --check ${PY_SRC}

.html.up2date: refdocs examples distributions
	rm -rf ${WEBDIR}
	mkdir -p ${WEBDIR}
	cp -r ${DOCS} ${WEBDIR}
	cp -r ${API} ${WEBDIR}
	cp -r ${EXAMPLES} ${WEBDIR}
	cp -r src/dist/epydoc* ${WEBDIR}

refdocs: .up2date.refdocs
.up2date.refdocs: ${PY_SRC}
	rm -rf ${API}
	mkdir -p ${API}
	epydoc ${PY_SRC} -o ${API} -n epydoc \
	       -u http://epydoc.sourceforge.net --css blue
	touch .up2date.refdocs

examples: .up2date.examples
.up2date.examples: ${EXAMPLES_SRC} ${PY_SRC}
	rm -rf ${EXAMPLES}
	mkdir -p ${EXAMPLES}
	epydoc ${EXAMPLES_SRC} sre -o ${EXAMPLES} -n epydoc \
	       -u http://epydoc.sourceforge.net --css blue
	touch .up2date.examples
