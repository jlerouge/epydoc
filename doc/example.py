"""
Examples for the epytext manual.
"""

def x_intercept(m, b):
    """
    Return the x intercept of the line M{y=m*x+b}.  The X{x intercept}
    of a line is the point at which it crosses the x axis (M{y=0}).

    This function can be used in conjuction with L{z_transform} to
    find an arbitrary function's zeros.

    @type  m: number
    @param m: The slope of the line.
    @type  b: number
    @param b: The y intercept of the line.  The X{y intercept} of a
              line is the point at which it crosses the y axis (M{x=0}).
    @rtype:   number
    @return:  the x intercept of the line M{y=m*x+b}.
    """
    return -b/m

def z_transform(f):
    """
    This is just an example; there is no z_transform function.
    """
    return f(12)
