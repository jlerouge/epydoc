############################################################
##  epydoc Makefile
##
##  Edward Loper
############################################################

##//////////////////////////////////////////////////////////////////////
## Configuration variables
##//////////////////////////////////////////////////////////////////////

# Python source files
PY_SRC = $(wildcard src/epydoc/*.py)
EXAMPLES_SRC = $(wildcard doc/*.py)
DOCS = $(wildcard doc/*.html) $(wildcard doc/*.css) $(wildcard doc/*.png)

# The location of the webpage.
HOST = shell.sf.net
DIR = /home/groups/e/ep/epydoc/htdocs

# Output directories
WEBDIR = html
API = api
EXAMPLES = examples
STDLIB = stdlib

##//////////////////////////////////////////////////////////////////////
## Usage
##//////////////////////////////////////////////////////////////////////

.PHONY: all usage clean distributions web webpage xfer local
.PHONY: checkdocs refdocs examples stdlib

all: usage
usage:
	@echo "Usage:"
	@echo "  make webpage -- build the webpage and copy it to sourceforge"
	@echo "    make refdocs -- build the API docs for epydoc"
	@echo "    make examples -- build example API docs for the webpage"
	@echo "  make checkdoc -- check the documentation completeness"
	@echo "  make distributions -- build the distributions"
	@echo "  make clean -- remove all built files"
	@echo "  make stdlib -- build docs for the Python Standard Library"

##//////////////////////////////////////////////////////////////////////
## Clean
##//////////////////////////////////////////////////////////////////////

clean:
	$(MAKE) -C src clean
	rm -rf ${WEBDIR} ${API} ${EXAMPLES} ${STDLIB}
	rm -rf .*.up2date

##//////////////////////////////////////////////////////////////////////
## Distributions
##//////////////////////////////////////////////////////////////////////

distributions: .distributions.up2date
.distributions.up2date: $(PY_SRC) .html.up2date $(DOCS)
	$(MAKE) -C src distributions
	touch .distributions.up2date

##//////////////////////////////////////////////////////////////////////
## Web page
##//////////////////////////////////////////////////////////////////////

web: xfer
webpage: xfer
xfer: .html.up2date stdlib
	rsync -arzv -e ssh ${WEBDIR}/* $(HOST):$(DIR)
	rsync -arzv -e ssh ${STDLIB}/ $(HOST):$(DIR)/stdlib

local: .html.up2date
	cp -r ${WEBDIR}/* /var/www/epydoc

checkdocs:
	epydoc --check ${PY_SRC}

.html.up2date: .refdocs.up2date .examples.up2date \
		doc/epydoc-man.html doc/epydocgui-man.html ${DOCS}
	rm -rf ${WEBDIR}
	mkdir -p ${WEBDIR}
	cp -r ${DOCS} ${WEBDIR}
	cp -r ${API} ${WEBDIR}
	cp -r ${EXAMPLES} ${WEBDIR}
	touch .html.up2date

# Use plaintext docformat by default.  But this is overridden by the
# __docformat__ strings in each epydoc module.  (So just
# xml.dom.minidom gets plaintext docstrings).
refdocs: .refdocs.up2date
.refdocs.up2date: ${PY_SRC}
	rm -rf ${API}
	mkdir -p ${API}
	epydoc -o ${API} -n epydoc -u http://epydoc.sourceforge.net \
	       --css blue --private-css green -v --debug --navlink 'epydoc'\
	       --docformat plaintext ${PY_SRC} xml.dom.minidom
	touch .refdocs.up2date

examples: .examples.up2date
.examples.up2date: ${EXAMPLES_SRC} ${PY_SRC}
	rm -rf ${EXAMPLES}
	mkdir -p ${EXAMPLES}
	epydoc -o ${EXAMPLES} -n epydoc -u http://epydoc.sourceforge.net \
	       --no-private --css blue -t example -q \
	       --navlink 'epydoc examples' ${EXAMPLES_SRC} sre
	touch .examples.up2date

# Generate the HTML version of the man page.  Note: The
# post-processing clean-up that I do is probably *not* very portable.
doc/epydoc-man.html: man/epydoc.1
	wget http://localhost/cgi-bin/man2html?epydoc -O - \
	     2>/dev/null \
	     | sed 's/<\/HEAD><BODY>/<link rel="stylesheet" href="epydoc.css" type="text\/css"\/><\/HEAD><BODY>/'\
	     | sed '/<DD>/{s/<DD>//; :loop; n; b loop;}'\
	     | sed '/<H1>/,/<HR>/{s/.*//;}'\
	     | sed 's/\(<A NAME=".*">\)&nbsp;<\/A>/\1/'\
	     | sed 's/<\/H2>/<\/H2><\/A>/'\
	     | sed 's/"\/cgi-bin\/man2html?epydocgui+1"/"epydocgui-man.html"/'\
	     | sed 's/<A HREF="\/cgi-bin\/man2html">man2html<\/A>/man2html/'\
	     > doc/epydoc-man.html

doc/epydocgui-man.html: man/epydocgui.1
	wget http://localhost/cgi-bin/man2html?epydocgui -O - \
	     2>/dev/null \
	     | sed 's/<\/HEAD><BODY>/<link rel="stylesheet" href="epydoc.css" type="text\/css"\/><\/HEAD><BODY>/'\
	     | sed '/<H1>/,/<HR>/{s/.*//;}'\
	     | sed 's/\(<A NAME=".*">\)&nbsp;<\/A>/\1/'\
	     | sed 's/<\/H2>/<\/H2><\/A>/'\
	     | sed 's/"\/cgi-bin\/man2html?epydoc+1"/"epydoc-man.html"/'\
	     | sed 's/<A HREF="\/cgi-bin\/man2html">man2html<\/A>/man2html/'\
	     > doc/epydocgui-man.html

##//////////////////////////////////////////////////////////////////////
## Standard Library docs
##//////////////////////////////////////////////////////////////////////

SLNAME = 'Python 2.2 Standard Library'
SLURL = "http://www.python.org/doc/2.2/lib/lib.html"
SLLINK = '<font size="-2">Python 2.2<br />Standard Library</font>'
SLFILES = $(shell find /usr/lib/python2.2/ -name '*.py' -o -name '*.so' \
	      |grep -v '/python2.2/config/' \
	      |grep -v '/python2.2/lib-old/' \
	      |grep -v '/python2.2/site-packages/')
stdlib: .stdlib.up2date
.stdlib.up2date: ${PY_SRC}
	rm -rf ${STDLIB}
	mkdir -p ${STDLIB}
	python2.2 src/epydoc/cli.py -o ${STDLIB} -c white --show-imports \
	       -n ${SLNAME} -u ${SLURL} --docformat plaintext --debug \
	       --navlink ${SLLINK} --builtins ${SLFILES}
	touch .stdlib.up2date
