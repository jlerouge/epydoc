"""

Merge API documentation information from multiple sources.

  - inspection + parsing
  
"""

######################################################################
## Debugging
######################################################################

# path fun
import sys, random
sys.path.insert(0, '/home/edloper/data/programming/epydoc/sandbox/epydoc3')

######################################################################
## Imports
######################################################################

# API documentation encoding:
from epydoc.apidoc import *

True = getattr(__builtins__, 'True', 1)   #: For backwards compatibility
False = getattr(__builtins__, 'False', 0) #: For backwards compatibility

######################################################################
## Doc Merger
######################################################################

class DocMerger:
    """
    To do:
      - copy is_imported src->dst
      - copy variable docstrings src->dst
      - copy instvars src->dst
      - copy function arg default values src->dst (?)
      - copy variable ast src->dst (?)
    """

    MERGE_VALUEDOC_AST = True
    MERGE_ARG_DEFAULT_AST = True
    MERGE_IS_IMPORTED = True
    MERGE_VAR_DOCSTRINGS = True
    MERGE_INSTANCE_VARS = True

    def __init__(self):
        # This is to prevent cycles:
        self._merge_cache = {}

    def merge(self, dst_doc, src_doc):
        # If the types don't match, ignore src_doc.
        if src_doc is None: return
        if dst_doc.__class__ is not src_doc.__class__: return

        pyids = (id(dst_doc), id(src_doc))
        if self._merge_cache.has_key(pyids):
            return dst_doc
        else:
            self._merge_cache[pyids] = 1

        # Merge value syntax trees for valuedoc
        if isinstance(dst_doc, ValueDoc) and self.MERGE_VALUEDOC_AST:
            if dst_doc.ast is None:
                dst_doc.ast = src_doc.ast

        # Merge is_imported value for variables
        if isinstance(dst_doc, VariableDoc) and self.MERGE_IS_IMPORTED:
            if dst_doc.is_imported == 'unknown':
                dst_doc.is_imported = src_doc.is_imported

        # Merge docstrings for variables
        if isinstance(dst_doc, VariableDoc) and self.MERGE_VAR_DOCSTRINGS:
            if dst_doc.docstring is None:
                dst_doc.docstring = src_doc.docstring

        # Recurse to valuedocs for variables
        if isinstance(dst_doc, VariableDoc):
            if (dst_doc.valuedoc is not None and
                src_doc.valuedoc is not None):
                self.merge(dst_doc.valuedoc, src_doc.valuedoc)

        # In namespaces, recurse to children (for shared children)
        if isinstance(dst_doc, NamespaceDoc):
            for varname, dst_var in dst_doc.children.items():
                self.merge(dst_var, src_doc.children.get(varname))

        # In modules, mark any remaining children as imported
        if isinstance(dst_doc, ModuleDoc) and self.MERGE_IS_IMPORTED:
            for varname, dst_var in dst_doc.children.items():
                if dst_var.is_imported == 'unknown':
                    dst_var.is_imported = True

        # In classes, copy any instance variables
        if isinstance(dst_doc, ClassDoc) and self.MERGE_INSTANCE_VARS:
            for varname, src_var in src_doc.children.items():
                if (src_var.is_instvar and
                    not dst_doc.children.has_key(varname)):
                    dst_doc.children[varname] = src_var

        # In functions, merge any default values...
        if isinstance(dst_doc, RoutineDoc) and self.MERGE_ARG_DEFAULT_AST:
            if len(dst_doc.args) == len(src_doc.args):
                for dst_arg, src_arg in zip(dst_doc.args, src_doc.args):
                    if (dst_arg.default is not None and
                        src_arg.default is not None):
                        # [XX] not quite what I mean?
                        dst_arg.default = src_arg.default

        # Return the merged destination doc.
        return dst_doc
    
######################################################################
## Testing
######################################################################

if __name__ == '__main__':
    # Import inspector/parser
    from epydoc.docinspector import DocInspector
    from epydoc.docparser import DocParser

    # Create Insepctor, Parser, Merger
    inspector = DocInspector()
    parser = DocParser(inspector.inspect(__builtins__))
    merger = DocMerger()

    # Build docs
    try:
        import epydoc_test; del sys.modules['epydoc_test']
        import epydoc_test
        inspectdoc = inspector.inspect(epydoc_test)
    except: inspectdoc = None
    try: parsedoc = parser.parse('epydoc_test.py')
    except: parsedoc = None
    if parsedoc is None and inspectdoc is None:
        raise ValueError, "no docs for the module"
    elif parsedoc is None:
        moduledoc = inspectdoc
    elif inspectdoc is None:
        moduledoc = parsedoc
    else:
        moduledoc = merger.merge(inspectdoc, parsedoc)

    print moduledoc.pp(depth=-1, exclude=['subclasses', 'bases',
                                          'is_alias', 'name'])
    




