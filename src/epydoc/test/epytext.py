#
# test/epytext.py: tests for epytext markup language
# Edward Loper
#
# Created [10/30/02 12:06 PM]
# $Id$
#

"""
Regression testing for the epytext markup language.

The test cases currently implemented are by no means comprehensive.
"""

if __name__ == '__main__':
    import epydoc.epytext; reload(epydoc.epytext)

import unittest, re
from epydoc.epytext import *

##//////////////////////////////////////////////////////
##  Parse Tests
##//////////////////////////////////////////////////////

class ParseTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def failIfParseError(self, errors, warnings):
        estr = ''
        if errors:
            estr += '\n'+'~'*60+'\nERRORS:\n'
            for e in errors: estr += '%s\n' % e
        if warnings:
            estr += '\n'+'~'*60+'\nWARNINGS:\n'
            for w in warnings: estr += '%s\n' % w
        if errors or warnings:
            self.fail(estr+'~'*60)


    def checkParse(self, epytext, debug=None):
        """
        Parse C{epytext}, and check that it generates xml output
        X{xml}, with no warnings or errors.
        """
        errors = []
        warnings = []
        out = parse(epytext, errors, warnings)
        self.failIfParseError(errors, warnings)
        if debug:
            self.failUnlessEqual(to_debug(out).strip(), debug.strip())

    def checkParseError(self, epytext, errtype, linenum):
        errors = []
        warnings = []
        out = parse(epytext, errors, warnings)

        for err in errors:
            if isinstance(err, errtype) and err.linenum == linenum:
                errors.remove(err)
                break
        else:
            self.fail("No %s generated on line %s" %
                      (errtype.__name__, linenum))

        self.failIfParseError(errors, warnings)

    def testPara(self):
        self.checkParse("""
        this is one paragraph.

        This is
        another.

        This is a third.""", """
   P>|this is one paragraph.
     |
   P>|This is another.
     |
   P>|This is a third.
     |""")

    def testUnindentedFields(self):
        """
        Make sure that unindented fields are allowed.
        """
        self.checkParse("""
        This is a paragraph.
        
        @foo: This is a field.""")
        
        self.checkParse("""
        This is a paragraph.
        @foo: This is a field.""")
        
        self.checkParse("""
        This is a paragraph.
           @foo: This is a field.
             Hello.""")
        
        self.checkParse("""
        This is a paragraph.
           @foo: This is a field.
             Hello.""")
        self.checkParse("""Paragraph\n@foo: field""")
        self.checkParse("""Paragraph\n\n@foo: field""")
        self.checkParse("""\nParagraph\n@foo: field""")

    def testUnindentedList(self):
        """
        Make sure that unindented lists are not allowed.
        """
        self.checkParseError("""
        This is a paragraph.
        
        - This is a list item.""", StructuringError, 4)
        
        self.checkParseError("""
        This is a paragraph.
        - This is a list item.""", StructuringError, 3)
        
        self.checkParseError("""
        This is a paragraph.
           - This is a list item.
             Hello.
             - Sublist item.""", StructuringError, 5)
        
        self.checkParseError("""
        This is a paragraph.
           - This is a list item.
             Hello.
             
             - Sublist item.""", StructuringError, 6)
        self.checkParseError("""Paragraph\n- list item""",
                             StructuringError, 2)
        self.checkParseError("""Paragraph\n\n- list item""",
                             StructuringError, 3)
        self.checkParseError("""\nParagraph\n- list item""",
                             StructuringError, 3)

    def testIndentedList(self):
        """
        Make sure that indented lists are allowed.
        """
        list1 = """
   P>|This is a paragraph.
     |
LIST>|- This is a list item.
     |
   P>|This is a paragraph
     |"""
        self.checkParse('This is a paragraph.\n  - This is a list item.\n'+
                        'This is a paragraph', list1)
        self.checkParse('This is a paragraph.\n\n  - This is a list item.'+
                        '\n\nThis is a paragraph', list1)
        self.checkParse("""
        This is a paragraph.
        
          - This is a list item.
          
        This is a paragraph""", list1)
        self.checkParse("""
        This is a paragraph.
        
              - This is a list item.
        This is a paragraph""", list1)
        list2 = """
LIST>|- This is a list item.
     |"""
        self.checkParse("""
        - This is a list item.""", list2)
        self.checkParse("""- This is a list item.""", list2)
        self.checkParse("""\n- This is a list item.""", list2)

    def testListBasic(self):
        self.checkParse("""
        This is a paragraph.
          - This is a list item.
          - This is a
            list item.
        This is a paragraph""", """
   P>|This is a paragraph.
     |
LIST>|- This is a list item.
     |
  LI>|- This is a list item.
     |
   P>|This is a paragraph
     |""")
            
        self.checkParse("""
          - This is a list item.
          - This is a
            list item.""", """
LIST>|- This is a list item.
     |
  LI>|- This is a list item.
     |""")
            
        self.checkParse("""
        This is a paragraph.

          - This is a list item.
          - This is a
            list item.
            
        This is a paragraph""", """
   P>|This is a paragraph.
     |
LIST>|- This is a list item.
     |
  LI>|- This is a list item.
     |
   P>|This is a paragraph
     |""")
            
        self.checkParse("""
        This is a paragraph.
          - This is a list item.
          
            It contains two paragraphs.
        This is a paragraph""", """
   P>|This is a paragraph.
     |
LIST>|- This is a list item.
     |
   P>|  It contains two paragraphs.
     |
   P>|This is a paragraph
     |""")
            
        self.checkParse("""
        This is a paragraph.
          - This is a list item with a literal
            block::
              hello
                there
        This is a paragraph""", """
   P>|This is a paragraph.
     |
LIST>|- This is a list item with a literal block::
     |
 LIT>|    hello
     |      there
     |
   P>|This is a paragraph
     |""")

    def testListItemWrap(self):
        self.checkParse("""
          - This is a list
            item.""", """
LIST>|- This is a list item.
     |""")

        self.checkParse("""
          - This is a list
          item.""", """
LIST>|- This is a list item.
     |""")

        self.checkParse("""
          - This is a list
          item.
          - This is a list
          item.""", """
LIST>|- This is a list item.
     |
  LI>|- This is a list item.
     |""")


     
            

##//////////////////////////////////////////////////////
##  Test Suite & Test Running
##//////////////////////////////////////////////////////

def testsuite():
    """
    Return a PyUnit testsuite for the epytext module.
    """
    
    tests = unittest.TestSuite()

    parse_tests = unittest.makeSuite(ParseTestCase, 'test')
    tests = unittest.TestSuite( (tests, parse_tests) )

    return tests

def test():
    import unittest
    runner = unittest.TextTestRunner()
    runner.run(testsuite())

if __name__ == '__main__':
    test()

