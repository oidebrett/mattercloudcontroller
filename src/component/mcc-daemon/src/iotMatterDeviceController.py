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
from binascii import hexlify, unhexlify
import queue
from dataModelLookup import PreDefinedDataModelLookup

#import chip.CertificateAuthority
import chip.clusters as Clusters
#import chip.FabricAdmin
import chip.logging
import chip.native
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


# TODO: Add utility to commission a device if needed
# TODO: Add utilities to keep track of controllers/fabrics

logger = logging.getLogger("matter.cloud_controller")
logger.setLevel(logging.INFO)

output_queue = queue.Queue()

class MatterDeviceController(object):
    args = None
    commissionableDevices = set()
    fabricDevices = set()
    MAX_DEVICES = 10

    def __init__(self,args):    
        self.args = args

    def lPrint(self,msg):
        logger.info(msg)
        print(msg, file=sys.stdout)
        sys.stderr.flush()

    def getFabricId(self):
        return devCtrl.GetCompressedFabricId()

    def discoverFabricDevices(self, stopAtFirstFail = False):
        # Discovery happens through mdns, which means we need to wait for responses to come back.
        '''
        self.lPrint("Querying cache for devices on this fabric...")
        compressFabricId = devCtrl.GetCompressedFabricId()
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

        return list(self.fabricDevices)
        '''

        for nodeId in range(1, self.MAX_DEVICES+1):
            self.lPrint(nodeId)
            try:
                devCtrl.ResolveNode(nodeId)
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
        self.commissionableDevices = devCtrl.DiscoverCommissionableNodes(filterType=chip.discovery.FilterType.LONG_DISCRIMINATOR, filter=3840, stopOnFirst=False, timeoutSecond=2)
        #print(devices)
        return list(self.commissionableDevices)

    def commissionDevice(self, ipAddress, nodeId=None):
        try:
            #if we dont have a nodeId then set one
            if nodeId is None:
                self.lPrint("nodeId is None")
                if len(self.fabricDevices) == 0:
                    nodeId = 1
                else:
                    nodeId = max(self.fabricDevices) + 1
            time.sleep(5)
            self.lPrint("Commissioning - nodeId " )
            builtins.devCtrl.CommissionIP(ipAddress, 20202021, nodeId)

            #Commented Out support for byte type of IpAddress
            #ipAddressAsBytes = str.encode(ipAddress)0
            #builtins.devCtrl.CommissionIP(ipAddressAsBytes, 20202021, nodeId)

            #Set the nodel label to node id so that when we restart the controller we can
            #build a list of the controllers in the correct order
            time.sleep(10)
            self.writeNodeLabel(nodeId)

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
        result = await devCtrl.ReadAttribute(node_id, [(endpoint, attribute)])
        data = result[endpoint]
        return list(data.values())[0][attribute]

    def writeNodeLabel(self, node_id: int):
        # when its commissioned, set the NodeLabel to "node_id"
        self.lPrint(f"Set BasicInformation.NodeLabel to {node_id}")
        asyncio.run(devCtrl.WriteAttribute(node_id, [(0, Clusters.BasicInformation.Attributes.NodeLabel(value=node_id))]))
        time.sleep(2)

    def writeAttribute(self, node_id: int, endpoint: int, clusterName: str, attributeName: str, value: str):
        # when its commissioned, set the NodeLabel to "node_id"
        self.lPrint(f"WriteAttribute to {attributeName}")
        pddml = PreDefinedDataModelLookup()
        attributeClass = pddml.get_attribute(clusterName,attributeName)
        asyncio.run(devCtrl.WriteAttribute(node_id, [(endpoint, attributeClass(value=value))]))
        time.sleep(2)

    def devOn(self, nodeId):
        self.lPrint('on')
        asyncio.run(devCtrl.SendCommand(nodeId, 1, Clusters.OnOff.Commands.On()))
        time.sleep(2)

    def devOff(self, nodeId):
        self.lPrint('off')
        asyncio.run(devCtrl.SendCommand(nodeId, 1, Clusters.OnOff.Commands.Off()))
        time.sleep(2)

    def readEndpointZeroAsJsonStr(self, nodeId):
        self.lPrint('Start Reading Endpoint0 Attributes')
        #if we are limited to json document size we could just ask for these
        #data = (asyncio.run(devCtrl.ReadAttribute(nodeId, [(0, Clusters.Basic),(0,Clusters.PowerSource),(0,Clusters.Identify)])))
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
        data = (asyncio.run(devCtrl.ReadAttribute(nodeId, large_read_paths)))
        '''
        data = (asyncio.run(devCtrl.ReadAttribute(nodeId, [0])))
        '''
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

        sub = asyncio.run(devCtrl.ReadAttribute(nodeId, attributes=[(0, Clusters.BasicInformation.Attributes.NodeLabel)],reportInterval=(min_report_interval_sec, max_report_interval_sec), keepSubscriptions=False))
        attribute_handler = AttributeChangeAccumulator(name=nodeId, callback=callback, expected_attribute=Clusters.BasicInformation.Attributes.NodeLabel, output=output_queue)
        sub.SetAttributeUpdateCallback(attribute_handler)

        return sub

    def cleanStart(self):
        if os.path.isfile('/tmp/repl-storage.json'):
            os.remove('/tmp/repl-storage.json')
        # So that the all-clusters-app won't boot with stale prior state.
        os.system('rm -rf /tmp/chip_*')
        time.sleep(2)

    def bytes_from_hex(self, hex: str) -> bytes:
        """Converts any `hex` string representation including `01:ab:cd` to bytes
        Handles any whitespace including newlines, which are all stripped.
        """
        return unhexlify("".join(hex.replace(":", "").replace(" ", "").split()))


    def hex_from_bytes(self, b: bytes) -> str:
        """Converts a bytes object `b` into a hex string (reverse of bytes_from_hex)"""
        return hexlify(b).decode("utf-8")


    def MatterInit(self, args, debug=True):
        global devCtrl
        global caList
        global chipStack
        global certificateAuthorityManager

        chip.native.Init()

        chipStack = ChipStack(persistentStoragePath=args.storagepath, enableServerInteractions=False)
        certificateAuthorityManager = chip.CertificateAuthority.CertificateAuthorityManager(chipStack, chipStack.GetStorageManager())

        certificateAuthorityManager.LoadAuthoritiesFromStorage()

        if (len(certificateAuthorityManager.activeCaList) == 0):
            ca = certificateAuthorityManager.NewCertificateAuthority()
            ca.NewFabricAdmin(vendorId=0xFFF1, fabricId=1)
        elif (len(certificateAuthorityManager.activeCaList[0].adminList) == 0):
            certificateAuthorityManager.activeCaList[0].NewFabricAdmin(vendorId=0xFFF1, fabricId=1)

        caList = certificateAuthorityManager.activeCaList

        devCtrl = caList[0].adminList[0].NewController()
        builtins.devCtrl = devCtrl

        atexit.register(self.StackShutdown)        

    def StackShutdown(self):
        certificateAuthorityManager.Shutdown()
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


