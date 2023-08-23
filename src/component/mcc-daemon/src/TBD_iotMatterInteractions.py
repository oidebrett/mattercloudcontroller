#
# Copyright (c) 2023 Matter Cloud Controller Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from matter_yamltests.definitions import SpecDefinitions
from matter_yamltests.parser import TestParserConfig
from matter_yamltests.parser import TestParser
import matter_yamltests.parser 
from typing import Union

from matter_yamltests.yaml_loader import YamlLoader
from matter_yamltests.errors import (TestStepError, TestStepGroupResponseError, TestStepInvalidTypeError, TestStepKeyError,
                     TestStepNodeIdAndGroupIdError, TestStepValueAndValuesError, TestStepVerificationStandaloneError,
                     TestStepWaitResponseError)
from chip.yaml.runner import ReplTestRunner

class ReplRunner(ReplTestRunner):
    '''Action runner to encode/decode values from YAML Parser for executing the Interaction.

    Uses ChipDeviceCtrl from chip-repl to execute parsed YAML TestSteps.
    '''

    def __init__(self, test_spec_definition, certificate_authority_manager, alpha_dev_ctrl):
        ReplTestRunner.__init__(self, test_spec_definition, certificate_authority_manager, alpha_dev_ctrl)

class YamlActionsLoader(YamlLoader):
    """This class loads a file from the disk and validates that the content is a well formed yaml test."""
    
    def load(self, yaml_data: str) -> tuple[str, Union[list, str], dict, list]:
        name = ''
        pics = None
        config = {}
        tests = []

        if yaml_data:
            content = yaml_data

            self.__check_content(content)

            name = content.get('name', '')
            pics = content.get('PICS')
            config = content.get('config', {})
            tests = content.get('actions', [])

        return (name, pics, config, tests)

    def __check_content(self, content):
        schema = {
            'name': str,
            'PICS': (str, list),
            'config': dict,
            'actions': list,
        }

        try:
            self._YamlLoader__check(content, schema)
        except TestStepError as e:
            if 'actions' in content:
                # This is a top level error. The content of the tests section
                # does not really matter here and dumping it may be counter-productive
                # since it can be very long...
                content['actions'] = 'Skipped...'
            e.update_context(content, 0)
            raise

        actions = content.get('actions', [])
        for step_index, step in enumerate(actions):
            try:
                self._YamlLoader__check_test_step(step)
            except TestStepError as e:
                e.update_context(step, step_index)
                raise


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
