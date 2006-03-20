# epydoc -- Graph generation
#
# Copyright (C) 2005 Edward Loper
# Author: Edward Loper <edloper@loper.org>
# URL: <http://epydoc.sf.net>
#
# $Id: docparser.py 1015 2006-03-19 03:27:50Z edloper $

"""
Render Graphviz directed graphs as images.

@see: L{Graphviz Homepage<http://www.research.att.com/sw/tools/graphviz/>}
"""

from sets import Set
import re
from epydoc import log

# Backwards compatibility imports:
try: sorted
except NameError: from epydoc.util import py_sorted as sorted

######################################################################
#{ Dot Graphs
######################################################################

class DotGraph:
    """
    A C{dot} directed graph.  The contents of the graph are
    constructed from the following instance variables:

      - C{nodes}: A list of L{DotGraphNode}s, encoding the nodes
        that are present in the graph.  Each node is characterized
        a set of attributes, including an optional label.
      - C{edges}: A list of L{DotGraphEdge}s, encoding the edges
        that are present in the graph.  Each edge is characterized
        by a set of attributes, including an optional label.
      - C{node_defaults}: Default attributes for nodes.
      - C{edge_defaults}: Default attributes for edges.
      - C{body}: A string that is appended as-is in the body of
        the graph.  This can be used to build more complex dot
        graphs.

    The C{link()} method can be used to resolve crossreference links
    within the graph.  In particular, if the 'href' attribute of any
    node or edge is assigned a value of the form C{<name>}, then it
    will be replaced by the URL of the object with that name.  This
    applies to the C{body} as well as the C{nodes} and C{edges}.

    To render the graph, use the methods C{write()} and C{render()}.
    Usually, you should call C{link()} before you render the graph.
    """
    _uids = Set()
    """A set of all uids that that have been generated, used to ensure
    that each new graph has a unique uid."""

    DOT_COMMAND = 'dot'
    """The command that should be used to spawn dot"""
    
    def __init__(self, title, body='', node_defaults=None, edge_defaults=None):
        """
        Create a new C{DotGraph}.
        """
        self.title = title
        """The title of the graph."""
        
        self.nodes = []
        """A list of the nodes that are present in the graph.
        @type: C{list} of L{DocGraphNode}"""
        
        self.edges = []
        """A list of the edges that are present in the graph.
        @type: C{list} of L{DocGraphEdge}"""

        self.body = body
        """A string that should be included as-is in the body of the
        graph.
        @type: C{str}"""
        
        self.node_defaults = node_defaults or {}
        """Default attribute values for nodes."""
        
        self.edge_defaults = edge_defaults or {}
        """Default attribute values for edges."""

        self.uid = re.sub(r'\W', '_', title)
        """A unique identifier for this graph.  This can be used as a
        filename when rendering the graph.  No two C{DotGraph}s will
        have the same uid."""

        # Make sure the UID is unique
        if self.uid in self._uids:
            n = 2
            while ('%s_%s' % (self.uid, n)) in self._uids: n += 1
            self.uid = '%s_%s' % (self.uid, n)
        self._uids.add(self.uid)

    def link(self, docstring_linker):
        """
        Replace any href attributes whose value is <name> with 
        the url of the object whose name is <name>.
        """
        # Link xrefs in nodes
        self._link_href(self.node_defaults, docstring_linker)
        for node in self.nodes:
            self._link_href(node.attribs, docstring_linker)

        # Link xrefs in edges
        self._link_href(self.edge_defaults, docstring_linker)
        for edge in self.nodes:
            self._link_href(edge.attribs, docstring_linker)

        # Link xrefs in body
        def subfunc(m):
            url = docstring_linker.url_for(m.group(1))
            if url: return 'href="%s"%s' % (url, m.group(2))
            else: return ''
        self.body = re.sub("href\s*=\s*['\"]?<([\w\.]+)>['\"]?\s*(,?)",
                           subfunc, self.body)

    def _link_href(self, attribs, docstring_linker):
        """Helper for L{link()}"""
        if 'href' in attribs:
            m = re.match(r'^<([\w\.]+)>$', attribs['href'])
            if m:
                url = docstring_linker.url_for(m.group(1))
                if url: attribs['href'] = url
                else: del attribs['href']
                
    def write(self, filename, language='gif'):
        """
        Render the graph using the output format C{language}, and write
        the result to C{filename}.
        @return: True if rendering was successful.
        """
        s = self.render(language)
        if s is not None:
            out = open(filename, 'w')
            out.write(s)
            out.close()
            return True
        else:
            return False

    def render(self, language='gif'):
        """
        Use the C{dot} command to render this graph, using the output
        format C{language}.  Return the result as a string, or C{None}
        if the rendering failed.
        """
        try:
            from subprocess import Popen, PIPE
            cmd = [self.DOT_COMMAND, '-T%s' % language]
            pipe = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE,
                         close_fds=True)
            (to_child, from_child) = (pipe.stdin, pipe.stdout)
        except ImportError:
            from popen2 import Popen4
            cmd = '%s -T%s' % (self.DOT_COMMAND, language)
            pipe = Popen4(cmd)
            (to_child, from_child) = (pipe.tochild, pipe.fromchild)

        to_child.write(self.to_dotfile())
        to_child.close()
        result = ''
        while pipe.poll() is None:
            result += from_child.read()
        result += from_child.read()
        exitval = pipe.wait()
        
        if exitval:
            log.warning("Unable to render Graphviz dot graph:\n%s" %
                        from_child.read())
            return None

        return result

    def to_dotfile(self):
        """
        Return the string contents of the dot file that should be used
        to render this graph.
        """
        lines = ['digraph %s {' % self.uid,
                 'node [%s]' % ','.join(['%s="%s"' % (k,v) for (k,v)
                                         in self.node_defaults.items()]),
                 'edge [%s]' % ','.join(['%s="%s"' % (k,v) for (k,v)
                                         in self.edge_defaults.items()])]
        if self.body:
            lines.append(self.body)
        lines.append('/* Nodes */')
        for node in self.nodes:
            lines.append(node.to_dotfile())
        lines.append('/* Edges */')
        for edge in self.edges:
            lines.append(edge.to_dotfile())
        lines.append('}')
        return '\n'.join(lines)

