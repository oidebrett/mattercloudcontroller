#!/usr/bin/env python

#
#    Copyright (c) 2022 MatterCloudControllera Authors
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

#
#    @file
#      This file implements the Python-based Matter Cloud Controller Process.
#

from __future__ import absolute_import
from __future__ import print_function
import ttp
import pprint

class Templater:
    def __init__(self, response, name):
        self.name = name
        self.response = response

    def get_response(self):
        return self.response

class LsTemplater(Templater):
    def __init__(self, response, name="Ls"):
        self.name = name
        self.response = response

    def parse(self):


        template = """
<group name="bleDevices">
[1649187014.823464][5796:5801] CHIP:DIS: 	Vendor ID: {{vendorID}}
[1649187014.823504][5796:5801] CHIP:DIS: 	Product ID: {{productID}}
[1649187014.823513][5796:5801] CHIP:DIS: 	Long Discriminator: {{longDiscriminator}}
[1649187014.823521][5796:5801] CHIP:DIS: 	Pairing Hint: {{pairingHint}}
[1649187014.823530][5796:5801] CHIP:DIS: 	Hostname: {{hostname}}
[1649187014.823538][5796:5801] CHIP:DIS: 	Instance Name: {{instanceName}}
[1649187014.823556][5796:5801] CHIP:DIS: 	IP Address #1: {{ipAddress#1}}
[1649187014.823556][5796:5801] CHIP:DIS: 	IP Address #2: {{ipAddress#2}}
[1649187014.823556][5796:5801] CHIP:DIS: 	IP Address #3: {{ipAddress#3}}
[1649187014.823587][5796:5801] CHIP:DIS: 	Port: {{port}}
</group>
        """
        print(self.response)
        parser = ttp.ttp(self.response, template)
        parser.parse()
        pprint.pprint(parser.result(), width=100)


class BleScanTemplater(Templater):
    def __init__(self, response, name="BleScan"):
        self.name = name
        self.response = response

    def parse(self):

        template = """
scanning started
<group name="bleDevices">
Name            = {{ MatterDeviceName }} 
ID              = {{ MatterBleId }}
RSSI            = {{ RSSI }}
Address         = {{ BleAdaptorAddress}}
Pairing State   = {{ BlePairingState }}
Discriminator   = {{ MatterDeviceDiscriminator }}
Vendor Id       = {{ MatterDeviceVendorId }}
Product Id      = {{ MatterDeviceProductId }}
Adv UUID        = {{ AdvUUID }}
Adv Data        = {{ AdvData }}
</group>
scanning stopped
        """
        print(self.response)
        parser = ttp.ttp(self.response, template)
        parser.parse()
        pprint.pprint(parser.result(), width=100)

class BleAdapterPrintTemplater(Templater):
    def __init__(self, response, name="BleAdapterPrint"):
        self.name = name
        self.response = response

    def parse(self):

        template = """
AdapterName: {{ AdapterName }}   AdapterAddress: {{ AdapterAddress }}
        """
        print(self.response)
        parser = ttp.ttp(self.response, template)
        parser.parse()
        pprint.pprint(parser.result(), width=100)


