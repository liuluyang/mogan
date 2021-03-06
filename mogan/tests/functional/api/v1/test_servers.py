#
# Copyright 2016 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import fixtures
import mock
import six

from mogan.tests.functional.api import v1 as v1_test


def _get_fake_image(**kwargs):
    attrs = {u'status': u'active',
             u'tags': [],
             u'kernel_id': u'fd24d91a-dfd5-4a3c-b990-d4563eb27396',
             u'container_format': u'ami',
             u'min_ram': 0,
             u'ramdisk_id': u'd629522b-ebaa-4c92-9514-9e31fe760d18',
             u'updated_at': u'2016-06-20T13: 34: 41Z',
             u'visibility': u'public',
             u'owner': u'6824974c08974d4db864bbaa6bc08303',
             u'file': u'/v2/images/fda54a44-3f96-40bf-ab07-0a4ce9e1761d/file',
             u'min_disk': 0,
             u'virtual_size': None,
             u'id': u'b8f82429-3a13-4ffe-9398-4d1abdc256a8',
             u'size': 25165824,
             u'name': u'cirros-0.3.4-x86_64-uec',
             u'checksum': u'eb9139e4942121f22bbc2afc0400b2a4',
             u'created_at': u'2016-06-20T13: 34: 40Z',
             u'disk_format': u'ami',
             u'protected': False,
             u'schema': u'/v2/schemas/image'}
    attrs.update(kwargs)
    return type('Image', (object,), attrs)


