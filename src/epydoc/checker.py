#
# objdoc: epydoc documentation completeness checker
# Edward Loper
#
# Created [01/30/01 05:18 PM]
# $Id$
#

"""
Check for missing documentation field values.
"""

##################################################
## Imports
##################################################

import re, sys, os.path, string
from xml.dom.minidom import Text as _Text
from types import ModuleType as _ModuleType
from types import ClassType as _ClassType
from types import FunctionType as _FunctionType
from types import BuiltinFunctionType as _BuiltinFunctionType
from types import BuiltinMethodType as _BuiltinMethodType
from types import MethodType as _MethodType
from types import StringType as _StringType

import epydoc.epytext as epytext
from epydoc.uid import UID, Link
from epydoc.objdoc import Documentation, ModuleDoc, FuncDoc
from epydoc.objdoc import ClassDoc, Var, Raise, ObjDoc

def _is_private(str):
    for piece in str.split('.'):
        if piece[0] == '_' and piece[-1] != '_':
            return 1
    return 0

class DocChecker:
    # Types
    MODULE = 1
    CLASS  = 2
    FUNC   = 4
    VAR    = 8
    IVAR   = 16
    CVAR   = 32
    PARAM  = 64
    RETURN = 128
    ALL_T  = 1+2+4+8+16+32+64+128

    # Checks
    TYPE = 256
    SEE = 512
    AUTHOR = 1024
    VERSION = 2048
    DESCR_LAZY = 4096
    DESCR_STRICT = 8192
    DESCR = DESCR_LAZY + DESCR_STRICT
    ALL_C = 256+512+1024+2048+4096+8192

    # Private/public
    PRIVATE = 16384
    PUBLIC = 32768
    ALL_P = PRIVATE + PUBLIC

    ALL = ALL_T + ALL_C + ALL_P

    def __init__(self, docmap):
        docs = []
        self._docs = docmap.values()
        self._docmap = docmap
        """
        self._docmap = docmap
        for (uid, doc) in docmap.items():
            if isinstance(doc, ModuleDoc) or isinstance(doc, ClassDoc):
                docs.append(uid)
        self._docs = []
        self._add(docs)
        """
        f = lambda d1,d2:cmp(`d1.uid()`, `d2.uid()`)
        self._docs.sort(f)
        self._checks = 0

    def check(self, checks = None):
        if checks == None:
            self.check(DocChecker.MODULE | DocChecker.CLASS |
                       DocChecker.FUNC | DocChecker.DESCR_LAZY |
                       DocChecker.PUBLIC)
            self.check(DocChecker.PARAM | DocChecker.VAR |
                       DocChecker.IVAR | DocChecker.CVAR |
                       DocChecker.RETURN | DocChecker.DESCR |
                       DocChecker.TYPE | DocChecker.PUBLIC)
            return

        self._checks = checks
        for doc in self._docs:
            if isinstance(doc, ModuleDoc):
                self._check_module(doc)
            elif isinstance(doc, ClassDoc):
                self._check_class(doc)
            elif isinstance(doc, FuncDoc):
                self._check_func(doc)
            else:
                raise AssertionError(doc)

    def _check_name_publicity(self, name):
        if (_is_private(name) and
            not (self._checks & DocChecker.PRIVATE)): return 0
        if (not _is_private(name) and
            not (self._checks & DocChecker.PUBLIC)): return 0
        return 1

    def _check_basic(self, doc):
        if (self._checks & DocChecker.DESCR) and (not doc.descr()):
            if ((self._checks & DocChecker.DESCR_STRICT) or
                (not isinstance(doc, FuncDoc)) or
                (not doc.returns().descr())):
                print 'Warning -- No descr    ', doc.uid()
        if (self._checks & DocChecker.SEE):
            for (elt, descr) in doc.seealsos():
                if not self._docmap.has_key(elt):
                    print 'Warning -- Broken see-also ', doc.uid(), elt
        if (self._checks & DocChecker.AUTHOR) and (not doc.authors()):
            print 'Warning -- No authors  ', doc.uid()
        if (self._checks & DocChecker.VERSION) and (not doc.version()):
            print 'Warning -- No version  ', doc.uid()
            
    def _check_module(self, doc):
        if not self._check_name_publicity(`doc.uid()`): return
        if self._checks & DocChecker.MODULE:
            self._check_basic(doc)
        if self._checks & DocChecker.VAR:
            for v in doc.variables():
                self._check_var(v, `doc.uid()`)
        
    def _check_class(self, doc):
        if not self._check_name_publicity(`doc.uid()`): return
        if self._checks & DocChecker.CLASS:
            self._check_basic(doc)
        if self._checks & DocChecker.IVAR:
            for v in doc.ivariables():
                self._check_var(v, `doc.uid()`)
        if self._checks & DocChecker.CVAR:
            for v in doc.cvariables():
                self._check_var(v, `doc.uid()`)

    def _check_var(self, var, name):
        if not self._check_name_publicity(name): return
        if var == None: return
        if var.name() == 'return':
            if (var.type() and
                epytext.to_plaintext(var.type()).strip().lower() == 'none'):
                return
        if (self._checks & DocChecker.DESCR) and (not var.descr()):
            print 'Warning -- No descr    ', name+'.'+var.name()
        if (self._checks & DocChecker.TYPE) and (not var.type()):
            print 'Warning -- No type     ', name+'.'+var.name()
            
    def _documented_ancestor(self, doc):
        if isinstance(doc, FuncDoc):
            while (not doc.documented() and
                   doc.overrides() and
                   self._docmap.has_key(doc.overrides())):
                doc = self._docmap[doc.overrides()]
        return doc
            
    def _check_func(self, doc):
        if not self._check_name_publicity(`doc.uid()`): return
        doc = self._documented_ancestor(doc)
        if self._checks & DocChecker.FUNC:
            if ((`doc.uid()`.split('.'))[-1] not in
                ('__hash__',)):
                self._check_basic(doc)
        if (self._checks & DocChecker.RETURN):
            if ((`doc.uid()`.split('.'))[-1] not in
                ('__init__', '__hash__')):
                self._check_var(doc.returns(), `doc.uid()`)
        if (self._checks & DocChecker.PARAM):
            if doc.uid().is_method():
                for v in doc.parameters()[1:]:
                    self._check_var(v, `doc.uid()`)
            else:
                for v in doc.parameters():
                    self._check_var(v, `doc.uid()`)
            self._check_var(doc.vararg(), `doc.uid()`)
            self._check_var(doc.kwarg(), `doc.uid()`)
