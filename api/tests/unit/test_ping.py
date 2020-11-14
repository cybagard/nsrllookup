# coding: UTF-8

"""Unit tests"""

import unittest

from app import api


class BasicTests(unittest.TestCase):
    """Basic Test Class"""

    def setUp(self):
        self.api = api.test_client()
        self.api.testing = True

    def tearDown(self):
        pass

    def test_ping(self):
        response = self.api.get('/ping')
        self.assertEqual(response.status_code, 200)
