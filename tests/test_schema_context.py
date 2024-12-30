import unittest
import sys

sys.path.append('../')
sys.path.append('.')
from sysrepocli import SchemaContext, ContextNode
from sysrepo.session import SysrepoSession
from sysrepo.connection import SysrepoConnection


class TestSchemaContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
         conn = SysrepoConnection()
         sess = conn.start_session()
         cls.sess = sess
         cls.conn = conn
         cls.schema_context = SchemaContext(sess)

    @classmethod
    def tearDownClass(cls):
        cls.sess.stop()
        cls.conn.disconnect()

    def test_get_ctx_empty(self):
        nodes = self.schema_context.get_ctx([])
        self.assertEqual(len(nodes), 0)

    def test_get_ctx_config(self):
        nodes = self.schema_context.get_ctx(['interfaces', 'interface', 'name'], is_config=True)
        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0].snode.name(), 'interfaces')
        self.assertEqual(nodes[1].snode.name(), 'interface')
        self.assertEqual(nodes[1].list_keys, ['name'])

    def test_get_ctx_config(self):
        nodes = self.schema_context.get_ctx(['interfaces', 'interface', 'name'], is_config=True)
        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0].snode.name(), 'interfaces')
        self.assertEqual(nodes[1].snode.name(), 'interface')
        self.assertEqual(nodes[1].list_keys, ['name'])


    def test_get_ctx_config_partial_name(self):
        nodes = self.schema_context.get_ctx(['int', 'int', 'name'], is_config=True)
        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0].snode.name(), 'interfaces')
        self.assertEqual(nodes[1].snode.name(), 'interface')
        self.assertEqual(nodes[1].list_keys, ['name'])

    def test_get_ctx_config_partial_name_leaf(self):
        nodes = self.schema_context.get_ctx(['int', 'int', 'name', 'admin-status'], is_config=True)
        self.assertEqual(len(nodes), 3)
        self.assertEqual(nodes[0].snode.name(), 'interfaces')
        self.assertEqual(nodes[1].snode.name(), 'interface')
        self.assertEqual(nodes[1].list_keys, ['name'])
        self.assertEqual(nodes[2].snode.name(), 'admin-status')

if __name__ == '__main__':
    unittest.main()