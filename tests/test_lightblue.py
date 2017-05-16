# -*- coding: utf-8 -*-
#
# Copyright (c) 2017  Red Hat, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import json
import unittest

from mock import patch
from six.moves import http_client

from freshmaker.lightblue import ContainerImage
from freshmaker.lightblue import ContainerRepository
from freshmaker.lightblue import LightBlue
from freshmaker.lightblue import LightBlueRequestFailure


class TestLightBlueRequestFailure(unittest.TestCase):
    """Test case for exception LightBlueRequestFailure"""

    def setUp(self):
        self.fake_error_data = {
            'entity': 'containerImage',
            'entityVersion': '0.0.11',
            'errors': [
                {
                    'context': 'rest/FindCommand/containerImage/find(containerImage:0.0.11)/'
                               'containerImage/parsed_data/rpm_manifes',
                    'errorCode': 'metadata:InvalidFieldReference',
                    'msg': 'rpm_manifes in parsed_data.rpm_manifes.*.nvra',
                    'objectType': 'error'
                }
            ],
            'hostname': 'lightbluecrud1.dev2.a1.vary.redhat.com',
            'matchCount': 0,
            'modifiedCount': 0,
            'status': 'ERROR'
        }
        self.e = LightBlueRequestFailure(self.fake_error_data,
                                         http_client.INTERNAL_SERVER_ERROR)

    def test_get_raw_error_json_data(self):
        self.assertEqual(self.fake_error_data, self.e.raw)

    def test_get_status_code(self):
        self.assertEqual(http_client.INTERNAL_SERVER_ERROR, self.e.status_code)

    def test_get_inner_errors(self):
        self.assertEqual(self.fake_error_data['errors'], self.e.errors)

    def test_errors_listed_in_str(self):
        expected_s = '\n'.join(('    {}'.format(err['msg'])
                                for err in self.fake_error_data['errors']))
        self.assertIn(expected_s, str(self.e))


class TestContainerImageObject(unittest.TestCase):

    def test_create(self):
        image = ContainerImage.create({
            '_id': '1233829',
            'brew': {
                'completion_date': '20151210T10:09:35.000-0500',
                'build': 'jboss-webserver-3-webserver30-tomcat7-openshift-docker-1.1-6',
                'package': 'jboss-webserver-3-webserver30-tomcat7-openshift-docker'
            }
        })

        self.assertEqual('1233829', image['_id'])
        self.assertEqual('20151210T10:09:35.000-0500', image['brew']['completion_date'])


class TestContainerRepository(unittest.TestCase):

    def test_create(self):
        image = ContainerRepository.create({
            'creationDate': '20160927T11:14:56.420-0400',
            'metrics': {
                'pulls_in_last_30_days': 0,
                'last_update_date': '20170223T08:28:40.913-0500'
            }
        })

        self.assertEqual('20160927T11:14:56.420-0400', image['creationDate'])
        self.assertEqual(0, image['metrics']['pulls_in_last_30_days'])
        self.assertEqual('20170223T08:28:40.913-0500', image['metrics']['last_update_date'])