class DotGraphNode:
    _next_id = 0
    def __init__(self, label=None, **attribs):
        if label is not None: attribs['label'] = label
        self.attribs = attribs
        self.id = self.__class__._next_id
        self.__class__._next_id += 1

    def to_dotfile(self):
        """
        Return the dot commands that should be used to render this node.
        """
        attribs = ','.join(['%s="%s"' % (k,v) for (k,v)
                            in self.attribs.items()])
        if attribs: attribs = ' [%s]' % attribs
        return 'node%d%s' % (self.id, attribs)

class DotGraphEdge:
    def __init__(self, start, end, label=None, **attribs):
        """
        @type start: L{DotGraphNode}
        @type end: L{DotGraphNode}
        """
        if label is not None: attribs['label'] = label
        self.start = start       #: @type: L{DotGraphNode}
        self.end = end           #: @type: L{DotGraphNode}
        self.attribs = attribs

    def to_dotfile(self):
        """
        Return the dot commands that should be used to render this edge.
        """
        attribs = ','.join(['%s="%s"' % (k,v) for (k,v)
                            in self.attribs.items()])
        if attribs: attribs = ' [%s]' % attribs
        return 'node%d -> node%d%s' % (self.start.id, self.end.id, attribs)

######################################################################
#{ Graph Generation Functions
######################################################################

def package_tree_graph(packages, linker, context=None, **options):
    """
    Return a L{DotGraph} that graphically displays the package
    hierarchies for the given packages.
    """
    graph = DotGraph('package',
                     node_defaults={'shape':'box', 'width': 0, 'height': 0},
                     edge_defaults={'sametail':True})
    
    # Options
    if options.get('dir', 'LR') != 'TB':
        graph.body += 'rankdir=%s\n' % options.get('dir', 'LR')

    # Get a list of all modules in the package.
    queue = list(packages)
    modules = Set(packages)
    for module in queue:
        queue.extend(module.submodules)
        modules.update(module.submodules)

    # Add a node for each module.
    nodes = {}
    modules = sorted(modules, key=lambda d:d.canonical_name)
    for i, module in enumerate(modules):
        url = linker.url_for(module)
        nodes[module] = DotGraphNode(module.canonical_name, href=url)
        graph.nodes.append(nodes[module])
        if module == context:
            attribs = nodes[module].attribs
            attribs.update({'fillcolor':'black', 'fontcolor':'white',
                            'style':'filled'})
            del attribs['href']

    # Add an edge for each package/submodule relationship.
    for module in modules:
        for submodule in module.submodules:
            graph.edges.append(DotGraphEdge(nodes[module], nodes[submodule]))

    return graph

# [xx] Use short names when possible, but long names when needed?
def class_tree_graph(bases, linker, context=None, **options):
    """
    Return a L{DotGraph} that graphically displays the package
    hierarchies for the given packages.
    """
    graph = DotGraph('class_hierarchy',
                     node_defaults={'shape':'box', 'width': 0, 'height': 0},
                     edge_defaults={'sametail':True})

    # Options
    if options.get('dir', 'LR') != 'TB':
        graph.body += 'rankdir=%s\n' % options.get('dir', 'LR')

    # Get a list of all classes derived from the given base(s).
    queue = list(bases)
    classes = Set(bases)
    for cls in queue:
        queue.extend(cls.subclasses)
        classes.update(cls.subclasses)

    # Add a node for each cls.
    nodes = {}
    classes = sorted(classes, key=lambda d:d.canonical_name)
    for i, cls in enumerate(classes):
        url = linker.url_for(cls)
        nodes[cls] = DotGraphNode(cls.canonical_name[-1], href=url)
        graph.nodes.append(nodes[cls])

    # Add an edge for each package/subcls relationship.
    for cls in classes:
        for subcls in cls.subclasses:
            graph.edges.append(DotGraphEdge(nodes[cls], nodes[subcls]))

    return graph

