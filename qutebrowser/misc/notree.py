# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2019 Giuseppe Stelluto (pinusc) <giuseppe@gstelluto.com>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Tree library for tree-tabs.

The fundamental unit is the Node class.

Create a tree with with Node(value, parent):
root = Node('foo')
child = Node('bar', root)
child2 = Node('baz', root)
child3 = Node('lorem', child)

You can also assign parent after instantiation, or even reassign it:
child4 = Node('ipsum')
child4.parent = root

Assign children:
child.children = []
child2.children = [child4, child3]
child3.parent
> Node('foo/bar/baz')

Render a tree with render_tree(root_node):
render_tree(root)

> ('', 'foo')
> ('├─', 'bar')
> ('│ ├─', 'lorem')
> ('│ └─', 'ipsum')
> ('└─', 'baz')
"""
import enum
import typing

# For Node.render
CORNER = '└─'
INTERSECTION = '├─'
PIPE = '│'


class TreeError(RuntimeError):
    """Exception used for tree-related errors."""


class TraverseOrder(enum.Enum):
    """To be used as argument to traverse().

    Implemented orders are pre-order and post-order.
    Attributes:
        PRE: pre-order (parents before children). Same as in Node.render
        POST: children of a node are always yield before their parent.
        POST_R: Like POST, but children are yield in reverse order
    """

    PRE = 'pre-order'
    POST = 'post-order'
    POST_R = 'post-order-reverse'


class Node():
    """Fundamental unit of notree library.

    Attributes:
        value: The element (ususally a tab) the node represents
        parent: Node's parent.
        children: Node's children elements.
        siblings: Children of parent node that are not self.
        path: List of nodes from root of tree to self
    value, parent, and children can all be set by user. Everything else will be
    updated accordingly, so that if `node.parent = root_node`, then `node in
    root_node.children` will be True.
    """

    sep: str = '/'
    __parent: typing.Optional['Node'] = None
    __uid: int
    __last_uid: int = 0  # this is a global 'static' class attribute

    PARENT_TYPE = typing.TypeVar('PARENT_TYPE')

    def __init__(self,
                 value: PARENT_TYPE,
                 parent: typing.Optional['Node'] = None,
                 childs: typing.Sequence['Node'] = (),
                 uid: typing.Optional[int] = None) -> None:
        if uid is not None:
            self.__uid = uid  # TODO find a way to check if given ID exists already
        else:
            self.__uid = self.__get_new_uid()

        self.value = value
        # set initial values so there's no need for AttributeError checks
        self.__parent = None  # type: typing.Optional['Node']
        self.__children = []  # type: typing.List['Node']

        # For render memoization
        self.__modified = False
        self.__set_modified()  # not the same as line above
        self.__rendered = []  # type: typing.List[typing.Tuple[str, 'Node']]

        if parent:
            self.parent = parent  # calls setter
        if childs:
            self.children = childs  # this too

        self.__collapsed = False

    @property
    def uid(self) -> int:
        return self.__uid

    @property
    def parent(self) -> typing.Optional['Node']:
        return self.__parent

    @parent.setter
    def parent(self, value) -> None:
        """Set parent property. Also adds self to value.children."""
        # pylint: disable=protected-access
        assert(value is None or isinstance(value, Node))
        if self.__parent:
            self.__parent.__disown(self)
            self.__parent = None
        if value is not None:
            value.__add_child(self)
            self.__parent = value
        self.__set_modified()

    @property
    def children(self) -> typing.Sequence['Node']:
        return tuple(self.__children)

    @children.setter
    def children(self, value: typing.Sequence['Node']):
        """Set children property, preserving order.

        Also sets n.parent = self for n in value. Does not allow duplicates.
        """
        seen = set(value)
        if len(seen) != len(value):
            raise TreeError("A duplicate item is present in in %r" % value)
        new_children = list(value)
        for child in new_children:
            if child.parent is not self:
                child.parent = self
        self.__children = new_children
        self.__set_modified()

    @property
    def path(self) -> typing.List['Node']:
        """Get a list of all nodes from the root node to self."""
        if self.parent is None:
            return [self]
        else:
            return self.parent.path + [self]

    @property
    def siblings(self) -> typing.Iterable['Node']:
        """Get siblings. Can not be set."""
        if self.parent:
            return (i for i in self.parent.children if i is not self)
        else:
            return ()

    @property
    def index(self) -> int:
        """Get self's position among its siblings (self.parent.children)"""
        return self.parent.children.index(self)

    @property
    def collapsed(self) -> bool:
        return self.__collapsed

    @collapsed.setter
    def collapsed(self, val: bool) -> None:
        self.__collapsed = val
        self.__set_modified()

    def __set_modified(self) -> None:
        """If self is modified, every ancestor is modified as well."""
        for node in self.path:
            node.__modified = True  # pylint: disable=protected-access

    def render(self) -> typing.Iterable[typing.Tuple[str, "Node"]]:
        """Render a tree with ascii symbols.

        Tabs appear in the same order as in traverse() with TraverseOrder.PRE
        Args:
            node; the root of the tree to render

        Return: list of tuples where the first item is the symbol,
                and the second is the node it refers to
        """
        if not self.__modified:
            return self.__rendered

        result = [('', self)]
        for child in self.children:
            if child.children:
                subtree = child.render()
                if child is not self.children[-1]:
                    subtree = [(PIPE + ' ' + c, n) for c, n in subtree]
                    char = INTERSECTION
                else:
                    subtree = [('  ' + c, n) for c, n in subtree]
                    char = CORNER
                subtree[0] = (char, subtree[0][1])
                if child.collapsed:
                    result += [subtree[0]]
                else:
                    result += subtree
            else:
                if child is self.children[-1]:
                    result.append((CORNER, child))
                else:
                    result.append((INTERSECTION, child))
        self.__modified = False
        self.__rendered = result
        return result

    def traverse(self, order: TraverseOrder = TraverseOrder.PRE,
                 render_collapsed: bool = True) -> typing.Iterable['Node']:
        """Generator for all descendants of `self`.

        Args:
            order: a TraverseOrder object. See TraverseOrder documentation.
            render_collapsed: whether to yield children of collapsed nodes
        Even if render_collapsed is False, collapsed nodes will be rendered.
        It's their children that won't.
        """
        if order == TraverseOrder.PRE:
            yield self

        f = reversed if order is TraverseOrder.POST_R else tuple
        for child in f(self.children):
            if render_collapsed or not child.collapsed:
                yield from child.traverse(order)
            else:
                yield child
        if order in [TraverseOrder.POST, TraverseOrder.POST_R]:
            yield self

    def __add_child(self, node: 'Node') -> None:
        if node not in self.__children:
            self.__children.append(node)

    def __disown(self, value: 'Node') -> None:
        self.__set_modified()
        if value in self.__children:
            self.__children.remove(value)

    def __get_new_uid(self) -> int:
        Node.__last_uid += 1
        return Node.__last_uid

    def get_descendent_by_uid(self, uid: int) -> 'Node':
        for descendent in self.traverse():
            if descendent.uid == uid:
                return descendent

    def __repr__(self) -> str:
        try:
            value = str(self.value.url().url())
        except:
            value = str(self.value)
        return "<Node -%d- '%s'>" % (self.__uid, value)

    def __str__(self) -> str:
        # return "<Node '%s'>" % self.value
        return str(self.value)
