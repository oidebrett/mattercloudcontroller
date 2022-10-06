import sys
import time
import asyncio
import subprocess
import json
import re
from pprint import pformat
from rich import print
from rich.pretty import pprint
from rich import pretty
from rich import inspect
from rich.console import Console
import logging
from chip import ChipDeviceCtrl
import chip.clusters as Clusters
from chip.ChipStack import *
import coloredlogs
import chip.logging
import argparse
import builtins
import chip.FabricAdmin
import chip.CertificateAuthority
import chip.native
import chip.discovery
from chip.utils import CommissioningBuildingBlocks
import atexit

_fabricAdmins = None

class MatterDeviceController(object):
    args = None
    commissionedDevices = []
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

    def discoverDevices(self):
        self.lPrint("Discovering devices")
        for nodeId in range(1,self.MAX_DEVICES+1):
            try:
                err = devCtrl.ResolveNode(int(nodeId))
                if err == 0:
                    ret = devCtrl.GetAddressAndPort(int(nodeId))
                    if ret == None:
                        self.lPrint("Get address and port failed: " + str(nodeId))
                    else:
                        self.commissionedDevices.append(nodeId)
                else:
                    self.lPrint("Resolve node failed [{}]".format(err))
            except:
                self.lPrint("No discovered devices on nodeId:" + str(nodeId))

        return self.commissionedDevices

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

    def getCommissionedDevices(self):
        #return self.commissionedDevices
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
            #ipAddressAsBytes = str.encode(ipAddress)
            #builtins.devCtrl.CommissionIP(ipAddressAsBytes, 20202021, nodeId)
            #self.commissionedDevices.append(nodeId)
            self.fabricDevices.add(nodeId)
            time.sleep(10)
            return nodeId
        except Exception as e:
            self.lPrint("Commission failed: ", e.message)
            return -1

    def readDevAttributesAsJsonStr(self, nodeId):
        self.lPrint('Start Reading Dev Attributes')
        data = (asyncio.run(devCtrl.ReadAttribute(nodeId, [Clusters.OnOff])))
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
        #this method is required as dumps doesnt work with advanced types
        dmstr = pformat(dm)
        dmstr = dmstr.replace(" ", "")
        dmstr = dmstr.replace("\n", "")
        dmstr = dmstr.replace("<class'", "\"")
        dmstr = dmstr.replace("\'>", "\"")
        dmstr = dmstr.replace("False", "false")
        dmstr = dmstr.replace("True", "true")
        dmstr = dmstr.replace("Null", "null")
        dmstr = dmstr.replace("<OnOffStartUpOnOff.kOff:0>", "0")
        dmstr = dmstr.replace("<OnOffStartUpOnOff.kOn:1>", "1")
        dmstr = dmstr.replace("1>", "1")
        line = re.sub(r"(\d+)(:)", "\"\g<1>\":", dmstr)
        return line

    def testDumps(self, dm):
        #this method is required as dumps doesnt work with advanced types
        dmstr = pprint.pformat(dm)
        return dmstr

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

        console.rule('Matter REPL')
        console.print('''
                [bold blue]
        
                Welcome to the Matter Python REPL!
        
                For help, please type [/][bold green]matterhelp()[/][bold blue]
        
                To get more information on a particular object/class, you can pass
                that into [bold green]matterhelp()[/][bold blue] as well.
        
                ''')
        console.rule()

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


