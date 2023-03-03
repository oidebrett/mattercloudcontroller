import copy
from enum import Enum, auto

import yaml
import sys 
import os

from matter_yamltests.definitions import SpecDefinitions
from matter_yamltests.parser import TestParserConfig
from matter_yamltests.parser import TestParser
import matter_yamltests.parser 
from yamlActionsLoader import YamlActionsLoader

class ActionParser(TestParser):
    def __init__(self, data: str, parser_config: TestParserConfig = TestParserConfig()):

        yaml_loader = YamlActionsLoader()
        name, pics, config, tests = yaml_loader.load(data)

        self._TestParser__apply_config_override(config, parser_config.config_override)
        self._TestParser__apply_legacy_config(config)

        self.tests = matter_yamltests.parser.YamlTests(
            config,
            parser_config.definitions,
            matter_yamltests.parser.PICSChecker(parser_config.pics),
            tests
        )
