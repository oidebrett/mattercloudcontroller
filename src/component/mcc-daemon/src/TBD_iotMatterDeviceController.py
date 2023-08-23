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
import argparse
import asyncio
import builtins
import json
import logging
import os
import pathlib
import re
import sys
import uuid
from binascii import hexlify, unhexlify
from dataclasses import asdict as dataclass_asdict
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import atexit
import subprocess
import time
import bisect 
import queue
import uuid

import chip.clusters as Clusters
import chip.logging
import chip.native
from chip import ChipDeviceCtrl
from chip.ChipStack import *
from chip.storage import PersistentStorage
from chip.utils import CommissioningBuildingBlocks
from chip import discovery, exceptions
from chip.clusters.Attribute import SubscriptionTransaction, TypedAttributePath
from chip.ChipBluezMgr import BluezManager as BleManager

from mobly import base_test, logger, signals, utils
from mobly.config_parser import ENV_MOBLY_LOGPATH, TestRunConfig
from mobly.test_runner import TestRunner
import jsonDumps
from attributesConfig import AttributesInScope
import yaml


# TODO: Add utility to commission a device if needed
# TODO: Add utilities to keep track of controllers/fabrics

logger = logging.getLogger("matter.cloud_controller")
logger.setLevel(logging.INFO)

output_queue = queue.Queue()

