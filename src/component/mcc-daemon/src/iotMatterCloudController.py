#!/home/ubuntu/connectedhomeip/out/python_env/bin/python
"""
Listen for incoming chip requests and publish the results onto response topic
--request-topic - defaults to chip/request
--response-topic - defaults to chip/response

Command message structure (JSON):
{
    "command": "onoff toggle 1",
    "txid": "12345ABC",
    "format": "json|text",
    "timeout": 10
}
- `command` - full string to pass to chip
- `txid` - unique id to track status of message, returned as part of response.
  Note: New commands cannot use the id of any in-flight operations that have not completed.
- `format` - Optional, default json. Format of response message. JSON is serialized string,
  text is key value formatted with response as everything after the RESPONSE: line.
- `timeout` - Optional, default is 10 seconds. Amount of time for the command to complete.
- Total payload size must be less than 128KiB in size, including request topic.
- Command will run as default ggc_user unless changed in the recipe file
Response message structure (JSON):
{
    "txid": "12345ABC",
    "return_code": 0,
    "response": "total 17688\n-rw-r--r--   1 ggc_user  staff     8939 Apr 30 16:37 README.md\n"
}
- If response is greater than 128KiB, exit_code will be set to 255 and "payload too long" response.
- Malformed request with set exit_code  to 255 and "malformed request/missing transaction id/etc" response.
"""

from datetime import datetime
import traceback
#import boto3
#import botocore
import sys
import subprocess
import os
import sys
import json
import time
import datetime
import uuid
import logger
import awsiot.greengrasscoreipc
import awsiot.greengrasscoreipc.client as client
from awsiot.greengrasscoreipc.model import (
    IoTCoreMessage,
    QOS,
    SubscribeToIoTCoreRequest,
    PublishToIoTCoreRequest,
    SubscribeToTopicRequest,
    SubscriptionResponseMessage,
    ListNamedShadowsForThingRequest,
    GetThingShadowRequest,
    UpdateThingShadowRequest
)

from rich.console import Console
import argparse
from rich import pretty
import coloredlogs
from chip import ChipDeviceCtrl
from chip import ChipCommissionableNodeCtrl
import chip.clusters as Clusters
from chip.ChipStack import *
import chip.FabricAdmin
import chip.logging
import logging
import builtins
import asyncio
import subprocess

import iotMatterRuleEngine

curr_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(curr_dir)
sleep_time_in_sec = int(os.environ.get('SLEEP_TIME', '5'))

RESPONSE_FORMAT = "json"
TIMEOUT = 10
MSG_TIMEOUT = f"Command timed out, limit of {TIMEOUT} seconds"
MSG_MISSING_ATTRIBUTE = "The attributes 'txid' and 'command' missing from request"
MSG_INVALID_JSON = "Request message was not a valid JSON object"
THING_NAME = os.getenv('AWS_IOT_THING_NAME')

# Set up request topic and response topic from passed in arguments
REQUEST_TOPIC = "chip/request"
RESPONSE_TOPIC = "chip/response"


parser = argparse.ArgumentParser()
parser.add_argument("-p", "--storagepath", help="Path to persistent storage configuration file (default: /tmp/repl-storage.json)", action="store", default="/tmp/repl-storage.json")
parser.add_argument("-t", "--test", help="true if testing local", action="store", default="False")
args = parser.parse_args()
LOCAL_TEST_ARG = args.test

LOCAL_TEST = LOCAL_TEST_ARG.lower() == 'true'

def lPrint(msg):
    console = Console()
    console.print(msg)
    logging.info(msg)
    print(msg, file=sys.stdout)
    sys.stderr.flush()


lPrint("LOCAL_TEST: "+str(LOCAL_TEST))

if not LOCAL_TEST:
    logger.info("not LOCAL_TEST")
    workingDir = "/home/ubuntu/connectedhomeip"
    ipc_client = awsiot.greengrasscoreipc.connect()
