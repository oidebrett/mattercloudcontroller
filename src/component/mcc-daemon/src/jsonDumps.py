from base64 import b64encode, b64decode
import json
import chip.native
import re



def jsonDumps(dm):
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

    def cleanUpClassNames(jsonStr):
        #to handle the extra classname we will remove now
        #First we need to make the Dataversion unique - otherwise the AWS device shadow complains
        #result = re.search(r"<class\'chip.clusters.Objects.([^.]*)\'>:{<class\'chip.clusters.Attribute.DataVersion\'>", jsonStr)
        #while (result is not None):
        #    newDataVersionClassName= f"<class'chip.clusters.Attribute.{result.group(1)}.DataVersion'>"
        #    newStr = "<class\'chip.clusters.Objects."+result.group(1)+"\'>:{"+newDataVersionClassName
        #    jsonStr = jsonStr.replace(result.group(0), newStr)
        #    result = re.search(r"<class\'chip.clusters.Objects.([^.]*)\'>:{<class\'chip.clusters.Attribute.DataVersion\'>", jsonStr)

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

    #call function to clean up class names in json str
    jsonStr = cleanUpClassNames(jsonStr)

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



