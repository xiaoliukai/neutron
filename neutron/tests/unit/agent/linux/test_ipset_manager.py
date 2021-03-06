#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import mock
from oslo_config import cfg

from neutron.agent.common import config as a_cfg
from neutron.agent.linux import ipset_manager
from neutron.tests import base

TEST_SET_ID = 'fake_sgid'
ETHERTYPE = 'IPv4'
TEST_SET_NAME = ipset_manager.IpsetManager.get_name(TEST_SET_ID, ETHERTYPE)
TEST_SET_NAME_NEW = TEST_SET_NAME + ipset_manager.SWAP_SUFFIX
FAKE_IPS = ['10.0.0.1', '10.0.0.2', '10.0.0.3', '10.0.0.4',
            '10.0.0.5', '10.0.0.6']


class BaseIpsetManagerTest(base.BaseTestCase):
    def setUp(self, maxelem=None, hashsize=None):
        super(BaseIpsetManagerTest, self).setUp()
        cfg.CONF.register_opts(a_cfg.IPSET_OPTS, 'AGENT')
        cfg.CONF.set_override('ipset_maxelem', maxelem, 'AGENT')
        cfg.CONF.set_override('ipset_hashsize', hashsize, 'AGENT')
        self.maxelem = maxelem
        self.hashsize = hashsize
        self.ipset = ipset_manager.IpsetManager()
        self.execute = mock.patch.object(self.ipset, "execute").start()
        self.expected_calls = []
        self.expect_create()

    def verify_mock_calls(self):
        self.execute.assert_has_calls(self.expected_calls, any_order=False)

    def expect_set(self, addresses):
        hash_args = []
        if self.hashsize:
            hash_args.extend(['hashsize', str(self.hashsize)])
        if self.maxelem:
            hash_args.extend(['maxelem', str(self.maxelem)])
        temp_input = ['create IPv4fake_sgid-new hash:ip family inet %s' %
                      ' '.join(hash_args)]
        temp_input.extend('add IPv4fake_sgid-new %s' % ip for ip in addresses)
        input = '\n'.join(temp_input)
        self.expected_calls.extend([
            mock.call(['ipset', 'restore', '-exist'],
                      process_input=input,
                      run_as_root=True),
            mock.call(['ipset', 'swap', TEST_SET_NAME_NEW, TEST_SET_NAME],
                      process_input=None,
                      run_as_root=True),
            mock.call(['ipset', 'destroy', TEST_SET_NAME_NEW],
                      process_input=None,
                      run_as_root=True)])

    def expect_add(self, addresses):
        self.expected_calls.extend(
            mock.call(['ipset', 'add', '-exist', TEST_SET_NAME, ip],
                      process_input=None,
                      run_as_root=True) for ip in addresses)

    def expect_del(self, addresses):
        self.expected_calls.extend(
            mock.call(['ipset', 'del', TEST_SET_NAME, ip],
                      process_input=None,
                      run_as_root=True) for ip in addresses)

    def expect_create(self):
        ipset_call = ['ipset', 'create', '-exist', TEST_SET_NAME,
                      'hash:ip', 'family', 'inet']
        if self.hashsize:
            ipset_call.extend(['hashsize', str(self.hashsize)])
        if self.maxelem:
            ipset_call.extend(['maxelem', str(self.maxelem)])
        self.expected_calls.append(
            mock.call(ipset_call,
                      process_input=None,
                      run_as_root=True))

    def expect_destroy(self):
        self.expected_calls.append(
            mock.call(['ipset', 'destroy', TEST_SET_NAME],
                      process_input=None,
                      run_as_root=True))

    def add_first_ip(self):
        self.expect_set([FAKE_IPS[0]])
        self.ipset.set_members(TEST_SET_ID, ETHERTYPE, [FAKE_IPS[0]])

    def add_all_ips(self):
        self.expect_set(FAKE_IPS)
        self.ipset.set_members(TEST_SET_ID, ETHERTYPE, FAKE_IPS)


class IpsetManagerTestCase(BaseIpsetManagerTest):
    """Run all tests, but with maxelem/hashsize values not configured
    """
    def setUp(self):
        super(IpsetManagerTestCase, self).setUp()

    def test_set_exists(self):
        self.add_first_ip()
        self.assertTrue(self.ipset.set_exists(TEST_SET_ID, ETHERTYPE))

    def test_set_members_with_first_add_member(self):
        self.add_first_ip()
        self.verify_mock_calls()

    def test_set_members_adding_less_than_5(self):
        self.add_first_ip()
        self.expect_add(reversed(FAKE_IPS[1:5]))
        self.ipset.set_members(TEST_SET_ID, ETHERTYPE, FAKE_IPS[0:5])
        self.verify_mock_calls()

    def test_set_members_deleting_less_than_5(self):
        self.add_all_ips()
        self.expect_del(reversed(FAKE_IPS[4:5]))
        self.ipset.set_members(TEST_SET_ID, ETHERTYPE, FAKE_IPS[0:3])
        self.verify_mock_calls()

    def test_set_members_adding_more_than_5(self):
        self.add_first_ip()
        self.expect_set(FAKE_IPS)
        self.ipset.set_members(TEST_SET_ID, ETHERTYPE, FAKE_IPS)
        self.verify_mock_calls()

    def test_destroy(self):
        self.add_first_ip()
        self.expect_destroy()
        self.ipset.destroy(TEST_SET_ID, ETHERTYPE)
        self.verify_mock_calls()


class IpsetManagerTestCaseHashArgs(IpsetManagerTestCase):
    """Run all the above tests, but with maxelem/hashsize values configured
    """
    def setUp(self):
        super(IpsetManagerTestCase, self).setUp(maxelem=131072, hashsize=2048)
