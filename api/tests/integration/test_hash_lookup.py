# coding: UTF-8

"""Integration tests"""

import unittest
import json

from app import api

class BasicTests(unittest.TestCase):
    """Basic Test Class"""

    def setUp(self):
        self.api = api.test_client()
        self.api.testing = True

    def tearDown(self):
        pass

    def test_hash_lookup_status_code(self):
        response = self.api.get('/check/ad7b9c14083b52bc532fba5948342b98')
        self.assertEqual(response.status_code, 200)

    def test_hash_lookup_respone_data_lower(self):
        response = self.api.get('/check/ad7b9c14083b52bc532fba5948342b98')
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(data['result'], 'true')

    def test_hash_lookup_respone_data_upper(self):
        response = self.api.get('/check/AD7B9C14083B52BC532FBA5948342B98')
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(data['result'], 'true')

    def test_hash_lookup_respone_data_negative(self):
        response = self.api.get('/check/2977520a5c5faad2286d58675e400412')
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(data['result'], 'false')

    def test_hash_lookup_respone_data_invalid_format(self):
        response = self.api.get('/check/2977520a5c5faad2286d58675e4004122977520a5c5faad2286d58675e400412')
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(data['result'], 'invalid hash format')

    def test_hash_lookup_respone_data_invalid_format_1(self):
        response = self.api.get('/check/2977520')
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(data['result'], 'invalid hash format')
