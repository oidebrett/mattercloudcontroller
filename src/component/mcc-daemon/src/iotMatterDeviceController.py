import argparse
import asyncio
import atexit
import builtins
import json
import logging
import os
import re
import subprocess
import sys
import time
from pprint import pformat
from base64 import b64encode, b64decode

#import chip.CertificateAuthority
import chip.clusters as Clusters
import chip.discovery
#import chip.FabricAdmin
import chip.logging
import chip.native
import coloredlogs
from chip import ChipDeviceCtrl
from chip.ChipStack import *
from chip.utils import CommissioningBuildingBlocks
from chip.clusters.Types import Nullable, NullValue
from rich import inspect, pretty, print
from rich.console import Console
from rich.pretty import pprint

class MatterDeviceController(object):
    args = None
    commissionableDevices = set()
    fabricDevices = set()
    MAX_DEVICES = 10

    def __init__(self,args):    
        self.args = args

    def lPrint(self,msg):
        console = Console()
        console.print(msg)
        logging.info(msg)
        print(msg, file=sys.stdout)
        sys.stderr.flush()

    def getFabricId(self):
        return devCtrl.GetCompressedFabricId()

    def discoverFabricDevices(self):
        # Discovery happens through mdns, which means we need to wait for responses to come back.
        self.lPrint("Querying cache for devices on this fabric...")
        compressFabricId = devCtrl.GetCompressedFabricId()
        compressFabricIdHex = "%0.2X" % compressFabricId
        #self.lPrint(compressFabricIdHex)
        cmd = subprocess.Popen('avahi-browse -rt _matter._tcp', shell=True, stdout=subprocess.PIPE)
        for line in cmd.stdout:
            lineStr = line.decode("utf-8")
            if "_matter._tcp" in lineStr:
                print(lineStr)
                if re.search(compressFabricIdHex+'-[\d]+', lineStr) is not None:
                    for catch in re.finditer(compressFabricIdHex+'-[\d]+', lineStr):
                        self.fabricDevices.add(int(catch[0][len(compressFabricIdHex)+1:])) # catch is a match object

        return list(self.fabricDevices)

    def discoverCommissionableDevices(self):
        # Discovery happens through mdns, which means we need to wait for responses to come back.
        self.lPrint("Querying for commissionable devices ...")
        self.commissionableDevices = devCtrl.DiscoverCommissionableNodes(filterType=chip.discovery.FilterType.LONG_DISCRIMINATOR, filter=3840, stopOnFirst=False, timeoutSecond=2)
        #print(devices)
        return list(self.commissionableDevices)

    def getCommissionedDevices(self):
        return list(self.fabricDevices)

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
            self.fabricDevices.add(nodeId)
            time.sleep(10)
            return nodeId
        except Exception as e:
            self.lPrint("Commission failed: ", e.message)
            return -1



    def readEndpointZeroAsJsonStr(self, nodeId):
        self.lPrint('Start Reading Endpoint0 Attributes')
        #data = (asyncio.run(devCtrl.ReadAttribute(nodeId, [0])))
        #We are limited to json document size so just asking for these
        data = (asyncio.run(devCtrl.ReadAttribute(nodeId, [(0, Clusters.Basic),(0,Clusters.PowerSource),(0,Clusters.Identify)])))
        self.lPrint('End Reading Endpoint0 Attributes')

        jsonStr = self.jsonDumps(data)
        self.lPrint(jsonStr)
        return jsonStr

    def readDevAttributesAsJsonStr(self, nodeId):
        self.lPrint('Start Reading Dev Attributes')
        data = (asyncio.run(devCtrl.ReadAttribute(nodeId, [Clusters.OnOff])))
        #data = (asyncio.run(devCtrl.ReadAttribute(nodeId, [('*')])))
        self.lPrint('End Reading Dev Attributes')
        jsonStr = self.jsonDumps(data)
        self.lPrint(jsonStr)
        return jsonStr

    def devOn(self, nodeId):
        self.lPrint('on')
        asyncio.run(devCtrl.SendCommand(nodeId, 1, Clusters.OnOff.Commands.On()))
        time.sleep(2)

    def devOff(self, nodeId):
        self.lPrint('off')
        asyncio.run(devCtrl.SendCommand(nodeId, 1, Clusters.OnOff.Commands.Off()))
        time.sleep(2)

    def jsonDumps(self, dm):
        class Base64Encoder(json.JSONEncoder):
            # pylint: disable=method-hidden
            def default(self, o):
                if isinstance(o, bytes):
                    return b64encode(o).decode() #Note we will be able to get back to bytes using b64decode(o)
                if isinstance(o, chip.ChipDeviceCtrl.CommissionableNode):
                    return {
                        "addresses": o.addresses, 
                        "commissioningMode": o.commissioningMode,
                        "deviceName": o.deviceName ,
                        "deviceType": o.deviceType,
                        "hostName": o.hostName ,
                        "instanceName": o.instanceName ,
                        "longDiscriminator": o.longDiscriminator ,
                        "mrpRetryIntervalActive": o.mrpRetryIntervalActive ,
                        "mrpRetryIntervalIdle": o.mrpRetryIntervalIdle ,
                        "pairingHint": o.pairingHint ,
                        "pairingInstruction": o.pairingInstruction ,
                        "port": o.port,
                        "productId": o.productId,
                        "supportsTcp": o.supportsTcp,
                        "vendorId": o.vendorId
                        }
                    
                return o.__dict__ 
            
        def iterator(jsonStr, d):
            if isinstance(d, dict):
                for k, v in d.items():
                    if isinstance(v, dict):
                        if isinstance(k, int):
                            jsonStr = jsonStr + "\"" + str(k) + "\"" + ": {"
                        else:
                            jsonStr = jsonStr + str(k) + ": {"

                        jsonStr = iterator(jsonStr, v)
                    else:
                        jsonStr = jsonStr + "{0} : {1}".format(k, json.dumps(v, cls=Base64Encoder)) + ","
            elif isinstance(d, list):
                for item in d:
                    jsonStr = '{"list":[' + iterator(jsonStr, item) + ']}'
            else: 
                jsonStr = jsonStr + json.dumps(d, cls=Base64Encoder)

            return jsonStr + "},"

        jsonStr = ""
        jsonStr = iterator(jsonStr, dm)
        jsonStr = jsonStr.replace(" ", "")
        jsonStr = jsonStr.replace("\n", "")
        jsonStr = jsonStr.replace("<class'", "\"")
        jsonStr = jsonStr.replace("chip.clusters.Objects.", "")
        jsonStr = jsonStr.replace("chip.clusters.", "")
        jsonStr = jsonStr.replace("\'>", "\"")
        jsonStr = jsonStr.replace("False", "false")
        jsonStr = jsonStr.replace("True", "true")
        jsonStr = jsonStr.replace("Null", "null")
        jsonStr = jsonStr.replace(",}", "}")
        jsonStr = jsonStr.replace(",]", "]")
        jsonStr = jsonStr.rstrip(',')
        jsonStr = "{" + jsonStr

        #to handle the extra curly put in for a list we will remove now - fix this later
        jsonStr = jsonStr.replace("}]}}", "}]}")

        #to handle the extra curly put in for a standard commissionable node entry we will remove now- fix this later
        result = re.search(r"(^{{)(.*?)(}})", jsonStr)
        if (result is not None):
            jsonStr = jsonStr.replace(result.group(0), "{"+result.group(2)+"}")
        return jsonStr


    def cleanStart(self):
        if os.path.isfile('/tmp/repl-storage.json'):
            os.remove('/tmp/repl-storage.json')
        # So that the all-clusters-app won't boot with stale prior state.
        os.system('rm -rf /tmp/chip_*')
        time.sleep(2)

    def ReplInit(self, debug):
        #
        # Install the pretty printer that rich provides to replace the existing
        # printer.
        #
        pretty.install(indent_guides=True, expand_all=True)

        console = Console()

        coloredlogs.install(level='DEBUG')
        chip.logging.RedirectToPythonLogging()

        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.WARN)


    def StackShutdown(self):
        certificateAuthorityManager.Shutdown()
        builtins.chipStack.Shutdown()


    def matterhelp(self, classOrObj=None):
        if (classOrObj is None):
            inspect(builtins.devCtrl, methods=True, help=True, private=False)
            inspect(mattersetlog)
            inspect(mattersetdebug)
        else:
            inspect(classOrObj, methods=True, help=True, private=False)


    def mattersetlog(self, level):
        logging.getLogger().setLevel(level)


    def mattersetdebug(self, enableDebugMode: bool = True):
        ''' Enables debug mode that is utilized by some Matter modules
            to better facilitate debugging of failures (e.g throwing exceptions instead
            of returning well-formatted results).
        '''
        builtins.enableDebugMode = enableDebugMode

    def MatterInit(self, args, debug=True):
        global devCtrl
        global caList
        global chipStack
        global certificateAuthorityManager

        console = Console()

        chip.native.Init()

        self.ReplInit(debug)
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


