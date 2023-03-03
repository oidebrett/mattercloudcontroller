import sys
import os
from typing import Union

import yaml

from matter_yamltests.yaml_loader import YamlLoader
from matter_yamltests.errors import (TestStepError, TestStepGroupResponseError, TestStepInvalidTypeError, TestStepKeyError,
                     TestStepNodeIdAndGroupIdError, TestStepValueAndValuesError, TestStepVerificationStandaloneError,
                     TestStepWaitResponseError)


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

