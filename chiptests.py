#
#    Copyright (c) 2021 Project CHIP Authors
#    All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#

from dataclasses import dataclass
from inspect import Attribute
from typing import Any
import typing
from chip import ChipDeviceCtrl
from chip import ChipCommissionableNodeCtrl
import chip.interaction_model as IM
import threading
import os
import sys
import logging
import time
import ctypes
#import chip.clusters as Clusters
#import chip.clusters.Attribute as Attribute
from chip.ChipStack import *
#import chip.FabricAdmin

logging.basicConfig(filename="logs/pythonMatterCloudControllerTEST.log")
logger = logging.getLogger('PythonMatterCloudControllerTEST')
logger.setLevel(logging.INFO)

nodeid = 1
chipStack = ChipStack('/tmp/repl_storage.json')
'''
fabricAdmin = chip.FabricAdmin.FabricAdmin(
    fabricId=1, fabricIndex=1)
devCtrl = fabricAdmin.NewController(nodeid, False)
'''
controllerNodeId = nodeid

logger.info(f"Closing sessions with device {nodeid}")
try:
    devCtrl.CloseSession(nodeid)
except Exception as ex:
    logger.exception(f"Failed to close sessions with device {nodeid}: {ex}")


logger.info( "Shutting down controllers & fabrics and re-initing stack...")
ChipDeviceCtrl.ChipDeviceController.ShutdownAll()
chip.FabricAdmin.FabricAdmin.ShutdownAll()

