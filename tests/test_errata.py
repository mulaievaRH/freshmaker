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

import unittest

from mock import patch

from freshmaker.errata import Errata
from freshmaker.events import BrewSignRPMEvent, GitRPMSpecChangeEvent


class MockedErrataAPI(object):
    """
    Class mocking methods accessing Errata API in Errata class.
    """
    def __init__(self, errata_rest_get, errata_http_get=None):
        errata_rest_get.side_effect = (self.errata_rest_get)
        if errata_http_get:
            errata_http_get.side_effect = self.errata_http_get

        self.builds_json = {
            "PRODUCT1": [
                {
                    "libntirpc-1.4.3-4.el6rhs":
                    {
                        "PRODUCT1-3.2-NFS":
                            {"x86_64": ["libntirpc-devel-1.4.3-4.el6rhs.x86_64.rpm"],
                             "SRPMS": ["libntirpc-1.4.3-4.el6rhs.src.rpm"]}
                    }
                }
            ],
            "PRODUCT2": [
                {
                    "libntirpc-1.4.3-4.el7rhgs":
                    {
                        "PRODUCT2-3.2-NFS":
                            {"x86_64": ["libntirpc-devel-1.4.3-4.el7rhgs.x86_64.rpm"],
                             "SRPMS": ["libntirpc-1.4.3-4.el7rhgs.src.rpm"]}
                    }
                }
            ]
        }

        self.builds = {}
        self.builds["libntirpc-1.4.3-4.el6rhs"] = {
            "all_errata": [{"id": 28484, "name": "RHSA-2017:28484", "status": "QE"}],
            "rpms_signed": True}
        self.builds["libntirpc-1.4.3-4.el7rhgs"] = {
            "all_errata": [{"id": 28484, "name": "RHSA-2017:28484", "status": "QE"}],
            "rpms_signed": True}

    def errata_rest_get(self, endpoint):
        if endpoint.find("build/") != -1:
            nvr = endpoint.split("/")[-1]
            return self.builds[nvr]

    def errata_http_get(self, endpoint):
        if endpoint.endswith("builds.json"):
            return self.builds_json


class TestErrata(unittest.TestCase):
    def setUp(self):
        self.errata = Errata("https://localhost/")

    @patch.object(Errata, "_errata_rest_get")
    def test_advisories_from_event(self, errata_rest_get):
        MockedErrataAPI(errata_rest_get)
        event = BrewSignRPMEvent("msgid", "libntirpc-1.4.3-4.el7rhgs")
        advisories = self.errata.advisories_from_event(event)
        self.assertEqual(len(advisories), 1)
        self.assertEqual(advisories[0].errata_id, 28484)

    @patch.object(Errata, "_errata_rest_get")
    def test_advisories_from_event_missing_all_errata(self, errata_rest_get):
        mocked_errata = MockedErrataAPI(errata_rest_get)
        del mocked_errata.builds["libntirpc-1.4.3-4.el7rhgs"]["all_errata"]

        event = BrewSignRPMEvent("msgid", "libntirpc-1.4.3-4.el7rhgs")
        advisories = self.errata.advisories_from_event(event)
        self.assertEqual(len(advisories), 0)

    def test_advisories_from_event_unsupported_event(self):
        event = GitRPMSpecChangeEvent("msgid", "libntirpc", "master", "foo")
        with self.assertRaises(ValueError):
            self.errata.advisories_from_event(event)

    @patch.object(Errata, "_errata_rest_get")
    @patch.object(Errata, "_errata_http_get")
    def test_builds_signed_all_signed(self, errata_http_get, errata_rest_get):
        MockedErrataAPI(errata_rest_get, errata_http_get)
        self.assertTrue(self.errata.builds_signed(28484))

    @patch.object(Errata, "_errata_rest_get")
    @patch.object(Errata, "_errata_http_get")
    def test_builds_signed_some_unsigned(self, errata_http_get, errata_rest_get):
        mocked_errata = MockedErrataAPI(errata_rest_get, errata_http_get)
        mocked_errata.builds["libntirpc-1.4.3-4.el7rhgs"]["rpms_signed"] = False
        self.assertFalse(self.errata.builds_signed(28484))

    @patch.object(Errata, "_errata_rest_get")
    @patch.object(Errata, "_errata_http_get")
    def test_builds_signed_missing_data(self, errata_http_get, errata_rest_get):
        mocked_errata = MockedErrataAPI(errata_rest_get, errata_http_get)
        mocked_errata.builds["libntirpc-1.4.3-4.el7rhgs"] = {}
        self.assertFalse(self.errata.builds_signed(28484))

    @patch('freshmaker.errata.requests.get')
    def test_get_errata_repo_ids(self, get):
        get.return_value.json.return_value = {
            'rhel-6-server-eus-source-rpms__6_DOT_7__x86_64': [
            ],
            'rhel-6-server-eus-optional-debug-rpms__6_DOT_7__i386': [
                '/path/to/package.rpm',
                '/path/to/package1.rpm',
                '/path/to/package2.rpm',
            ],
            'rhel-6-server-eus-rpms__6_DOT_7__x86_64': [
            ],
        }

        repo_ids = self.errata.get_pulp_repository_ids(25718)

        self.assertEqual(set(['rhel-6-server-eus-source-rpms__6_DOT_7__x86_64',
                              'rhel-6-server-eus-optional-debug-rpms__6_DOT_7__i386',
                              'rhel-6-server-eus-rpms__6_DOT_7__x86_64']),
                         set(repo_ids))