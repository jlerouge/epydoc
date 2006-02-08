# Import inspector/parser
from epydoc.apidoc import *
from epydoc.docinspector import DocInspector
from epydoc.docparser import DocParser
from epydoc.docmerger import DocMerger
from epydoc.docindexer import DocIndex
from epydoc.docstringparser import DocstringParser
from epydoc.docinheriter import DocInheriter
from epydoc.docwriter.plaintext import PlaintextWriter
from epydoc.docwriter.html import HTMLWriter
import sys

def build_docs(names, inspect=True, parse=True):
    names = [DottedName(name) for name in names]
    
    # Create our tool chain
    inspector = DocInspector()
    parser = DocParser(inspector.inspect(__builtins__))
    merger = DocMerger()
    docstring_parser = DocstringParser()
    inheriter = DocInheriter()

    parsedocs = []
    inspectdocs = []
    for name in names:
        if parse:
            parsedocs.append(parser.find(name))
        else:
            parsedocs.append(None)
    
        # Inspecting
        if inspect:
            for i in range(len(name)):
                try:
                    n = '.'.join(name[:len(name)-i])
                    val = __import__(n)
                    for identifier in name[1:]:
                        val = getattr(val, identifier)
                    inspectdocs.append(inspector.inspect(val))
                    break
                except ImportError:
                    pass
            else:
                print 'Could not import %s' % name
                inspectdocs.append(None)
        else:
            inspectdocs.append(None)

    # Merge all docs.
    merged_docs = []
    for name, parsedoc, inspectdoc in zip(names, parsedocs, inspectdocs):
        if inspectdoc is None and parsedoc is None:
            print 'Warning: No docs for %s' % name
        elif inspectdoc is None:
            merged_docs.append(parsedoc)
        elif parsedoc is None:
            merged_docs.append(inspectdoc)
        else:
            merged_docs.append(merger.merge(inspectdoc, parsedoc))

    # Construct a dictionary mapping name -> ValueDoc, and use that
    # dictionary to create an index.
    doc_dict = dict(zip(names, merged_docs))
    docindex = DocIndex(doc_dict)

    # Parse all docstrings.
    for val_doc in docindex.reachable_valdocs:
        docstring_parser.parse_docstring(val_doc)
        if isinstance(val_doc, ClassDoc):
            if val_doc.local_variables is not UNKNOWN:
                for var_doc in val_doc.local_variables.values():
                    docstring_parser.parse_docstring(var_doc)
        if isinstance(val_doc, NamespaceDoc):
            if val_doc.variables is not UNKNOWN:
                for var_doc in val_doc.variables.values():
                    docstring_parser.parse_docstring(var_doc)

    # Inheritance.
    inheriter.inherit(docindex)

#     # debug:
#     for n,v in docindex.items():
#         if n!=v.canonical_name: continue
#         if isinstance(v, NamespaceDoc):
#             for var in v.variables.values():
#                 assert var.container == v
#             for var in v.sorted_variables:
#                 assert var.container == v
#     print docindex[DottedName('epydoc.apidoc.APIDoc')].\
#            pp(exclude='canonical_container')

    return docindex

def help(names):
    """
    Given a name, find its docs.
    """
    inspect = True
    parse = True
    
    #inspect = False
    #parse = False

    docindex = build_docs(names, inspect=inspect, parse=parse)
    
    #print docindex.get_valdoc(DottedName(names[0]))
    #print 'C', sorted([v.canonical_name for v in docindex.contained_valdocs])
    #print 'R', sorted([v.canonical_name for v in docindex.reachable_valdocs])
    
    writer = HTMLWriter(docindex)
    def progress(s):
        print 'Writing %s...' % s
    writer.write('/home/edloper/public_html/epydoc', progress)
    
if __name__ == '__main__':
    if len(sys.argv) <= 1:
        print 'usage: %s <name>' % sys.argv[0]
    else:
        help(sys.argv[1:])
