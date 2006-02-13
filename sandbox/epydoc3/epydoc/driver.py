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

    doc_dict = {}
    for name in names:
        # Parsing
        if parse:
            try:
                parsedoc = parser.find(name)
            except ValueError:
                # hmm -- ValueError might be too general!
                print "  Failed to parse (couldn't find %s)." % name
                parsedoc = None
        else:
            parsedoc = None
    
        # Inspecting
        if inspect:
            print 'inspect %s...' % name
            for i in range(len(name)):
                n = '.'.join(name[:len(name)-i])
                try:
                    val = __import__(n)
                    for identifier in name[1:]:
                        val = getattr(val, identifier)
                    inspectdoc = inspector.inspect(val)
                    break
                except ImportError, err:
                    if str(err).endswith(' '+n): pass # continue loop
                    else: raise
            else:
                print 'Could not import %s' % name
                inspectdoc = None
        else:
            inspectdoc = None
            
        # Merge them.
        if inspectdoc is None and parsedoc is None:
            print 'Warning: No docs for %s' % name
        elif inspectdoc is None:
            doc_dict[name] = parsedoc
        elif parsedoc is None:
            doc_dict[name] = inspectdoc
        else:
            doc_dict[name] = merger.merge(inspectdoc, parsedoc)

        if name in doc_dict:
            print `doc_dict[name]`, name

    # Construct a dictionary mapping name -> ValueDoc, and use that
    # dictionary to create an index.
    docindex = DocIndex(doc_dict)

    # Parse all docstrings.
    for val_doc in docindex.reachable_valdocs:
        docstring_parser.parse_docstring(val_doc)
#         if isinstance(val_doc, ClassDoc):
#             if val_doc.local_variables is not UNKNOWN:
#                 for var_doc in val_doc.local_variables.values():
#                     docstring_parser.parse_docstring(var_doc)
#         if isinstance(val_doc, NamespaceDoc):
#             if val_doc.variables is not UNKNOWN:
#                 for var_doc in val_doc.variables.values():
#                     docstring_parser.parse_docstring(var_doc)

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