else:
    logger.info("is LOCAL_TEST")
    workingDir = "/home/ivob/Projects/connectedhomeip"
    _sample_file_name = 'sample_data.json'


_topic = None
_thing_name = None
_version = None

#This topic is triggered every time the shadow is updated.
subscribeShadowUpdateTopic = "$aws/things/mcc-thing-ver01-1/shadow/name/2/update/accepted"

messages = []
class RequestsHandler(logging.Handler):
    def emit(self, record):
        """Send the log records (created by loggers) to
        the appropriate destination.
        """
        #lPrint(record.getMessage())
        messages.append(record.getMessage())

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()
handler = RequestsHandler()
logger.addHandler(handler)

def loadSampleData(file_name: str):
    with open(curr_dir + '/' + file_name) as f:
        try:
            sample = json.load(f)
            f.close()
            return sample
        except:
            return json.loads('''{}''')


def clearSampleData(file_name: str):
    file = open(curr_dir + '/' + file_name,"r+")
    file. truncate(0)
    file. close()

def loadAndCleanSampleData(file_name: str):
    sample = loadSampleData(file_name)
    clearSampleData(file_name)
    return sample

def pollForCommand(file_name: str):
    sample = loadAndCleanSampleData(file_name)
    lPrint(sample)
    try:
        command = sample["command"]
        lPrint(command)
        if command == "commission":
            if not LOCAL_TEST:
                commissionDevice('192.168.0.12')
            else:
                commissionDevice('127.0.0.1')
                readDevAttributes()
        elif command == "on":
            devOn()
        elif command == "off":
            devOff()
    except:
        pass

def load_environ():
    global _topic, _thing_name, _version
    _topic = os.environ.get('RULE_TOPIC', 'test/rule/topic')
    _thing_name = os.environ.get('AWS_IOT_THING_NAME', 'DevLocal')
    _version = os.environ.get('FUNCTION_VERION', 'not-defined')
    lPrint('--->load_environ: topic- {}'.format(_topic))
    lPrint('--->load_environ: lambda version- {} at {}--==<<'.format(_version, str(datetime.datetime.now())))

