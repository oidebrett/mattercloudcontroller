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


