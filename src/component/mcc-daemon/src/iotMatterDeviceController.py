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

#import chip.CertificateAuthority
import chip.clusters as Clusters
#import chip.FabricAdmin
import chip.logging
import chip.native
#import click
from chip import ChipDeviceCtrl
from chip.ChipStack import *
from chip.storage import PersistentStorage
from chip.utils import CommissioningBuildingBlocks
from chip import discovery, exceptions
from chip.clusters.Attribute import SubscriptionTransaction, TypedAttributePath

from mobly import base_test, logger, signals, utils
from mobly.config_parser import ENV_MOBLY_LOGPATH, TestRunConfig
from mobly.test_runner import TestRunner
import jsonDumps
#import tempfile
import yaml


#Set the paths up so we are using the parsing in the connectedhomeip repo
import config 
sys.path.append(os.path.abspath(config.chipDir+"/scripts/py_matter_yamltests/"))
sys.path.append(os.path.abspath(config.chipDir+"/scripts/py_matter_idl/"))

from runner import ReplRunner

from matter_yamltests.definitions import SpecDefinitionsFromPaths
from matter_yamltests.parser import TestParser, TestParserConfig
from actionParser import ActionParser


# TODO: Add utility to commission a device if needed
# TODO: Add utilities to keep track of controllers/fabrics

logger = logging.getLogger("matter.cloud_controller")
logger.setLevel(logging.INFO)

output_queue = queue.Queue()

