############################################################
##  epydoc Makefile
##
##  Edward Loper
############################################################

##//////////////////////////////////////////////////////////////////////
## Configuration variables
##//////////////////////////////////////////////////////////////////////

# Python source files (don't include src/epydoc/test?)
PY_SRC = src/epydoc/
PY_SRCFILES = $(shell find $(PY_SRC) -name '*.py')
EXAMPLES_SRC = $(wildcard doc/*.py)
DOCS = $(wildcard doc/*)
DOCTESTS = $(wildcard src/epydoc/test/*.doctest)

# What version of python to use?
PYTHON = python2.4

# The location of the webpage.
HOST = shell.sf.net
DIR = /home/groups/e/ep/epydoc/htdocs

# The current version of epydoc.
VERSION = $(shell $(PYTHON) -c 'import epydoc; print epydoc.__version__')

# Base output directories
WEBDIR        = webpage
LATEX         = latex
HTML          = html

# Output subdirectories
HTML_API      = $(HTML)/api
HTML_EXAMPLES = $(HTML)/examples
HTML_STDLIB   = $(HTML)/stdlib
HTML_DOCTEST  = $(HTML)/doctest
LATEX_API     = $(LATEX)/api
LATEX_STDLIB  = $(LATEX)/stdlib

EPYDOC = $(PYTHON) src/epydoc/cli.py
export PYTHONPATH=src/

# Options for rst->html converter
RST2HTML = $(PYTHON) src/tools/rst2html.py

##//////////////////////////////////////////////////////////////////////
## Usage
##//////////////////////////////////////////////////////////////////////

.PHONY: all usage clean distributions web webpage xfer local
.PHONY: checkdocs api-html api-pdf examples stdlib-html stdlib-pdf
.PHONY: test tests

all: usage
usage:
	@echo "Usage:"
	@echo "  make webpage -- build the webpage and copy it to sourceforge"
	@echo "    make api-html -- build the HTML docs for epydoc"
	@echo "    make api-pdf -- build the PDF docs for epydoc"
	@echo "    make doctest-html -- convert doctests to HTML"
	@echo "    make examples -- build example API docs for the webpage"
	@echo "    make stdlib-html -- build HTML docs for the Python Standard Library"
	@echo "  make checkdocs -- check the documentation completeness"
	@echo "  make distributions -- build the distributions"
	@echo "  make clean -- remove all built files"
	@echo "  make test -- run unit tests"

##//////////////////////////////////////////////////////////////////////
## Clean
##//////////////////////////////////////////////////////////////////////

clean:
	$(MAKE) -C src clean
	rm -rf $(WEBDIR) $(HTML) $(LATEX)
	rm -rf .*.up2date

##//////////////////////////////////////////////////////////////////////
## Distributions
##//////////////////////////////////////////////////////////////////////

distributions: .distributions.up2date
.distributions.up2date: test $(PY_SRCFILES) .webpage.up2date $(DOCS)
	$(MAKE) -C src distributions
	touch .distributions.up2date

##//////////////////////////////////////////////////////////////////////
## Web page
##//////////////////////////////////////////////////////////////////////

web: xfer
webpage: xfer
xfer: test .webpage.up2date stdlib-html
	rsync -arzv -e ssh $(WEBDIR)/* $(HOST):$(DIR)
	rsync -arzv -e ssh $(HTML_STDLIB)/ $(HOST):$(DIR)/stdlib

local: .webpage.up2date
	rm -rf /var/www/epydoc/*
	cp -r $(WEBDIR)/* /var/www/epydoc

checkdoc: checkdocs
checkdocs:
	epydoc --check --tests=vars,types $(PY_SRC)

.webpage.up2date: .api-html.up2date .examples.up2date .api-pdf.up2date \
		.doctest-html.up2date doc/epydoc-man.html \
		doc/epydocgui-man.html $(DOCS)
	rm -rf $(WEBDIR)
	mkdir -p $(WEBDIR)
	cp -r $(DOCS) $(WEBDIR)
	cp -r $(HTML_API) $(WEBDIR)/api
	cp -r $(HTML_EXAMPLES) $(WEBDIR)/examples
	cp -r $(HTML_DOCTEST)/* $(WEBDIR)/doctest
	cp $(LATEX_API)/api.pdf $(WEBDIR)/epydoc.pdf
	touch .webpage.up2date

# Use plaintext docformat by default.  But this is overridden by the
# __docformat__ strings in each epydoc module.  (So just
# xml.dom.minidom and a few Docutils modules get plaintext
# docstrings).
api-html: .api-html.up2date
.api-html.up2date: $(PY_SRCFILES) profile.out
	rm -rf $(HTML_API)
	mkdir -p $(HTML_API)
	$(EPYDOC) -o $(HTML_API) --name epydoc --css white \
	       --url http://epydoc.sourceforge.net --pstat profile.out \
	       --inheritance=listed --navlink "epydoc $(VERSION)"\
	       --docformat plaintext -v --graph all $(PY_SRC)
	touch .api-html.up2date

api-pdf: .api-pdf.up2date
.api-pdf.up2date: $(PY_SRCFILES)
	rm -rf $(LATEX_API)
	mkdir -p $(LATEX_API)
	$(EPYDOC) --pdf -o $(LATEX_API) --docformat plaintext \
	       --name "Epydoc $(VERSION)" $(PY_SRC) -v
	touch .api-pdf.up2date

doctest-html: .doctest-html.up2date
.doctest-html.up2date: $(DOCTESTS)
	rm -rf $(HTML_DOCTEST)
	mkdir -p $(HTML_DOCTEST)
	for doctest in $(DOCTESTS); do \
	    out_file=$(HTML_DOCTEST)/`basename $$doctest .doctest`.html; \
	    echo "$(RST2HTML) $$doctest $$out_file"; \
	    if $(RST2HTML) $$doctest $$out_file; then true; \
	    else exit 1; fi\
	done
	touch .doctest-html.up2date

examples: .examples.up2date
.examples.up2date: $(EXAMPLES_SRC) $(PY_SRCFILES)
	rm -rf $(HTML_EXAMPLES)
	mkdir -p $(HTML_EXAMPLES)
	$(EPYDOC) -o $(HTML_EXAMPLES) --name epydoc \
	       --url http://epydoc.sourceforge.net \
	       --css white --top epytext_example --docformat=plaintext \
	       --navlink 'epydoc examples' doc/epytext_example.py sre
	$(EPYDOC) -o $(HTML_EXAMPLES)/grouped \
	       --inheritance=grouped \
	       --name epydoc --url http://epydoc.sourceforge.net \
	       --css white --debug \
	       --navlink 'epydoc examples' doc/inh_example.py
	$(EPYDOC) -o $(HTML_EXAMPLES)/listed \
	       --inheritance=listed \
	       --name epydoc --url http://epydoc.sourceforge.net \
	       --css white --debug \
	       --navlink 'epydoc examples' doc/inh_example.py
	$(EPYDOC) -o $(HTML_EXAMPLES)/included \
	       --inheritance=included \
	       --name epydoc --url http://epydoc.sourceforge.net \
	       --css white --debug \
	       --navlink 'epydoc examples' doc/inh_example.py
	touch .examples.up2date

# Generate the HTML version of the man page.  Note: The
# post-processing clean-up that I do is probably *not* very portable.
doc/epydoc-man.html: man/epydoc.1
	man2html man/epydoc.1 \
	     | sed 's/<\/HEAD>/<link rel="stylesheet" href="epydoc.css" type="text\/css"\/><\/HEAD>/' \
	     | sed 's/<H1>EPYDOC<\/H1>/<H1>epydoc (1)<\/H1>/' \
	     | sed 's/<BODY>/<BODY><DIV CLASS="BODY">/'\
	     | sed 's/Content-type:.*//' \
	     | sed '/Section: User Commands/,/<HR>/{s/.*//;}'\
	     | sed 's/<\/BODY>/<\/DIV><\/BODY>/'\
	     | sed '/<DD>/{s/<DD>//; :loop; n; b loop;}'\
	     | sed 's/\(<A NAME=".*">\)&nbsp;<\/A>/\1/'\
	     | sed 's/<\/H2>/<\/H2><\/A>/'\
	     | sed 's/"\/cgi-bin\/man2html?epydocgui+1"/"epydocgui-man.html"/'\
	     | sed 's/<A HREF="\/cgi-bin\/man2html">man2html<\/A>/man2html/'\
	     > doc/epydoc-man.html

doc/epydocgui-man.html: man/epydocgui.1
	man2html man/epydocgui.1 \
	     | sed 's/<\/HEAD>/<link rel="stylesheet" href="epydoc.css" type="text\/css"\/><\/HEAD>/' \
	     | sed 's/<H1>EPYDOCGUI<\/H1>/<H1>epydocgui (1)<\/H1>/'\
	     | sed 's/<BODY>/<BODY><DIV CLASS="BODY">/'\
	     | sed 's/Content-type:.*//' \
	     | sed '/Section: User Commands/,/<HR>/{s/.*//;}'\
	     | sed 's/<\/BODY>/<\/DIV><\/BODY>/'\
	     | sed '/<DD>/{s/<DD>//; :loop; n; b loop;}'\
	     | sed 's/\(<A NAME=".*">\)&nbsp;<\/A>/\1/'\
	     | sed 's/<\/H2>/<\/H2><\/A>/'\
	     | sed 's/"\/cgi-bin\/man2html?epydocgui+1"/"epydocgui-man.html"/'\
	     | sed 's/<A HREF="\/cgi-bin\/man2html">man2html<\/A>/man2html/'\
	     > doc/epydocgui-man.html

profile.out: $(PY_SRCFILES)
	$(EPYDOC) -o profile.tmp --name epydoc --css white \
	       --url http://epydoc.sourceforge.net --profile-epydoc \
	       --inheritance=listed --navlink "epydoc $(VERSION)"\
	       --docformat plaintext -v --graph all $(PY_SRC)
	rm -rf profile.tmp

##//////////////////////////////////////////////////////////////////////
## Standard Library docs
##//////////////////////////////////////////////////////////////////////

SLNAME = 'Python Standard Library'
SLURL = "http://www.python.org/doc/lib/lib.html"
SLFILES = $(shell find /usr/lib/$(PYTHON)/ -name '*.py' -o -name '*.so' \
	      |grep -v "/$(PYTHON)/config/" \
	      |grep -v "/$(PYTHON)/lib-old/" \
	      |grep -v "/$(PYTHON)/site-packages/" \
              |grep -v "/$(PYTHON)/__phello__\.foo\.py" )
PY_PRINT_BUILTINS = "import sys; print ' '.join(sys.builtin_module_names)"
SLBUILTINS = $(shell $(PYTHON) -c $(PY_PRINT_BUILTINS))

export TZ='XXX00XXX;000/00,000/00' # So tzparse won't die.
stdlib-html: .stdlib-html.up2date
.stdlib-html.up2date: $(PY_SRCFILES)
	rm -rf $(HTML_STDLIB)
	mkdir -p $(HTML_STDLIB)
	@echo "Building stdlib html docs..."
	@$(EPYDOC) -o $(HTML_STDLIB) --css white --name $(SLNAME) \
	       --url $(SLURL) --debug --graph classtree \
	       --show-imports $(SLBUILTINS) $(SLFILES)
	touch .stdlib-html.up2date

# (this will typically cause latex to run out of resources)
stdlib-pdf: .stdlib-pdf.up2date
.stdlib-pdf.up2date: $(PY_SRCFILES)
	rm -rf $(LATEX_STDLIB)
	mkdir -p $(LATEX_STDLIB)
	$(EPYDOC) --pdf -o $(LATEX_STDLIB) \
		--no-private --name $(SLNAME) --docformat plaintext \
		--debug --builtins $(SLFILES)
##//////////////////////////////////////////////////////////////////////
## Unit Testing
##//////////////////////////////////////////////////////////////////////

tests: test
test:
	$(PYTHON) src/epydoc/test/__init__.py

##//////////////////////////////////////////////////////////////////////
## Other test targets
##//////////////////////////////////////////////////////////////////////

docutils: docutils-html docutils-pdf

docutils-html: .docutils-html.up2date
.docutils-html.up2date: $(PY_SRCFILES)
	rm -rf $(HTML)/docutils
	mkdir -p $(HTML)/docutils
	$(EPYDOC) -o $(HTML)/docutils -n 'Docutils' --html \
	        --docformat plaintext --ignore-param-mismatch \
	        /usr/lib/python2.3/site-packages/docutils
	touch .docutils-html.up2date

docutils-pdf: .docutils-pdf.up2date
.docutils-pdf.up2date: $(PY_SRCFILES)
	rm -rf $(LATEX)/docutils
	mkdir -p $(LATEX)/docutils
	$(EPYDOC) -o $(LATEX)/docutils -n 'Docutils' --pdf \
	        --docformat plaintext --ignore-param-mismatch \
	        /usr/lib/python2.3/site-packages/docutils
	touch .docutils-pdf.up2date


