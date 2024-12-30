import sysrepo
from libyang.schema import SNode, SContainer, SList, SLeaf, SLeafList
from dataclasses import dataclass

import sysrepo.session
from .utils import find_only


@dataclass
class ContextNode:
    snode: SNode
    list_keys: list[str]
    leaf_value: str


class SchemaContext:
    def __init__(self, session: sysrepo.session.SysrepoSession=None):
        self.session = session
        self.config_nodes = []  # type: list[SNode]
        self.status_nodes = []  # type: list[SNode]

        if session is not None:
            ctx = self.session.acquire_context()
            for mod in ctx:
                for snode in mod.children():
                    if snode.config_false():
                        self.status_nodes.append(snode)
                    elif isinstance(snode, SContainer):
                        self.config_nodes.append(snode)

    def get_ctx(self, path: list[str], is_config=True) -> list[ContextNode]:
        """Get context for a path.
        For example, the path is `int int eth0 admin-status`, the result is:
        [
            {
                "snode": <SNode for ietf-interfaces:interfaces>,
                "list_keys": [],
                "leaf_value": None
            },
            {
                "snode": <SNode for ietf-interfaces:interface>,
                "list_keys": ["eth0"],
                "leaf_value": None
            },
            {
                "snode": <SNode for ietf-interfaces:admin-status>,
                "list_keys": [],
                "leaf_value": None
            }
        ]
        """
        result = []
        if not path:
            return result
        # find the root node
        top_level = path[0]
        top_schema = self.status_nodes
        if is_config:
            top_schema = self.config_nodes
        
        root = find_only(top_schema, lambda x: x.name().startswith(top_level))
        if root is None:
            return result
        # add item in result
        result.append(ContextNode(root, [], None))

        fetched_key = True
        schema_node = root
        index = 1
        while index < len(path):
            item = path[index]
            if not fetched_key:
                if isinstance(schema_node, SList):
                    key_val = item
                    fetched_key = True
                    result.append(ContextNode(schema_node, [key_val], None))
            elif isinstance(schema_node, SList) or isinstance(schema_node, SContainer):
                # we expect the field name
                field = find_only(schema_node.children(), lambda x: x.name().startswith(item))
                if field is None:
                    return []
                if isinstance(field, SLeafList) or isinstance(field, SLeaf):
                    result.append(ContextNode(field, [], item))
                elif isinstance(field, SContainer):
                    result.append(ContextNode(field, [], None))
                    schema_node = field
                elif isinstance(field, SList):
                    schema_node = field
                    fetched_key = False
            elif isinstance(schema_node, SLeafList) or isinstance(schema_node, SLeaf):
                result[-1].leaf_value = item
                return result
            index += 1
        # if the last item is list, and key is not provided
        if isinstance(schema_node, SList) and not fetched_key:
            result.append(ContextNode(schema_node, [], None))
        return result
    