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

    def is_leaf(self):
        return isinstance(self.snode, SLeaf) or isinstance(self.snode, SLeafList)
    
    def is_list(self):
        return isinstance(self.snode, SList)
    
    def is_container(self):
        return isinstance(self.snode, SContainer)


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
    
    def ctx_to_xpath(self, ctx: list[ContextNode]) -> str:
        result = []
        mod = ""
        for node in ctx:
            if node.list_keys:
                if isinstance(node.snode, SList):
                    if mod != node.snode.module().name():
                        mod = node.snode.module().name()
                        s = f"{node.snode.module().name()}:{node.snode.name()}"
                    else:
                        s = f"{node.snode.name()}"
                    keys = node.snode.keys()
                    index = 0
                    for key in keys:
                        v = node.list_keys[index]
                        s += f"[{key.name()}='{v}']"
                        index += 1
                    result.append(s)
            else:
                if mod != node.snode.module().name():
                    mod = node.snode.module().name()
                    s = f"{node.snode.module().name()}:{node.snode.name()}"
                else:
                    s = f"{node.snode.name()}"
                result.append(s)
        return "/" + "/".join(result)
    
    def show_available_commands(self, prefix: list[str], is_status) -> dict[str, str]:
        """
        Get available commands for `show` command.
        prefix: the prefix of the command, e.g. `show interfaces`
        Return a dict of available commands.
        """
        if not prefix:
            if is_status:
                return {
                    s.name(): s.description()
                    for s in self.status_nodes
                }
            else:
                return {
                    s.name(): s.description()
                    for s in self.config_nodes
                }
        ctx = self.get_ctx(prefix, is_config=(not is_status))
        if not ctx:
            return {}
        last_node = ctx[-1]
        if isinstance(last_node.snode, SList):
            # if it does not have a key, then wait for the key
            if not last_node.list_keys:
                return {}
            # return a dict for all the child items
            return {
                child.name(): child.description()
                for child in last_node.snode.children()
                if (child.config_false() == is_status)
            }
        elif isinstance(last_node.snode, SContainer):
            # return a dict for all the child items
            return {
                child.name(): child.description()
                for child in last_node.snode.children()
                if (child.config_false() == is_status)
            }
        elif isinstance(last_node.snode, SLeaf):
            # if it is a leaf, then return empty
            return {
            }
    
    def get(self, xpath: str, include_default=False):
        # get operational state
        self.session.switch_datastore("operational")
        return self.session.get_data(xpath, include_implicit_defaults=include_default)
    
    def get_config(self, xpath: str, include_default=False):
        self.session.switch_datastore("running")
        return self.session.get_data(xpath, include_implicit_defaults=include_default)
    
    def print_data(self, data: any, level=0, listname=""):
        """
        Print the data returned by get_config or get.
        """
        if isinstance(data, dict):
            for k, v in data.items():
                # if v is string or number, print it along with k
                if isinstance(v, (str, int, float)):
                    print("  " * level, k, v)
                    continue
                elif isinstance(v, list):
                    self.print_data(v, level, k)
                    continue
                print("  " * level, k)
                self.print_data(v, level + 1)
        elif isinstance(data, list):
            for v in data:
                print("  " * level, listname)
                self.print_data(v, level + 1)
        else:
            print("  " * level, data)
