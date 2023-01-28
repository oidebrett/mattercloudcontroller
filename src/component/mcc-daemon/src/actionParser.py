import copy
from enum import Enum, auto

import yaml
import sys 
import os

#Set the paths up so we are using the parsing in the connectedhomeip repo
import config 
sys.path.append(os.path.abspath(config.chipDir+"/scripts/py_matter_yamltests/"))
import matter_yamltests.parser 

class ActionParser:
    def __init__(self, data, pics_file, definitions):

        matter_yamltests.parser._check_valid_keys(data, matter_yamltests.parser._TESTS_SECTION)

        self.name = matter_yamltests.parser._value_or_none(data, 'name')
        self.PICS = matter_yamltests.parser._value_or_none(data, 'PICS')

        self._parsing_config_variable_storage = matter_yamltests.parser._value_or_none(data, 'config')

        pics_checker = matter_yamltests.parser.PICSChecker(pics_file)
        tests = matter_yamltests.parser._value_or_none(data, 'tests')
        self.tests = matter_yamltests.parser.YamlTests(
            self._parsing_config_variable_storage, definitions, pics_checker, tests)

    def update_config(self, key, value):
        self._parsing_config_variable_storage[key] = value