#Respond to a MQTT message
def respond(event):
    resp = {}
    resp["return_code"] = 200
    resp["response"] = ""
    response_format = RESPONSE_FORMAT
    operation_timeout = TIMEOUT
    
    # validate message and attributes
    try:
        message_from_core = json.loads(event.message.payload.decode())

        lPrint('message from core {}: '.format(message_from_core))

        # Verify required keys are provided
        if not all(k in message_from_core for k in ("txid", "command")):
            resp["response"] = MSG_MISSING_ATTRIBUTE
            resp["return_code"] = 255
            response_message = {
                "timestamp": int(round(time.time() * 1000)),
                "message": str(event.message.payload),
                "response": resp["response"],
                "return_code": resp["return_code"]
                }
            # Publish to our topic
            response = PublishToIoTCoreRequest()
            response.topic_name = RESPONSE_TOPIC
            response.payload = bytes(json.dumps(response_message), "utf-8")
            response.qos = QOS.AT_MOST_ONCE
            response_op = ipc_client.new_publish_to_iot_core()
            response_op.activate(response)
            lPrint('{} for message: '.format(MSG_MISSING_ATTRIBUTE))
            lPrint('for message: '.format(message))
            return
        
        # check for and update optional settings
        for k in message_from_core:
            if k.lower() == "timeout" and isinstance(message_from_core[k], (int, float)):
                operation_timeout = message_from_core[k]
            elif k.lower() == "format" and (
                any(format in message_from_core[k] for format in ["json", "text"])
            ):
                response_format = message_from_core[k].lower()

    except json.JSONDecodeError as e:
        resp["response"] = MSG_INVALID_JSON
        resp["return_code"] = 255
        response_message = {
            "timestamp": int(round(time.time() * 1000)),
            "message": str(event.message.payload),
            "response": resp["response"],
            "return_code": resp["return_code"]
            }
        # Publish to our topic
        response = PublishToIoTCoreRequest()
        response.topic_name = RESPONSE_TOPIC
        response.payload = bytes(json.dumps(response_message), "utf-8")
        response.qos = QOS.AT_MOST_ONCE
        response_op = ipc_client.new_publish_to_iot_core()
        response_op.activate(response)        
        lPrint(f"{MSG_INVALID_JSON} for message: {message}")
        return
    except Exception as e:
        raise
    
    command = message_from_core["command"]
    command = command.lstrip()
    lPrint(command)

    if command == "commission":
        commissionDevice('192.168.0.12')
        resp["response"] = "commissioned"
        resp["return_code"] = 200
        resp["txid"] = message_from_core["txid"]
    elif command == "on":
        devOn()
        resp["response"] = "turned on"
        resp["return_code"] = 200
        resp["txid"] = message_from_core["txid"]
    elif command == "off":
        devOff()
        resp["response"] = "turned off"
        resp["return_code"] = 200
        resp["txid"] = message_from_core["txid"]
    else:
        
        try:
            output = subprocess.run(
                command,
                timeout=operation_timeout,
                capture_output=True,
                shell=True,
                )
            
            if output.returncode == 0:
                resp["response"] = output.stdout.decode("utf-8")
            else:
                resp["response"] = output.stderr.decode("utf-8")
                resp["return_code"] = output.returncode
            resp["txid"] = message_from_core["txid"]
            lPrint(resp["response"])
        except subprocess.TimeoutExpired:
            resp["response"] = MSG_TIMEOUT


    # Dummy response message
    response_message = {
        "timestamp": int(round(time.time() * 1000)),
        "message": str(event.message.payload),
        "txid": str(resp["txid"]),
        "response": resp["response"],
        "return_code": resp["return_code"]
        }

    # Print the message to stdout, which Greengrass saves in a log file.
    lPrint("event.message.payload:" + str(event.message.payload))

    # Publish to our topic
    response = PublishToIoTCoreRequest()
    response.topic_name = RESPONSE_TOPIC
    response.payload = bytes(json.dumps(response_message), "utf-8")
    response.qos = QOS.AT_MOST_ONCE
    response_op = ipc_client.new_publish_to_iot_core()
    response_op.activate(response)

#Start of the code that is not used for local testing
if not LOCAL_TEST:
    #Handler for stream callback
    class StreamHandler(client.SubscribeToIoTCoreStreamHandler):
        def __init__(self):
            super().__init__()

        def on_stream_event(self, event: IoTCoreMessage) -> None:
            lPrint("on_stream_event")
            lPrint(event)
            try:
                # Handle message.
                respond(event)
            except:
                traceback.print_exc()

        def on_stream_error(self, error: Exception) -> bool:
            # Handle error.
            lPrint("on_stream_error")
            return True  # Return True to close stream, False to keep stream open.

        def on_stream_closed(self) -> None:
            # Handle close.
            pass

    #Handler for subscription callback
    class SubHandler(client.SubscribeToTopicStreamHandler):
        def __init__(self):
            super().__init__()

        def on_stream_event(self, event: SubscriptionResponseMessage) -> None:

            lPrint(event)

            try:
                message_string = str(event.binary_message.message, "utf-8")
                # Load message and check values
                jsonmsg = json.loads(message_string)

                lPrint(jsonmsg)

                #if redledon is equal to true/1 then turn on else off
                if jsonmsg['state']['desired']['on']:
                    lPrint("true turn led on")
                    #set current status to bad and update actual value of led output to reported
                    devOn()
                else:
                    lPrint("false turn led off")
                    #set current status to good and update actual value of led output to reported
                    devOff()

            except:
                traceback.print_exc()

        def on_stream_error(self, error: Exception) -> bool:
            # Handle error.
            return True  # Return True to close stream, False to keep stream open.

        def on_stream_closed(self) -> None:
            # Handle close.
            pass

