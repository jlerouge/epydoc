# -*- coding: utf-8 -*-
"""Encoding epydoc test.

Characters in 128-155 range:
àèìòù¥©®

Going east
тзгяиѕ

South east
אבגד

More south
سشصضط

"""

class Test:
    """Un class di test"""
    def x(y):
        """A dummy fun.
        
        :param y: Unicode chars in a field: אבגד سشصضط
        """
        pass
