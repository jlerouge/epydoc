"""Test for unicode and other troubles in variable values and regexp patterns."""
import re

# from Django -- http://www.djangoproject.com
DOTS = ['&middot;', '*', '\xe2\x80\xa2', '&#149;', '&bull;', '&#8226;']
ustring_re = re.compile(u"([\u0080-\uffff])")
hard_coded_bullets_re = re.compile(r'((?:<p>(?:%s).*?[a-zA-Z].*?</p>\s*)+)' % '|'.join([re.escape(d) for d in DOTS]), re.DOTALL)
