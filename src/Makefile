############################################################
##  epydoc Makefile
##
##  Edward Loper
############################################################

# Python source files
PY_SRC = $(wildcard epydoc/*.py)

all: distributions

# Clean.  
#    - Erase any pyc and pyo files.
#    - Get rid of build/dist directories
clean:
	rm -rf build dist MANIFEST
	rm -f *.pyc epydoc/*.pyc epydoc/*/*.pyc
	rm -f *.pyo epydoc/*.pyo epydoc/*/*.pyo
	rm -f doc

# Distributions.
# Build all from scratch; and create links for convenient access.
distributions: dist/.up2date
dist/.up2date: $(PY_SRC) clean sdist bdist
	touch dist/.up2date

# Source distributions
sdist: gztardist zipdist

# Built distributions
bdist: rpmdist windist

# Produce dist/$(NAME)-$(VERSION).tar.gz
gztardist:
	rm -f doc; ln -s ../doc doc
	python setup.py -q sdist --format=gztar

# Produce dist/$(NAME)-$(VERSION).tar.gz
zipdist:
	rm -f doc; ln -s ../doc doc
	python setup.py -q sdist --format=zip

# Produce dist/$(NAME)-$(VERSION)-1.noarch.rpm
# Produce dist/$(NAME)-$(VERSION)-1.src.rpm
rpmdist:
	rm -f doc; ln -s ../doc doc
	python setup.py -q bdist --format=rpm

# Produce dist/$(NAME)-$(VERSION).win32.exe
windist:
	rm -f doc; ln -s ../doc doc
	python setup.py -q bdist --format=wininst