class TestLightBlue(unittest.TestCase):

    def setUp(self):
        self.fake_server_url = 'lightblue.localhost'
        self.fake_cert_file = 'path/to/cert'
        self.fake_private_key = 'path/to/private-key'

    @patch('freshmaker.lightblue.requests.post')
    def test_find_container_images(self, post):
        post.return_value.status_code = http_client.OK
        post.return_value.json.return_value = {
            'modifiedCount': 0,
            'resultMetadata': [],
            'entityVersion': '0.0.12',
            'hostname': self.fake_server_url,
            'matchCount': 2,
            'processed': [
                {
                    '_id': '57ea8d1f9c624c035f96f4b0',
                    'image_id': 'e0f97342ddf6a09972434f98837b5fd8b5bed9390f32f1d63e8a7e4893208af7',
                    'brew': {
                        'completion_date': '20151210T10:09:35.000-0500',
                        'build': 'jboss-webserver-3-webserver30-tomcat7-openshift-docker-1.1-6',
                        'package': 'jboss-webserver-3-webserver30-tomcat7-openshift-docker'
                    },
                },
                {
                    '_id': '57ea8d289c624c035f96f4db',
                    'image_id': 'c1ef3345f36b901b0bddc7ab01ea3f3c83c886faa243e02553f475124eb4b46c',
                    'brew': {
                        'package': 'sadc-docker',
                        'completion_date': '20151203T00:35:30.000-0500',
                        'build': 'sadc-docker-7.2-7'
                    },
                }
            ],
            'status': 'COMPLETE',
            'entity': 'containerImage'
        }

        fake_request = {
            "objectType": "containerImage",
            "projection": [
                {"field": "_id", "include": True},
                {"field": "image_id", "include": True},
                {"field": "brew", "include": True, "recursive": True},
            ],
        }

        with patch('os.path.exists'):
            lb = LightBlue(server_url=self.fake_server_url,
                           cert=self.fake_cert_file,
                           private_key=self.fake_private_key)
            images = lb.find_container_images(request=fake_request)

        post.assert_called_once_with(
            '{}/{}/{}'.format(lb.api_root,
                              'find/containerImage',
                              LightBlue.ENTITY_VERSION_CONTAINER_IMAGE),
            data=json.dumps(fake_request),
            verify=lb.verify_ssl,
            cert=(self.fake_cert_file, self.fake_private_key),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(2, len(images))

        image = images[0]
        self.assertEqual('57ea8d1f9c624c035f96f4b0', image['_id'])
        self.assertEqual('jboss-webserver-3-webserver30-tomcat7-openshift-docker',
                         image['brew']['package'])

    @patch('freshmaker.lightblue.requests.post')
    def test_find_container_repositories(self, post):
        post.return_value.status_code = http_client.OK
        post.return_value.json.return_value = {
            'entity': 'containerRepository',
            'status': 'COMPLETE',
            'modifiedCount': 0,
            'matchCount': 2,
            'processed': [
                {
                    'creationDate': '20160927T11:14:56.420-0400',
                    'metrics': {
                        'pulls_in_last_30_days': 0,
                        'last_update_date': '20170223T08:28:40.913-0500'
                    }
                },
                {
                    'creationDate': '20161020T04:52:43.365-0400',
                    'metrics': {
                        'last_update_date': '20170501T03:00:19.892-0400',
                        'pulls_in_last_30_days': 20
                    }
                }
            ],
            'entityVersion': '0.0.11',
            'hostname': self.fake_server_url,
            'resultMetadata': []
        }

        fake_request = {
            "objectType": "containerRepository",
            "projection": [
                {"field": "creationDate", "include": True},
                {"field": "metrics", "include": True, "recursive": True}
            ],
        }

        with patch('os.path.exists'):
            lb = LightBlue(server_url=self.fake_server_url,
                           cert=self.fake_cert_file,
                           private_key=self.fake_private_key)
            repos = lb.find_container_repositories(request=fake_request)

        post.assert_called_once_with(
            '{}/{}/{}'.format(lb.api_root,
                              'find/containerRepository',
                              LightBlue.ENTITY_VERSION_CONTAINER_REPOSITORY),
            data=json.dumps(fake_request),
            verify=lb.verify_ssl,
            cert=(self.fake_cert_file, self.fake_private_key),
            headers={'Content-Type': 'application/json'}
        )

        self.assertEqual(2, len(repos))

        repo = repos[0]
        self.assertEqual('20160927T11:14:56.420-0400', repo['creationDate'])
        self.assertEqual(0, repo['metrics']['pulls_in_last_30_days'])
        self.assertEqual('20170223T08:28:40.913-0500', repo['metrics']['last_update_date'])

    @patch('freshmaker.lightblue.requests.post')
    def test_raise_error_if_request_data_is_incorrect(self, post):
        post.return_value.status_code = http_client.INTERNAL_SERVER_ERROR
        post.return_value.json.return_value = {
            'entity': 'containerImage',
            'entityVersion': '0.0.11',
            'errors': [
                {
                    'context': 'rest/FindCommand/containerImage/find(containerImage:0.0.11)/'
                               'containerImage/parsed_data/rpm_manifes',
                    'errorCode': 'metadata:InvalidFieldReference',
                    'msg': 'rpm_manifes in parsed_data.rpm_manifes.*.nvra',
                    'objectType': 'error'
                }
            ],
            'hostname': 'lightbluecrud1.dev2.a1.vary.redhat.com',
            'matchCount': 0,
            'modifiedCount': 0,
            'status': 'ERROR'
        }

        fake_request = {
            "objectType": "containerRepository",
            "projection": [
                {"fiel": "creationDate", "include": True},
            ],
        }

        with patch('os.path.exists'):
            lb = LightBlue(server_url=self.fake_server_url,
                           cert=self.fake_cert_file,
                           private_key=self.fake_private_key)
            self.assertRaises(LightBlueRequestFailure,
                              lb._make_request, 'find/containerRepository/', fake_request)
