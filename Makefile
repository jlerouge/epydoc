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
API = doc/api
EXAMPLES = doc/examples

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
	rm -rf .*.up2date

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
	epydoc --check ${PY_SRC} -v

.html.up2date: refdocs examples #distributions
	rm -rf ${WEBDIR}
	mkdir -p ${WEBDIR}
	cp -r ${DOCS} ${WEBDIR}
	cp -r ${API} ${WEBDIR}
	cp -r ${EXAMPLES} ${WEBDIR}
#	cp -r src/dist/epydoc* ${WEBDIR}

refdocs: .refdocs.up2date
.refdocs.up2date: ${PY_SRC}
	rm -rf ${API}
	mkdir -p ${API}
	epydoc -o ${API} -n epydoc -u http://epydoc.sourceforge.net \
	       --css blue --private-css green -vv -f ${PY_SRC} 
	touch .refdocs.up2date

examples: .examples.up2date
.examples.up2date: ${EXAMPLES_SRC} ${PY_SRC}
	rm -rf ${EXAMPLES}
	mkdir -p ${EXAMPLES}
	epydoc -o ${EXAMPLES} -n epydoc -u http://epydoc.sourceforge.net \
	       --no-private --css blue -v ${EXAMPLES_SRC} sre
	touch .examples.up2date

LIBS = $(shell find /usr/lib/python2.1/ -name '*.py' -o -name '*.so' \
	      |grep -v '/eric/' \
	      |grep -v '/lib-old/' \
	      |grep -v '/site-packages/') # for now (?)

libdocs:
	mkdir -p libs
	epydoc -o libs -f -vv -q -n 'Python Standard Library' \
	       -u http://www.python.org -c white ${LIBS} #\
#	       >libs/libdocs.out 2>libs/libdocs.err
