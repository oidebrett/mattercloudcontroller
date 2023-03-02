import copy
from enum import Enum, auto

import yaml
import sys 
import os

#Set the paths up so we are using the parsing in the connectedhomeip repo
#import config 
#sys.path.append(os.path.abspath(config.chipDir+"/scripts/py_matter_yamltests/"))

from matter_yamltests.definitions import SpecDefinitions
from matter_yamltests.parser import TestParserConfig
import matter_yamltests.parser 

class ActionParser:
    def __init__(self, data: str, parser_config: TestParserConfig = TestParserConfig()):

        matter_yamltests.parser._TESTS_SECTION.append('actions') #Lets add the option for actions

        matter_yamltests.parser._check_valid_keys(data, matter_yamltests.parser._TESTS_SECTION)

        self.name = matter_yamltests.parser._value_or_none(data, 'name')
        self.PICS = matter_yamltests.parser._value_or_none(data, 'PICS')

        config = data.get('config', {})
        for key, value in parser_config.config_override.items():
            if value is None:
                continue

            if isinstance(config[key], dict) and 'defaultValue' in config[key]:
                config[key]['defaultValue'] = value
            else:
                config[key] = value
        self._parsing_config_variable_storage = config

        # These are a list of "KnownVariables". These are defaults the codegen used to use. This
        # is added for legacy support of tests that expect to uses these "defaults".
        self.__populate_default_config_if_missing('nodeId', 0x12345)
        self.__populate_default_config_if_missing('endpoint', '')
        self.__populate_default_config_if_missing('cluster', '')
        self.__populate_default_config_if_missing('timeout', '90')

        pics_checker = matter_yamltests.parser.PICSChecker(parser_config.pics)
        tests = matter_yamltests.parser._value_or_none(data, 'actions')
        print(tests)
        self.tests = matter_yamltests.parser.YamlTests(
            self._parsing_config_variable_storage, parser_config.definitions, pics_checker, tests)

    def __populate_default_config_if_missing(self, key, value):
        if key not in self._parsing_config_variable_storage:
            self._parsing_config_variable_storage[key] = value
