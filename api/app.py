# coding: UTF-8

"""Simple API to lookup any MD5 hash in the NSRL RDS hash set."""

import re

from flask import Flask, jsonify
from waitress import serve
from paste.translogger import TransLogger

from nsrllookup import NSRLLookup

api = Flask(__name__)


@api.route('/ping')
def ping():
    return jsonify({'result': 'pong'})


@api.route('/check/<hash_value>')
def check(hash_value):
    validate = re.finditer(r'(?=(\b[A-Fa-f0-9]{32}\b))', hash_value.upper())
    validated_input = [match.group(1) for match in validate]

    if validated_input:
        nsrl = NSRLLookup(server='svr')
        hash_value = validated_input.pop()
        nsrl.add_hash_only(hash_value)
        result = nsrl.run_query()

        if hash_value in result['known']:
            return jsonify({'result': 'true'})
        else:
            return jsonify({'result': 'false'})
    else:
        return jsonify({'result': 'invalid hash format'})


if __name__ == '__main__':
    serve(TransLogger(api, setup_console_handler=False),
          host='0.0.0.0',
          port=5000)