class MatterDeviceController(object):
    args = None
    commissionableDevices = set()
    fabricDevices = set()
    MAX_DEVICES = None
    MAX_EVENTS = None
    devCtrl = None
    caList = None
    chipStack = None
    certificateAuthorityManager = None
    runner = None
    clustersDefinitions = None
    chipDir = None
    storagePath = None

    def __init__(self,args):    
        self.args = args

    def lPrint(self,msg):
        logger.info(msg)
        print(msg, file=sys.stdout)
        sys.stderr.flush()

    def getFabricId(self):
        return self.devCtrl.GetCompressedFabricId()

    def discoverBleDevices(self, timeoutInSecs):
        found = False

        chip_service = uuid.UUID("0000FFF6-0000-1000-8000-00805F9B34FB")
        chip_service_short = uuid.UUID("0000FFF6-0000-0000-0000-000000000000")
        chromecast_setup_service = uuid.UUID("0000FEA0-0000-1000-8000-00805F9B34FB")
        chromecast_setup_service_short = uuid.UUID("0000FEA0-0000-0000-0000-000000000000")

        bleMgr = BleManager(self.devCtrl)
        bleMgr.ble_adapter_select()
        bleMgr.adapter.adapter_bg_scan(True)
        bleChipDevices = []

        timeout = timeoutInSecs + time.time()

        while time.time() < timeout:
            scanned_peripheral_list = bleMgr.adapter.find_devices(
                [
                        chip_service,
                        chip_service_short,
                        chromecast_setup_service,
                        chromecast_setup_service_short,
                ]
                )
            for device in scanned_peripheral_list:
                try:
                    devIdInfo = bleMgr.get_peripheral_devIdInfo(device)
                    if not devIdInfo:
                        # Not a chip device
                        print("Not a chip device")
                        continue
                    else:

                        bleChipDevice = {
                            "name": device.Name,
                            #"id": str(device.device_id),
                            "rssi": device.RSSI,
                            "address": device.Address,
                            "pairingState": devIdInfo.pairingState,
                            "discriminator": devIdInfo.discriminator,
                            "vendorId": devIdInfo.vendorId,
                            "productId": devIdInfo.productId
                        }
                        if (bleChipDevice not in bleChipDevices):
                            bleChipDevices.append(bleChipDevice)
                            found = True
                            break
                        else:
                            #We have already recorded this one
                            pass

                except Exception:
                    self.lPrint("error in discoverBleDevices")
        #    if found:
        #        break

        bleMgr.adapter.adapter_bg_scan(False)

        return bleChipDevices

    def discoverFabricDevices(self, useAvahi = False, stopAtFirstFail = False):
        # Discovery happens through mdns, which means we need to wait for responses to come back.
        if useAvahi: #This is much quicker than the resolbveNode method
            self.lPrint("Querying cache for devices on this fabric...")
            compressFabricId = self.devCtrl.GetCompressedFabricId()
            compressFabricIdHex = "%0.2X" % compressFabricId
            self.lPrint(compressFabricIdHex)
            cmd = subprocess.Popen('avahi-browse -rt _matter._tcp', shell=True, stdout=subprocess.PIPE)
            for line in cmd.stdout:
                lineStr = line.decode("utf-8")
                if "_matter._tcp" in lineStr:
                    print(lineStr)
                    if re.search(compressFabricIdHex+'-[\d]+', lineStr) is not None:
                        for catch in re.finditer(compressFabricIdHex+'-[\d]+', lineStr):
                            self.fabricDevices.add(int(catch[0][len(compressFabricIdHex)+1:])) # catch is a match object

        else: 
            for nodeId in range(1, self.MAX_DEVICES+1):
                self.lPrint(nodeId)
                try:
                    self.devCtrl.ResolveNode(nodeId)
                    self.lPrint("Found a node: " + str(nodeId))
                    self.fabricDevices.add(int(nodeId)) 
                except exceptions.ChipStackError as ex:
                    self.lPrint("DiscoverCommissionableNodes stopped {}".format(str(ex)))
                    if stopAtFirstFail:
                        break

        return list(self.fabricDevices)

    def discoverCommissionableDevices(self):
        # Discovery happens through mdns, which means we need to wait for responses to come back.
        self.lPrint("Querying for commissionable devices ...")
        self.commissionableDevices = self.devCtrl.DiscoverCommissionableNodes(filterType=chip.discovery.FilterType.LONG_DISCRIMINATOR, filter=3840, stopOnFirst=False, timeoutSecond=2)
        #print(devices)
        return list(self.commissionableDevices)

    def commissionDevice(self, ipAddress, nodeId=None, allocatedNodeIds = None):
        if allocatedNodeIds is not None:
            tmpList = list(self.fabricDevices)
            self.lPrint("allocatedNodeIds is not None")
            self.lPrint(allocatedNodeIds)
            #we will add these to the fabricDevices list
            for allocatedNodeId in allocatedNodeIds:
                bisect.insort(tmpList, allocatedNodeId)
            self.fabricDevices = set(tmpList)

        #if we dont have a nodeId then set one
        if nodeId is None:
            self.lPrint("nodeId is None")
            if len(self.fabricDevices) == 0:
                nodeId = 1
            else:
                nodeId = max(self.fabricDevices) + 1

        try:
            #time.sleep(5)
            self.lPrint("Commissioning - nodeId " )
            builtins.devCtrl.CommissionIP(ipAddress, 20202021, nodeId)

            #Commented Out support for byte type of IpAddress
            #ipAddressAsBytes = str.encode(ipAddress)0
            #builtins.devCtrl.CommissionIP(ipAddressAsBytes, 20202021, nodeId)

            #Set the nodel label to node id so that when we restart the controller we can
            #build a list of the controllers in the correct order
            #time.sleep(10)
            #self.writeNodeLabel(nodeId)

            #Then add this one to the fabricDevices
            self.fabricDevices.add(nodeId)
            time.sleep(2)
            return nodeId
        except Exception as e:
            self.lPrint("Commission failed: ")
            self.lPrint(e)
            return -1

    def getCommissionedDevices(self):
        return list(self.fabricDevices)

    async def readSingleAttribute(self, node_id: int, endpoint: int, attribute: object) -> object:
        self.lPrint('readSingleSttribute')
        result = await self.devCtrl.ReadAttribute(node_id, [(endpoint, attribute)])
        data = result[endpoint]
        return list(data.values())[0][attribute]

    def writeNodeLabel(self, node_id: int):
        # when its commissioned, set the NodeLabel to "node_id"
        self.lPrint(f"Set BasicInformation.NodeLabel to {node_id}")
        asyncio.run(self.devCtrl.WriteAttribute(node_id, [(0, Clusters.BasicInformation.Attributes.NodeLabel(value=node_id))]))
        time.sleep(2)

    def writeAttribute(self, node_id: int, endpoint: int, clusterName: str, attributeName: str, value: str):
        # when its commissioned, set the NodeLabel to "node_id"
        self.lPrint(f"WriteAttribute to {attributeName}")
        #time.sleep(2)

    async def runActions(self, node_id: int, data):
        # Parsing YAML test and setting up chip-repl yamltests runner.
        #We need a PICS file just to create the parser but we wont use it
        pics_file = os.path.abspath(os.path.dirname(__file__))+'/PICS_blank.yaml'
        parser_config = TestParserConfig(pics_file, self.clustersDefinitions)
        yamlParser = ActionParser(data, parser_config)
        self.lPrint(yamlParser)
        for test_step in yamlParser.tests:
            test_action = self.runner.encode(test_step)
            self.lPrint(test_action)
            if test_action is None:
                self.lPrint(f'Failed to encode test step {test_step.label}')
                raise Exception(f'Failed to encode test step {test_step.label}')
            response = await self.runner.execute(test_action)
            decoded_response = self.runner.decode(response)
        return decoded_response

    #This is just a test function to try to get the parsing work
    #Eventually we will remove this but we need it while the connectedhomeip repo
    #is changing how it handles test scripting
    def testExecute(self, node_id: int, actionsStr: str):
        yaml_path = os.path.abspath(os.path.dirname(__file__))+'/TestBasicInformation.yaml'
        pics_file = os.path.abspath(os.path.dirname(__file__))+'/PICS_blank.yaml'

        with open(yaml_path) as f:
            loader = yaml.FullLoader   
            actions = yaml.load(f, Loader=loader)

        self.lPrint(actions)
        self.lPrint(type(actions))

        yamlActions = yaml.dump(actions, allow_unicode=True)
        self.lPrint(yamlActions)

        self.lPrint("self.clustersDefinitions")
        self.lPrint(self.clustersDefinitions)
        parser_config = TestParserConfig(pics_file, self.clustersDefinitions)
        yamlParser = ActionParser(actions, parser_config)
        self.lPrint(yamlParser)
        return


    def execute(self, node_id: int, actionsStr: str):
        yamlActions = yaml.dump(actionsStr, allow_unicode=True)
        actions = yaml.safe_load(yamlActions)

        #Call the runner
        decoded_response = asyncio.run(self.runActions(node_id, actions))
        return decoded_response

    def devOn(self, nodeId):
        self.lPrint('on')
        asyncio.run(self.devCtrl.SendCommand(nodeId, 1, Clusters.OnOff.Commands.On()))
        time.sleep(2)

    def devOff(self, nodeId):
        self.lPrint('off')
        asyncio.run(self.devCtrl.SendCommand(nodeId, 1, Clusters.OnOff.Commands.Off()))
        time.sleep(2)

    def readEndpointZeroAsJsonStr(self, nodeId):
        self.lPrint('Start Reading Endpoint0 Attributes')
        #see attributesConfig.py to have more fine grain control over what attributes are requested

        data = (asyncio.run(self.devCtrl.ReadAttribute(nodeId, AttributesInScope)))

        self.lPrint('End Reading Endpoint0 Attributes')

        jsonStr = jsonDumps.jsonDumps(data)
        self.lPrint(jsonStr)
        return jsonStr

    def subscribeForAttributeChange(self, nodeId, callback):
        # Immediate reporting
        min_report_interval_sec = 0
        # 10 minutes max reporting interval --> We don't care about keep-alives per-se and
        # want to avoid resubscriptions
        max_report_interval_sec = 10 * 60
 
        self.lPrint("Establishing subscription from controller node %s" % (nodeId))

        sub = asyncio.run(self.devCtrl.ReadAttribute(nodeId, attributes=AttributesInScope,reportInterval=(min_report_interval_sec, max_report_interval_sec), keepSubscriptions=True))
        attribute_handler = AttributeChangeAccumulator(name=nodeId, callback=callback, expected_attribute=Clusters.BasicInformation.Attributes.NodeLabel, output=output_queue)
        sub.SetAttributeUpdateCallback(attribute_handler)

        return sub

    def subscribeForEventChange(self, nodeId, callback):
        # Immediate reporting
        min_report_interval_sec = 0
        # 10 minutes max reporting interval --> We don't care about keep-alives per-se and
        # want to avoid resubscriptions
        max_report_interval_sec = 60*10
 
        self.lPrint("Establishing event change subscription from controller node %s" % (nodeId))

        asyncio.set_event_loop(asyncio.new_event_loop())
        sub = asyncio.run(self.devCtrl.ReadEvent(nodeId, [()],reportInterval=(min_report_interval_sec, max_report_interval_sec), keepSubscriptions=True))
        event_handler = EventCatcher(name=nodeId, callback=callback)
        sub.SetEventUpdateCallback(event_handler)

        return sub

    def cleanStart(self):
        if os.path.isfile(self.storagePath):
            os.remove(self.storagePath)
        # So that the all-clusters-app won't boot with stale prior state.
        os.system('rm -rf /tmp/chip_*')
        time.sleep(2)

    def jsonDumps(self, data):
        return jsonDumps.jsonDumps(data)

    def MatterInit(self, args, debug=True):
        # Set Up Chip Rep Directory from Args
        self.chipDir = args.chipdir
        # Set Up Max Devices from Args
        self.MAX_DEVICES = args.maxdevices
        # Set Up Max Events from Args
        self.MAX_EVENTS = args.maxevents
        # Set Up the persistent storage path
        self.storagePath = args.storagepath

        global matter_idl_types, SpecDefinitionsFromPaths, TestParser, TestParserConfig, ReplRunner, ActionParser

        # ensure matter IDL is availale for import, otherwise set relative paths
        try:
            from matter_idl import matter_idl_types
            from matter_yamltests.definitions import SpecDefinitionsFromPaths
            from matter_yamltests.parser import TestParser, TestParserConfig
        except:
            #Set the paths up so we are using the parsing in the connectedhomeip repo
            SCRIPT_PATH = self.chipDir+"/scripts/"
            CONTROLLER_PATH = self.chipDir+"/src/controller/"
            import sys

            sys.path.append(os.path.join(SCRIPT_PATH, 'py_matter_idl'))
            sys.path.append(os.path.join(SCRIPT_PATH, 'py_matter_yamltests'))
            sys.path.append(os.path.join(CONTROLLER_PATH, 'python/chip/yaml'))

            from matter_idl import matter_idl_types
            from matter_yamltests.definitions import SpecDefinitionsFromPaths
            from matter_yamltests.parser import TestParser, TestParserConfig

        from iotMatterInteractions import ReplRunner, ActionParser
        #from runner import ReplRunner
        #from actionParser import ActionParser

        chip.native.Init()

        self.chipStack = ChipStack(persistentStoragePath=args.storagepath, enableServerInteractions=False)
        self.certificateAuthorityManager = chip.CertificateAuthority.CertificateAuthorityManager(self.chipStack, self.chipStack.GetStorageManager())

        self.certificateAuthorityManager.LoadAuthoritiesFromStorage()

        if (len(self.certificateAuthorityManager.activeCaList) == 0):
            ca = self.certificateAuthorityManager.NewCertificateAuthority()
            ca.NewFabricAdmin(vendorId=0xFFF1, fabricId=1)
        elif (len(self.certificateAuthorityManager.activeCaList[0].adminList) == 0):
            self.certificateAuthorityManager.activeCaList[0].NewFabricAdmin(vendorId=0xFFF1, fabricId=1)

        self.caList = self.certificateAuthorityManager.activeCaList

        self.devCtrl = self.caList[0].adminList[0].NewController()
        builtins.devCtrl = self.devCtrl

        atexit.register(self.StackShutdown)        

        _CLUSTER_XML_DIRECTORY_PATH = os.path.abspath(
            os.path.join(args.chipdir, "src/app/zap-templates/zcl/data-model/"))

        try:
            # Creating Cluster definition.
            self.clustersDefinitions = SpecDefinitionsFromPaths([
                _CLUSTER_XML_DIRECTORY_PATH + '/chip/*.xml'
            ])

            # Creating Runner for commands.
            self.runner = ReplRunner(self.clustersDefinitions, self.certificateAuthorityManager, self.devCtrl)

        except Exception:
            self.lPrint("Error Establishing cluster definitions")        

    def StackShutdown(self):
        self.certificateAuthorityManager.Shutdown()
        builtins.chipStack.Shutdown()

class AttributeChangeAccumulator:
    def __init__(self, name: str, callback, expected_attribute: Clusters.ClusterAttributeDescriptor, output: queue.Queue):
        self._name = name
        self._callback = callback
        self._output = output
        self._expected_attribute = expected_attribute

    def lPrint(self,msg):
        logger.info(msg)
        print(msg, file=sys.stdout)
        sys.stderr.flush()

    def __call__(self, path: TypedAttributePath, transaction: SubscriptionTransaction):
        #if path.AttributeType == self._expected_attribute:
        data = transaction.GetAttribute(path)

        value = {
            'name': self._name,
            'endpoint': path.Path.EndpointId,
            'attribute': path.AttributeType,
            'value': data
        }
        self.lPrint("Got subscription report on client %s for %s: %s" % (self.name, path.AttributeType, data))
        self._output.put(value)
        self._callback(self._name )

    @property
    def name(self) -> str:
        return self._name

class EventCatcher:
    def __init__(self, name, callback):
        self._name = name
        self._callback = callback

    def __call__(self, transaction: SubscriptionTransaction, terminationError):
        eventData = transaction
        print("Got resubscription on client %s" % self.name)
        self._callback(self._name, eventData)

    @property
    def name(self) -> str:
        return self._name