class MatterDeviceController(object):
    args = None
    commissionableDevices = set()
    fabricDevices = set()
    MAX_DEVICES = config.MAX_DEVICES
    devCtrl = None
    caList = None
    chipStack = None
    certificateAuthorityManager = None
    runner = None
    clustersDefinitions = None

    def __init__(self,args):    
        self.args = args

    def lPrint(self,msg):
        logger.info(msg)
        print(msg, file=sys.stdout)
        sys.stderr.flush()

    def getFabricId(self):
        return self.devCtrl.GetCompressedFabricId()

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
            time.sleep(5)
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
            time.sleep(5)
            return nodeId
        except Exception as e:
            self.lPrint("Commission failed: ", e.message)
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

    def run2(self, node_id: int, data):
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
            response = self.runner.execute(test_action)
            decoded_response = self.runner.decode(response)
        return decoded_response

    def run(self, node_id: int, yaml_path: str, deleteAfterRead = True):
        # Parsing YAML test and setting up chip-repl yamltests runner.
        #We need a PICS file just to create the parser but we wont use it
        pics_file = os.path.abspath(os.path.dirname(__file__))+'/PICS_blank.yaml'
        yaml = TestParser(yaml_path, pics_file, self.clustersDefinitions)
        if deleteAfterRead:
            os.remove(yaml_path)

        for test_step in yaml.tests:
            test_action = self.runner.encode(test_step)
            self.lPrint(test_action)
            if test_action is None:
                self.lPrint(f'Failed to encode test step {test_step.label}')
                raise Exception(f'Failed to encode test step {test_step.label}')
            response = self.runner.execute(test_action)
            decoded_response = self.runner.decode(response)
        return decoded_response

    #This is just a test function to try to get the parsing work
    #Eventually we will remove this but we need it while the connectedhomeip repo
    #is changing how it handles test scriptinh
    def testExecute(self, node_id: int, actionsStr: str):
        yaml_path = '/home/ivob/Projects/mattercloudcontroller/src/component/mcc-daemon/src/TestBasicInformation.yaml'
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
        exit()

        #yamlParser = ActionParser(actions, pics_file, self.clustersDefinitions)
        self.lPrint(yamlParser)


    def execute(self, node_id: int, actionsStr: str):
        yamlActions = yaml.dump(actionsStr, allow_unicode=True)
        actions = yaml.safe_load(yamlActions)

        '''
        # more complex as you must watch out for exceptions
        fd, path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, 'w') as tmp:
                # write yaml actions to the temp file
                tmp.write(yamlActions)
        except:
            self.lPrint("Error creating a named temporary file..")

        tmp.close()
        #Call the runner
        decoded_response = self.run(node_id=node_id, yaml_path=path, deleteAfterRead = True)
        '''
        #Call the runner
        decoded_response = self.run2(node_id, actions)
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
        #if we are less limited to json document size we could just ask for these
        #data = (asyncio.run(self.devCtrl.ReadAttribute(nodeId, [(0, Clusters.BasicInformation),(0,Clusters.PowerSource),(0,Clusters.Identify)])))
        data = (asyncio.run(self.devCtrl.ReadAttribute(nodeId, [
            (0, Clusters.BasicInformation),
            (0, Clusters.Identify),
            (0, Clusters.GeneralDiagnostics),
            (0, Clusters.Groups),
            (0, Clusters.Descriptor),
            (0, Clusters.Binding),
            (0, Clusters.AccessControl),
            (0, Clusters.OtaSoftwareUpdateRequestor),
#            (0, Clusters.LocalizationConfiguration),
#            (0, Clusters.TimeFormatLocalization),
#            (0, Clusters.UnitLocalization),
            (0, Clusters.PowerSourceConfiguration),
            (0, Clusters.PowerSource),
            (0, Clusters.GeneralCommissioning),
            (0, Clusters.NetworkCommissioning),
            (0, Clusters.DiagnosticLogs),
            (0, Clusters.SoftwareDiagnostics),
            (0, Clusters.ThreadNetworkDiagnostics),
            (0, Clusters.WiFiNetworkDiagnostics),
            (0, Clusters.EthernetNetworkDiagnostics),
            (0, Clusters.AdministratorCommissioning),
            (0, Clusters.OperationalCredentials),
            (0, Clusters.GroupKeyManagement),
            (0, Clusters.FixedLabel),
            (0, Clusters.UserLabel),
            (0, Clusters.RelativeHumidityMeasurement),
            (0, Clusters.ClientMonitoring),
            (0, Clusters.FaultInjection)
            ])))
        '''
        #if we all of endpoint 0 we could just ask for these
        data = (asyncio.run(self.devCtrl.ReadAttribute(nodeId, [0])))
        #if we are limited to json document size we could just ask for these specific attributes
        large_read_contents = [
            Clusters.BasicInformation.Attributes.DataModelRevision,
            Clusters.BasicInformation.Attributes.VendorName,
            Clusters.BasicInformation.Attributes.VendorID,
            Clusters.BasicInformation.Attributes.ProductName,
            Clusters.BasicInformation.Attributes.ProductID,
            Clusters.BasicInformation.Attributes.NodeLabel,
            Clusters.BasicInformation.Attributes.Location,
            Clusters.BasicInformation.Attributes.HardwareVersion,
            Clusters.BasicInformation.Attributes.HardwareVersionString,
        ]
        large_read_paths = [(0, attrib) for attrib in large_read_contents]
        data = (asyncio.run(self.devCtrl.ReadAttribute(nodeId, large_read_paths)))
        #if we all of everything in the node we could just ask for these
        data = (asyncio.run(self.devCtrl.ReadAttribute(nodeId, ['*'])))
        '''
        self.lPrint('End Reading Endpoint0 Attributes')

        jsonStr = jsonDumps.jsonDumps(data)
        #self.lPrint(jsonStr)
        return jsonStr

    def subscribeForAttributeChange(self, nodeId, callback):
        # Immediate reporting
        min_report_interval_sec = 0
        # 10 minutes max reporting interval --> We don't care about keep-alives per-se and
        # want to avoid resubscriptions
        max_report_interval_sec = 10 * 60
 
        self.lPrint("Establishing subscription from controller node %s" % (nodeId))

        #sub = asyncio.run(self.devCtrl.ReadAttribute(nodeId, attributes=[(0, Clusters.BasicInformation.Attributes.NodeLabel)],reportInterval=(min_report_interval_sec, max_report_interval_sec), keepSubscriptions=False))
        #attribute_handler = AttributeChangeAccumulator(name=nodeId, callback=callback, expected_attribute=Clusters.BasicInformation.Attributes.NodeLabel, output=output_queue)
        sub = asyncio.run(self.devCtrl.ReadAttribute(nodeId, attributes=[0],reportInterval=(min_report_interval_sec, max_report_interval_sec), keepSubscriptions=False))
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
        sub = asyncio.run(self.devCtrl.ReadEvent(nodeId, [()],reportInterval=(min_report_interval_sec, max_report_interval_sec)))
        event_handler = EventCatcher(name=nodeId, callback=callback)
        sub.SetEventUpdateCallback(event_handler)

        return sub

    def cleanStart(self):
        if os.path.isfile('/tmp/repl-storage.json'):
            os.remove('/tmp/repl-storage.json')
        # So that the all-clusters-app won't boot with stale prior state.
        os.system('rm -rf /tmp/chip_*')
        time.sleep(2)

    def jsonDumps(self, data):
        return jsonDumps.jsonDumps(data)

    def MatterInit(self, args, debug=True):

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