class TestServers(v1_test.APITestV1):
    FLAVOR_UUID = 'ff28b5a2-73e5-431c-b4b7-1b96b74bca7b'

    SERVER_UUIDS = ['59f1b681-6ca4-4a17-b784-297a7285004e',
                    '2b32fc87-576c-481b-880e-bef8c7351746',
                    '482decff-7561-41ad-9bfb-447265b26972',
                    '427693e1-a820-4d7d-8a92-9f5fe2849399',
                    '253b2878-ec60-4793-ad19-e65496ec7aab',
                    'f26f181d-7891-4720-b022-b074ec1733ef',
                    '02f53bd8-3514-485b-ba60-2722ef09c016',
                    '8f7495fe-5e44-4f33-81af-4b28e9b2952f']

    def setUp(self):
        self.rpc_api = mock.Mock()
        self.useFixture(fixtures.MockPatch('mogan.engine.rpcapi.EngineAPI',
                                           return_value=self.rpc_api))
        self.image_api = mock.Mock()
        self.useFixture(fixtures.MockPatch('mogan.image.api.API',
                                           return_value=self.image_api))
        self.network_api = mock.Mock()
        self.useFixture(fixtures.MockPatch('mogan.network.api.API',
                                           return_value=self.network_api))
        self.image_api.get.return_value = _get_fake_image()
        self.network_api.validate_networks.return_value = 100
        super(TestServers, self).setUp()
        self._prepare_flavor()

    def _clean_servers(self):
        for server_uuid in self.SERVER_UUIDS:
            # TODO(liusheng) should catch the NotFound exception
            self.delete('/servers/' + server_uuid, status=204,
                        expect_errors=True)

    def _make_app(self):
        return super(TestServers, self)._make_app()

    @mock.patch('oslo_utils.uuidutils.generate_uuid')
    def _prepare_flavor(self, mocked):
        mocked.side_effect = [self.FLAVOR_UUID]
        headers = self.gen_headers(self.context, roles="admin")
        body = {"name": "type_for_server_testing",
                "description": "type for server testing",
                "resources": {"CUSTOM_GOLD": 1}}
        self.post_json('/flavors', body, headers=headers, status=201)

    @mock.patch('mogan.scheduler.rpcapi.SchedulerAPI.select_destinations')
    @mock.patch('oslo_utils.uuidutils.generate_uuid')
    def _prepare_server(self, amount, mocked, mock_select_dest):
        # NOTE(wanghao): Since we added quota reserve in creation option,
        # there is one more generate_uuid out of provision_servers, so
        # amount should *2 here.
        mocked.side_effect = self.SERVER_UUIDS[:(amount * 2)]
        mock_select_dest.return_value = mock.MagicMock()
        responses = []
        headers = self.gen_headers(self.context)
        for i in six.moves.xrange(amount):
            test_body = {
                "name": "test_server_" + str(i),
                "description": "just test server " + str(i),
                'flavor_uuid': self.FLAVOR_UUID,
                'image_uuid': 'b8f82429-3a13-4ffe-9398-4d1abdc256a8',
                'networks': [
                    {'net_id': 'c1940655-8b8e-4370-b8f9-03ba1daeca31'}
                ],
                'metadata': {'fake_key': 'fake_value'}
            }
            responses.append(
                self.post_json('/servers', test_body, headers=headers,
                               status=201))
        return responses

    def test_server_post(self):
        resp = self._prepare_server(1)[0].json
        self.assertEqual('test_server_0', resp['name'])
        self.assertEqual('building', resp['status'])
        self.assertEqual(self.SERVER_UUIDS[1], resp['uuid'])
        self.assertEqual('just test server 0', resp['description'])
        self.assertEqual(self.FLAVOR_UUID, resp['flavor_uuid'])
        self.assertEqual('b8f82429-3a13-4ffe-9398-4d1abdc256a8',
                         resp['image_uuid'])
        self.assertIsNone(resp['availability_zone'])
        self.assertEqual([], resp['nics'])
        self.assertEqual({'fake_key': 'fake_value'}, resp['metadata'])
        self.assertIn('links', resp)
        self.assertIn('created_at', resp)
        self.assertIn('updated_at', resp)
        self.assertIn('nics', resp)
        self.assertIn('project_id', resp)
        self.assertIn('launched_at', resp)

    def test_destroy_flavor_in_use(self):
        self._prepare_server(1)
        headers = self.gen_headers(self.context, roles="admin")
        self.delete('/flavors/' + self.FLAVOR_UUID,
                    headers=headers, status=409)

    def test_server_show(self):
        self._prepare_server(1)
        headers = self.gen_headers(self.context)
        resp = self.get_json('/servers/%s' % self.SERVER_UUIDS[1],
                             headers=headers)
        self.assertEqual('test_server_0', resp['name'])
        self.assertEqual('building', resp['status'])
        self.assertEqual(self.SERVER_UUIDS[1], resp['uuid'])
        self.assertEqual('just test server 0', resp['description'])
        self.assertEqual(self.FLAVOR_UUID, resp['flavor_uuid'])
        self.assertEqual('b8f82429-3a13-4ffe-9398-4d1abdc256a8',
                         resp['image_uuid'])
        self.assertIsNone(resp['availability_zone'])
        self.assertEqual([], resp['nics'])
        self.assertEqual({'fake_key': 'fake_value'}, resp['metadata'])
        self.assertIn('links', resp)
        self.assertIn('created_at', resp)
        self.assertIn('updated_at', resp)
        self.assertIn('nics', resp)
        self.assertIn('project_id', resp)
        self.assertIn('launched_at', resp)

    def test_server_list(self):
        self._prepare_server(4)
        headers = self.gen_headers(self.context)
        resps = self.get_json('/servers', headers=headers)['servers']
        self.assertEqual(4, len(resps))
        self.assertEqual('test_server_0', resps[0]['name'])
        self.assertEqual('just test server 0', resps[0]['description'])
        self.assertEqual('building', resps[0]['status'])

    def test_server_list_with_details(self):
        self._prepare_server(4)
        headers = self.gen_headers(self.context)
        resps = self.get_json('/servers/detail',
                              headers=headers)['servers']
        self.assertEqual(4, len(resps))
        self.assertEqual(16, len(resps[0].keys()))
        self.assertEqual('test_server_0', resps[0]['name'])
        self.assertEqual('just test server 0', resps[0]['description'])
        self.assertEqual('building', resps[0]['status'])
        self.assertEqual('ff28b5a2-73e5-431c-b4b7-1b96b74bca7b',
                         resps[0]['flavor_uuid'])
        self.assertEqual('b8f82429-3a13-4ffe-9398-4d1abdc256a8',
                         resps[0]['image_uuid'])

        # Test with filters
        # Filter with server name
        resps = self.get_json('/servers/detail?name=test_server_0',
                              headers=headers)['servers']
        self.assertEqual(1, len(resps))
        resps = self.get_json('/servers/detail?name=test',
                              headers=headers)['servers']
        self.assertEqual(4, len(resps))
        # Filter with server status
        resps = self.get_json('/servers/detail?status=building',
                              headers=headers)['servers']
        self.assertEqual(4, len(resps))
        resps = self.get_json('/servers/detail?status=active',
                              headers=headers)['servers']
        self.assertEqual(0, len(resps))
        # Filter with flavor uuid
        search_opt = "flavor_uuid=ff28b5a2-73e5-431c-b4b7-1b96b74bca7b"
        resps = self.get_json('/servers/detail?' + search_opt,
                              headers=headers)['servers']
        self.assertEqual(4, len(resps))
        # Filter with image uuid
        search_opt = "image_uuid=b8f82429-3a13-4ffe-9398-4d1abdc256a8"
        resps = self.get_json('/servers/detail?' + search_opt,
                              headers=headers)['servers']
        self.assertEqual(4, len(resps))

    def test_server_delete(self):
        self._prepare_server(4)
        headers = self.gen_headers(self.context)
        self.delete('/servers/' + self.SERVER_UUIDS[1], headers=headers,
                    status=204)
        resp = self.get_json('/servers/%s' % self.SERVER_UUIDS[1],
                             headers=headers)
        self.assertEqual('deleting', resp['status'])
