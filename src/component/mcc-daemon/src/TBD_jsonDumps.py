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
import json
import chip.native
import re
from binascii import hexlify, unhexlify

class MatterJsonEncoder(json.JSONEncoder):

    # pylint: disable=method-hidden
    def default(self, o):
        if isinstance(o, bytes):
            return self.hex_from_bytes(o) #we convert the bytes into hex
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
        if isinstance(o, chip.clusters.GeneralDiagnostics.Structs.NetworkInterface): #Added these encoders as the AWS named shadow threw depth issue exceptions
            networkInterfaceObj = {
                "name":o.name,
                "isOperational":o.isOperational,
                "offPremiseServicesReachableIPv4":o.offPremiseServicesReachableIPv4,
                "offPremiseServicesReachableIPv6":o.offPremiseServicesReachableIPv6,
                "hardwareAddress":o.hardwareAddress,
                "IPv4Addresses":o.IPv4Addresses,
                "IPv6Addresses":o.IPv6Addresses,
                "type":o.type
            }

            #fix for error with IOT shadow depth exception check bool(dct)
            networkInterfaceObj['IPv4Addresses'] = self.listToStr(networkInterfaceObj['IPv4Addresses'])
            networkInterfaceObj['IPv6Addresses'] = self.listToStr(networkInterfaceObj['IPv6Addresses'])
            return networkInterfaceObj

        if isinstance(o, chip.clusters.AccessControl.Structs.AccessControlEntryStruct): #Added these encoders as the AWS named shadow threw depth issue exceptions
            aclEntryObj = {
                "privilege": o.privilege,
                "authMode": o.authMode,
                "subjects": o.subjects,
                "targets": o.targets,
                "fabricIndex": o.fabricIndex
            } 
            aclEntryObj['subjects'] = self.listToStr(aclEntryObj['subjects'])
            return aclEntryObj
        if isinstance(o, chip.clusters.Attribute.EventReadResult):
            return {
                "header": o.Header, 
                "status": o.Status,
                "data": o.Data
                }
        if isinstance(o, chip.clusters.Attribute.EventHeader):
            return {
                "EndpointId": o.EndpointId, 
                "ClusterId": o.ClusterId,
                "EventId": o.EventId,
                "EventNumber": o.EventNumber, 
                "Priority": o.Priority,
                "Timestamp": o.Timestamp,
                "TimestampType": o.TimestampType
                }
        if isinstance(o, chip.clusters.Attribute.EventPriority):
            return o.value
        if isinstance(o, chip.clusters.Attribute.EventTimestampType):
            return o.value
            
        return o.__dict__ 

    def bytes_from_hex(self, hex: str) -> bytes:
        """Converts any `hex` string representation including `01:ab:cd` to bytes
        Handles any whitespace including newlines, which are all stripped.
        """
        return unhexlify("".join(hex.replace(":", "").replace(" ", "").split()))


    def hex_from_bytes(self, b: bytes) -> str:
        """Converts a bytes object `b` into a hex string (reverse of bytes_from_hex)"""
        return hexlify(b).decode("utf-8")

    #This is a short term fix as the depth of the AWS JSON shadow documents are limited
    #so we need to reduce lists to strings in some cases
    def listToStr(self,listObject):
        if type(listObject) == list:
            listStr = "["
            separator = ""
            for listItem in listObject:
                if isinstance(listItem, bytes):
                    #convert from bytes to hex
                    listStr += separator + self.hex_from_bytes(listItem)
                elif isinstance(listItem, int):
                    #convert from int to str
                    listStr += separator + str(listItem)

                separator = ","
            listStr += "]"
        return listStr


def jsonDumps(dm):

    def cleanUpClassNames(jsonStr):
        #to handle the extra classname we will remove now
        result = re.search(r"<class\'chip.clusters.Objects.([^.]*)\'>", jsonStr)
        while (result is not None):
            jsonStr = jsonStr.replace(result.group(0), '"'+result.group(1)+'"')
            result = re.search(r"<class\'chip.clusters.Objects.([^.]*)\'>", jsonStr)

        result = re.search(r"<class\'chip.clusters.Objects.(\w+).Attributes.([^.]*)\'>", jsonStr)
        while (result is not None):
            jsonStr = jsonStr.replace(result.group(0), '"'+result.group(2)+'"')
            result = re.search(r"<class\'chip.clusters.Objects.(\w+).Attributes.([^.]*)\'>", jsonStr)

        result = re.search(r"\"([\w+]+)\":{<class\'chip.clusters.Attribute.DataVersion\'>", jsonStr)
        while (result is not None):
            jsonStr = jsonStr.replace(result.group(0), '"'+result.group(1)+'":{"'+result.group(1)+'.DataVersion"')
            result = re.search(r"\"([\w+]+)\":{<class\'chip.clusters.Attribute.DataVersion\'>", jsonStr)

        return jsonStr

    #turn list in a string and use the custom encoder in the process 
    def listToStr(lst):
        if len(lst) == 0:
            return '[]'
        elif isinstance(lst[0], list):
            return '[' + listToStr(lst[0]) + ',' + listToStr(lst[1:])[1:]
        elif len(lst) == 1:
            return '[' + json.dumps(lst[0], cls=MatterJsonEncoder) + ']'
        else:
            return '[' + json.dumps(lst[0], cls=MatterJsonEncoder) + ',' + listToStr(lst[1:])[1:]


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
                    jsonStr = jsonStr + "{0} : {1}".format(k, json.dumps(v, cls=MatterJsonEncoder)) + ","
        elif isinstance(d, list):
            jsonStr = jsonStr + '"list":' + listToStr(d)
        elif isinstance(d, object):
            jsonStr = jsonStr + json.dumps(d, cls=MatterJsonEncoder)

        jsonStr = jsonStr + "},"

        return jsonStr

    #Code starts here
    jsonStr = ""
    jsonStr = iterator(jsonStr, dm) # iterate over the object and do any custom encoding that is required
    jsonStr = jsonStr.replace(" ", "")
    jsonStr = jsonStr.replace("\n", "")

    #call function to clean up class names in json str
    jsonStr = cleanUpClassNames(jsonStr)

    jsonStr = jsonStr.replace("False", "false")
    jsonStr = jsonStr.replace("True", "true")
    jsonStr = jsonStr.replace("Null", "null")
    jsonStr = jsonStr.replace("{}", "\"\"") #this was added to avoid errors in iot shadow
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



