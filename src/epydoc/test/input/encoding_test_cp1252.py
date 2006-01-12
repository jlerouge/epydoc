# -*- coding: cp1252 -*-
"""Encoding epydoc test.

Questa � una prova.

:var `pippo`: L'amico di Topolino �.
    Lui si che � un amico. Non pensa agli ���.

:bug:
    Thus bug is serious.

    Really, it is.

    Terribly.
"""

pippo = 10

def testfun(a, b, c):
    """Test function.

    Docstring is long.

    :param `a`: Un tizio
    :type `a`: `string`
    :return: Un caio
    :rtype: `string`
    """
    pass

class Botto(Exception):
    """Capita quando uno fa il botto."""
    pass

class Test(object):
    """Un� class� d� t�st

    :ivar p: Anything
    :cvar q: Anythong else
    :IVariables:
      * `sezione_id`: (`int`) Id della sezione da cui � stato letto l'ordine,
        `None` se l'ordine � nuovo. Usato per verificare i permessi in caso di
        spostamento di sezione dell'ordine.
    """
    q = 10
    sezione_id=None

    z = property(fget=lambda x: 10, doc="Zeta � zeta!")

    def __init__(self):
        self.p = 20

    def x(y):
        """A dummy fun.

        :param y: Sar� d�ra!
        :type y: `string`
        :return: N� s�.
        :rtype: `int`
        :exception `KaBum`: Il Botto.
        :organization: PiroSoftware c.n.f.
        :todo: boheccheneso?

            e comunque, menefotto.

        """
        pass

class WithSlots(object):
    """Class with slots.

    This class has two instance variables. They are trated as properties.

    :ivar a: Prop1
    :ivar b: Prop2
    """
    __slots__ = ['a', 'b']
    def __init__(self):
        self.a = 10
        self.b = 20