#Get the shadow from the local IPC
def sample_get_thing_shadow_request(thingName, shadowName):
    lPrint("getting_thing_shadow_request: "+shadowName)

    try:
        lPrint("Getting ipc_client")
        # set up IPC client to connect to the IPC server
        ipc_client = awsiot.greengrasscoreipc.connect()
                            
        # create the GetThingShadow request
        get_thing_shadow_request = GetThingShadowRequest()
        get_thing_shadow_request.thing_name = thingName
        get_thing_shadow_request.shadow_name = shadowName
        
        # retrieve the GetThingShadow response after sending the request to the IPC server
        op = ipc_client.new_get_thing_shadow()
        op.activate(get_thing_shadow_request)
        fut = op.get_response()
        
        result = fut.result(TIMEOUT)

        return result.payload
        
    except Exception as e:
        lPrint("Error get shadow")
        # except ResourceNotFoundError | UnauthorizedError | ServiceError

#Set the local shadow using the IPC
def sample_update_thing_shadow_request(thingName, shadowName, payload):
    try:
        # set up IPC client to connect to the IPC server
        ipc_client = awsiot.greengrasscoreipc.connect()
                
        # create the UpdateThingShadow request
        update_thing_shadow_request = UpdateThingShadowRequest()
        update_thing_shadow_request.thing_name = thingName
        update_thing_shadow_request.shadow_name = shadowName
        update_thing_shadow_request.payload = payload
                        
        # retrieve the UpdateThingShadow response after sending the request to the IPC server
        op = ipc_client.new_update_thing_shadow()
        op.activate(update_thing_shadow_request)
        fut = op.get_response()
        
        result = fut.result(TIMEOUT)
        return result.payload
        
    except Exception as e:
        lPrint("Error update shadow")
        # except ConflictError | UnauthorizedError | ServiceError

#End of the code that is not used for local testing


def LoadFabricAdmins():
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
        lPrint("\n[purple]No previous fabric admins discovered in persistent storage - creating a new one...")
        _fabricAdmins.append(chip.FabricAdmin.FabricAdmin())
        return _fabricAdmins
    lPrint('\n')
    
    for k in adminList:
        lPrint(f"[purple]Restoring FabricAdmin from storage to manage FabricId {adminList[k]['fabricId']}, FabricIndex {k}...")
        _fabricAdmins.append(chip.FabricAdmin.FabricAdmin(fabricId=adminList[k]['fabricId'], fabricIndex=int(k)))

    lPrint('\n[blue]Fabric Admins have been loaded and are available at [red]fabricAdmins')
    return _fabricAdmins
    
def CreateDefaultDeviceController():
    global _fabricAdmins
    
    if (len(_fabricAdmins) == 0):
        raise RuntimeError("Was called before calling LoadFabricAdmins()")
    lPrint('\n')
    lPrint(f"[purple]Creating default device controller on fabric {_fabricAdmins[0]._fabricId}...")
    return _fabricAdmins[0].NewController()

def ReplInit():
    global console
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




def devCtrlStart():
    global devCtrl
    fabricAdmins = LoadFabricAdmins()
    devCtrl = CreateDefaultDeviceController()
    builtins.devCtrl = devCtrl

def cleanStart():
    if os.path.isfile('/tmp/repl-storage.json'):
        os.remove('/tmp/repl-storage.json')
    # So that the all-clusters-app won't boot with stale prior state.
    os.system('rm -rf /tmp/chip_*')
    os.chdir(workingDir)
    time.sleep(2)

def commissionDevice(ipAddress):
    time.sleep(5)
    lPrint("Commissioning")
    ipAddressAsBytes = str.encode(ipAddress)
    devCtrl.CommissionIP(ipAddressAsBytes, 20202021, 2)
    time.sleep(10)

