############################################################
##  epydoc Makefile
##
##  Edward Loper
############################################################

ll: distributions

# Tests.
test: 
	python epydoc/test/__init__.py -v epydoc/test/*.py

# Clean.  
#    - Erase any pyc and pyo files.
#    - Get rid of build/dist directories
clean:
	rm -rf build dist MANIFEST
	rm -f *.pyc epydoc/*.pyc epydoc/*/*.pyc
	rm -f *.pyo epydoc/*.pyo epydoc/*/*.pyo

# Distributions.
# Build all from scratch; and create links for convenient access.
distributions: clean sdist bdist

# Source distributions
sdist: gztardist zipdist

# Built distributions
bdist: rpmdist windist

# Produce dist/$(NAME)-$(VERSION).tar.gz
gztardist:
	python setup.py -q sdist --format=gztar

# Produce dist/$(NAME)-$(VERSION).tar.gz
zipdist:
	python setup.py -q sdist --format=zip

# Produce dist/$(NAME)-$(VERSION)-1.noarch.rpm
# Produce dist/$(NAME)-$(VERSION)-1.src.rpm
rpmdist:
	python setup.py -q bdist --format=rpm

# Produce dist/$(NAME)-$(VERSION).win32.exe
windist:
	python setup.py -q bdist --format=wininst
