import os
import logging
import sys
import time
import json
import re
import pprint
import builtins
from rich.console import Console
from rich import pretty
import coloredlogs
from chip import ChipDeviceCtrl
from chip import ChipCommissionableNodeCtrl
import chip.clusters as Clusters
from chip.ChipStack import *
import chip.FabricAdmin
import chip.logging
import asyncio
import subprocess


class MatterDeviceController(object):
    args = None
    commissionedDevices = []

    def __init__(self,args):    
        self.args = args

    def lPrint(self,msg):
        console = Console()
        console.print(msg)
        logging.info(msg)
        print(msg, file=sys.stdout)
        sys.stderr.flush()

    def devCtrlStart(self):
        global devCtrl
        fabricAdmins = self.LoadFabricAdmins()
        devCtrl = self.CreateDefaultDeviceController()
        builtins.devCtrl = devCtrl

    def LoadFabricAdmins(self):
        global _fabricAdmins

        #
        # Shutdown any fabric admins we had before as well as active controllers. This ensures we
        # relinquish some resources if this is called multiple times (e.g in a Jupyter notebook)
        #
        chip.FabricAdmin.FabricAdmin.ShutdownAll()
        ChipDeviceCtrl.ChipDeviceController.ShutdownAll()
        _fabricAdmins = []
        storageMgr = builtins.chipStack.GetStorageManager()
        console = Console()

        try:
            adminList = storageMgr.GetReplKey('fabricAdmins')
        except KeyError:
            self.lPrint("\n[purple]No previous fabric admins discovered in persistent storage - creating a new one...")
            _fabricAdmins.append(chip.FabricAdmin.FabricAdmin())
            return _fabricAdmins
        self.lPrint('\n')
        
        for k in adminList:
            self.lPrint(f"[purple]Restoring FabricAdmin from storage to manage FabricId {adminList[k]['fabricId']}, FabricIndex {k}...")
            _fabricAdmins.append(chip.FabricAdmin.FabricAdmin(fabricId=adminList[k]['fabricId'], fabricIndex=int(k)))

        self.lPrint('\n[blue]Fabric Admins have been loaded and are available at [red]fabricAdmins')
        return _fabricAdmins
        
    def CreateDefaultDeviceController(self):
        global _fabricAdmins
        
        if (len(_fabricAdmins) == 0):
            raise RuntimeError("Was called before calling LoadFabricAdmins()")
        self.lPrint('\n')
        self.lPrint(f"[purple]Creating default device controller on fabric {_fabricAdmins[0]._fabricId}...")
        return _fabricAdmins[0].NewController()

    def MatterInit(self):
        global console,chipStack
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
                that into [bold green]matterhelp()[/][bold blue] as well.''')
        console.rule()
        
        coloredlogs.install(level='DEBUG')
        chip.logging.RedirectToPythonLogging()
        
        #logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.WARN)

        #
        # Set up the ChipStack.
        #
        try:
            chipStack = ChipStack(persistentStoragePath=self.args.storagepath)
        except KeyError:
            self.lPrint("caught error")
            chipStack = ChipStack(persistentStoragePath=self.args.storagepath)

    def getCommissionedDevices(self):
        return self.commissionedDevices

    def commissionDevice(self, ipAddress, nodeId):
        time.sleep(5)
        self.lPrint("Commissioning")
        ipAddressAsBytes = str.encode(ipAddress)
        devCtrl.CommissionIP(ipAddressAsBytes, 20202021, nodeId)
        self.commissionedDevices.append(nodeId)
        time.sleep(10)

    def readDevAttributesAsJsonStr(self, nodeId):
        data = (asyncio.run(devCtrl.ReadAttribute(nodeId, [Clusters.OnOff])))
        jsonStr = self.jsonDumps(data)
        return jsonStr

    def devOn(self):
        self.lPrint('on')
        asyncio.run(devCtrl.SendCommand(3, 1, Clusters.OnOff.Commands.On()))
        time.sleep(2)

    def devOff(self):
        self.lPrint('off')
        asyncio.run(devCtrl.SendCommand(3, 1, Clusters.OnOff.Commands.Off()))
        time.sleep(2)

    def jsonDumps(self, dm):
        #this method is required as dumps doesnt work with advanced types
        dmstr = pprint.pformat(dm)
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

    def cleanStart(self, workingDir):
        if os.path.isfile('/tmp/repl-storage.json'):
            os.remove('/tmp/repl-storage.json')
        # So that the all-clusters-app won't boot with stale prior state.
        os.system('rm -rf /tmp/chip_*')
        os.chdir(workingDir)
        time.sleep(2)


