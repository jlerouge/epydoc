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
	@echo "  make epydoc"
	@echo "  make checkdoc"

web: refdocs
	(cd ${WEBDIR} && tar -cvzf webpage.tgz *)
	scp ${WEBDIR}/webpage.tgz ${HOST}:${DIR}
	ssh ${HOST} "cd ${DIR} && tar -xvzf webpage.tgz && rm webpage.tgz"
	ssh ${HOST} "cd ${DIR} && ln -s epydoc.html index.html"

refdocs: 
	epydoc ${PY_SRC} -o ${WEBDIR}
