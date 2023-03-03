import asyncio as asyncio
import logging
import queue
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, IntEnum

import chip.interaction_model

#We will try to import the connectedhomeip repo python library
#so we can stay up to date with any changes
import os
import sys

from chip.yaml.runner import ReplTestRunner

class ReplRunner(ReplTestRunner):
    '''Action runner to encode/decode values from YAML Parser for executing the Interaction.

    Uses ChipDeviceCtrl from chip-repl to execute parsed YAML TestSteps.
    '''

    def __init__(self, test_spec_definition, certificate_authority_manager, alpha_dev_ctrl):
        ReplTestRunner.__init__(self, test_spec_definition, certificate_authority_manager, alpha_dev_ctrl)