def readDevAttributes():
    data = (asyncio.run(devCtrl.ReadAttribute(2, [(1, Clusters.OnOff)])))
    matterRules = iotMatterRuleEngine.MatterRuleEngine(args)
    jsonStr = matterRules.jsonDumps(data)
    lPrint(jsonStr)
    a = json.loads(jsonStr)   
    lPrint("Print json object for Attributes.OnOff") 
    lPrint(a['1']['chip.clusters.Objects.OnOff']['chip.clusters.Objects.OnOff.Attributes.OnOff'])
    lPrint("Print json object for Attributes.GlobalSceneControl") 
    lPrint(a['1']['chip.clusters.Objects.OnOff']['chip.clusters.Objects.OnOff.Attributes.GlobalSceneControl'])

def devOn():
    lPrint('on')
    asyncio.run(devCtrl.SendCommand(2, 1, Clusters.OnOff.Commands.On()))
    time.sleep(2)

def devOff():
    lPrint('off')
    asyncio.run(devCtrl.SendCommand(2, 1, Clusters.OnOff.Commands.Off()))
    time.sleep(2)

def wait_for_many_discovered_devices():
    # Discovery happens through mdns, which means we need to wait for responses to come back.
    # x number of responses are received. For now, just 2 seconds. We can all wait that long.
    lPrint("Waiting for device responses...")
    time.sleep(2)

def exitGracefully():
    a = (asyncio.run(devCtrl.ReadAttribute(2, [(1, Clusters.OnOff)])))
    lPrint(a)
    # To stop subscribing, close the operation stream.
    if not LOCAL_TEST:
        operation1.close()
        operation2.close()
    lPrint("exiting gracefully")

def main():
    global operation1
    global operation2

    message = "Hello!"

    # Print the message to stdout, which Greengrass saves in a log file.
    lPrint(message)

    if not LOCAL_TEST:
        lPrint("Setting up the MQTT Subscription")
        # Setup the MQTT Subscription
        qos = QOS.AT_MOST_ONCE
        request1 = SubscribeToIoTCoreRequest()
        request1.topic_name = REQUEST_TOPIC
        request1.qos = qos
        handler1 = StreamHandler()
        operation1 = ipc_client.new_subscribe_to_iot_core(handler1)
        future1 = operation1.activate(request1)
        future1.result(TIMEOUT)

        lPrint("Setting up the Shadow Subscription")
        # Setup the Shadow Subscription
        request2 = SubscribeToTopicRequest()
        request2.topic = subscribeShadowUpdateTopic 
        handler2 = SubHandler()
        operation2 = ipc_client.new_subscribe_to_topic(handler2) 
        future2 = operation2.activate(request2)
        future2.result(TIMEOUT)

    lPrint('------------------------run-------------------')
    load_environ()

    topic = '{}/{}'.format(_topic, _thing_name)

    #Setting up the chip repl
    console = Console()
    console.print("Current Working Directory " , os.getcwd())
    cleanStart()
    lPrint("Current Working Directory " + os.getcwd())
    ReplInit()

    try:
        chipStack = ChipStack(persistentStoragePath=args.storagepath)
    except KeyError:
        lPrint("caught error")
        chipStack = ChipStack(persistentStoragePath=args.storagepath)

    devCtrlStart()

    commissionableNodeCtrl = ChipCommissionableNodeCtrl.ChipCommissionableNodeController(chipStack)

    lPrint(commissionableNodeCtrl)
    
    logging.getLogger().setLevel(logging.DEBUG)
    messages = []
    devCtrl.DiscoverCommissionableNodesCommissioningEnabled()
    wait_for_many_discovered_devices()
    devCtrl.PrintDiscoveredDevices()
    print(messages)
    logging.getLogger().setLevel(logging.WARN)
    #commissionDevice()

    # Keep the main thread alive, or the process will exit.
    x=1
    #initial settings for the reported states of the device
    currentstate = json.loads('''{"state": {"reported": {"status": "startup","on": false}}}''')

    while True:
        lPrint(x)
        x += 1

        if LOCAL_TEST:
            pollForCommand(_sample_file_name)

        lPrint('--->run: sleep- {}'.format(sleep_time_in_sec) + " " + REQUEST_TOPIC)
        time.sleep(sleep_time_in_sec)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        exitGracefully()
        pass
        
