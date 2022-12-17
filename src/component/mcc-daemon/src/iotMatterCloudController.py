#!/home/ubuntu/connectedhomeip/out/python_env/bin/python
"""
Listen for incoming chip requests and publish the results onto response topic
--request-topic - defaults to chip/request
--response-topic - defaults to chip/response

Command message structure (JSON):
{
    "command": "commission",
    "id":"192.168.0.36 | 1",
    "txid": "12345ABC",
    "format": "json|text",
    "timeout": 10
}
- `command` - full string to pass to chip
- `id` - is the IP address when commissioning and the node id when sending a command
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
import argparse
from rich.console import Console
from rich import pretty
import coloredlogs
import logging
import shlex

parser = argparse.ArgumentParser()
parser.add_argument("-p", "--storagepath", help="Path to persistent storage configuration file (default: /tmp/repl-storage.json)", action="store", default="/tmp/repl-storage.json")
parser.add_argument("-t", "--test", help="true if testing local", action="store", default="False")
parser.add_argument("-c", "--clean", help="true to clean working directory", action="store", default="False")
args = parser.parse_args()
LOCAL_TEST_ARG = args.test
LOCAL_TEST = LOCAL_TEST_ARG.lower() == 'true'
CLEAN_ARG = args.clean
CLEAN = CLEAN_ARG.lower() == 'true'

if not LOCAL_TEST:
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

import iotMatterDeviceController

curr_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(curr_dir)
sleep_time_in_sec = int(os.environ.get('SLEEP_TIME', '10'))

RESPONSE_FORMAT = "json"
TIMEOUT = 10
MSG_TIMEOUT = f"Command timed out, limit of {TIMEOUT} seconds"
MSG_MISSING_ATTRIBUTE = "The attributes 'txid' and 'command' missing from request"
MSG_INVALID_JSON = "Request message was not a valid JSON object"
THING_NAME = os.getenv('AWS_IOT_THING_NAME')

# Set up request topic and response topic from passed in arguments
REQUEST_TOPIC = "chip/request"
RESPONSE_TOPIC = "chip/response"


#create variable for matterDevices to store all information relating to local devices
matterDevices = None

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
    #workingDir = "/home/ivob/Projects/v1.0.0/connectedhomeip"
    workingDir = "/home/ubuntu/connectedhomeip"
    _sample_file_name = 'sample_data.json'


_topic = None
_thing_name = None
_version = None

def runUnixCommand(command):
    response = ""
    try:
        process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE)
        while True:
            output = process.stdout.readline().decode()
            if output == '' and process.poll() is not None:
                break
            if output:
                response += (output.strip()) + '\n'
        rc = process.poll()
        return response
    except subprocess.TimeoutExpired:
        logger.error(
            f"Comand took longer than {TIMEOUT} seconds for message"
        )

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

def pollForDeviceReports():
    thingName = 'mcc-thing-ver01-1'
    lPrint("pollForDeviceReports.........")
    
    deviceNodeIds = matterDevices.getCommissionedDevices()
    time.sleep(2)

    for nodeId in deviceNodeIds:
        #check device to read current state
        currentStateStr = matterDevices.readDevAttributesAsJsonStr(nodeId)

        #just print out the response for now
        lPrint(currentStateStr)

        if not LOCAL_TEST:
            #set the device shadow for test
            shadowName = str(nodeId)
            newStr = '{"state": {"reported": '+currentStateStr+'}}'
            lPrint(newStr)
#            newState = json.loads(newStr)
#            sample_update_thing_shadow_request(thingName, shadowName, bytes(json.dumps(newState), "utf-8"))
            sample_update_thing_shadow_request(thingName, shadowName, bytes(newStr, "utf-8"))

def pollForCommand(file_name: str):
    sample = loadAndCleanSampleData(file_name)
    lPrint(sample)
    nodeId = None
    try:
        command = sample["command"]
        lPrint(command)
        if command == "commission":
            id = sample["id"]
            if not LOCAL_TEST:
                nodeId = matterDevices.commissionDevice(id)
                currentStateStr = matterDevices.readDevAttributesAsJsonStr(nodeId)
            else:
                lPrint("Calling commissionDevice function")
                nodeId = matterDevices.commissionDevice(id)
                time.sleep(10)
                lPrint("Calling readDevAttributesAsJsonStr function on nodeId:")
                currentStateStr = matterDevices.readDevAttributesAsJsonStr(nodeId)
                lPrint("FInished ReadDevAttributesAsJsonStr function")
                lPrint(currentStateStr)
                #set the device shadow for the thing
                shadowName = str(nodeId)
                thingName = 'mcc-thing-ver01-1'
                newStr = '{"state": {"reported": '+currentStateStr+'}}'
                lPrint(newStr)
                newState = json.loads(newStr)
                lPrint(newState)

        if command == "discover": # we always have to update the discoveredCommissionableDevices after we commission
            discoveredCommissionableNodes = matterDevices.discoverCommissionableDevices()
            commissionableNodesJsonStr = matterDevices.jsonDumps(discoveredCommissionableNodes)
            lPrint(commissionableNodesJsonStr)
            if not LOCAL_TEST:
                #set the device shadow for commissionableNodes
                shadowName = "commissionableNodes"
                thingName = 'mcc-thing-ver01-1'
                newStr = '{"state": {"desired": '+commissionableNodesJsonStr+',"reported": '+commissionableNodesJsonStr+'}}'
                #lPrint(newStr)
                #newState = json.loads(newStr)
                #sample_update_thing_shadow_request(thingName, shadowName, bytes(json.dumps(newState), "utf-8"))
                sample_update_thing_shadow_request(thingName, shadowName, bytes(newStr, "utf-8"))
            else:
                pass

        elif command == "on":
            id = sample["id"]
            lPrint("Turning On")
            nodeId = int(id)
            matterDevices.devOn(nodeId)
        elif command == "off":
            id = sample["id"]
            lPrint("Turning Off")
            nodeId = int(id)
            matterDevices.devOff(nodeId)
        elif command == "resolve":
            id = sample["id"]
            lPrint("Resolving")
            nodeId = int(id)
            #Try running a command
            command = f'examples/chip-tool/out/debug/chip-tool discover resolve {nodeId} {matterDevices.getFabricId()}'
            output = runUnixCommand(command)
            lPrint(output)

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
            #lPrint('for message: '.format(message))
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

    nodeId = None
    if command == "commission":
        id = message_from_core["id"]
        nodeId = matterDevices.commissionDevice(id)
        currentStateStr = matterDevices.readDevAttributesAsJsonStr(nodeId)
        lPrint(currentStateStr)
        #set the device shadow for test
        shadowName = str(nodeId)
        thingName = 'mcc-thing-ver01-1'
        newStr = '{"state": {"desired": '+currentStateStr+',"reported": '+currentStateStr+'}}'

        lPrint(newStr)
        #newState = json.loads(newStr)
        #sample_update_thing_shadow_request(thingName, shadowName, bytes(json.dumps(newState), "utf-8"))
        sample_update_thing_shadow_request(thingName, shadowName, bytes(newStr, "utf-8"))

        resp["response"] = "commissioned"
        resp["return_code"] = 200
        resp["txid"] = message_from_core["txid"]

        #set up subscription of device shadow update deltas
        subscribeShadowDeltaTopic = "$aws/things/mcc-thing-ver01-1/shadow/name/"+str(nodeId)+"/update/delta"
        lPrint("Setting up the Shadow Subscription")
        # Setup the Shadow Subscription
        request = SubscribeToTopicRequest()
        request.topic = subscribeShadowDeltaTopic 
        handler = SubHandler()
        operation = ipc_client.new_subscribe_to_topic(handler) 
        future = operation.activate(request)
        future.result(TIMEOUT)
        subscribeToTopic(subscribeShadowDeltaTopic, handler)

    elif command == "discover":
        discoveredCommissionableNodes = matterDevices.discoverCommissionableDevices()
        commissionableNodesJsonStr = matterDevices.jsonDumps(discoveredCommissionableNodes)
        lPrint(commissionableNodesJsonStr)
        if not LOCAL_TEST:
            #set the device shadow for test
            shadowName = "commissionableNodes"
            thingName = 'mcc-thing-ver01-1'
            newStr = '{"state":{"desired":{"nodes":'+commissionableNodesJsonStr+'},"reported":{"nodes":'+commissionableNodesJsonStr+'}}}'
            #newStr = '{"state":{"desired":{"welcome":"aws-iot","status":"good"},"reported":{"welcome":"aws-iot","status":"good"}}}'
            lPrint(newStr)
            #newState = json.loads(newStr)
            #sample_update_thing_shadow_request(thingName, shadowName, bytes(json.dumps(newState), "utf-8"))
            sample_update_thing_shadow_request(thingName, shadowName, bytes(newStr, "utf-8"))
        else:
            pass
        resp["response"] = "discovery complete"
        resp["return_code"] = 200
        resp["txid"] = message_from_core["txid"]

    elif command == "on":
        id = message_from_core["id"]
        nodeId = int(id)
        matterDevices.devOn(nodeId)
        resp["response"] = "turned on"
        resp["return_code"] = 200
        resp["txid"] = message_from_core["txid"]
    elif command == "off":
        id = message_from_core["id"]
        nodeId = int(id)
        matterDevices.devOff(nodeId)
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

            lPrint("Handler for subscription callback")

            try:
                message_string = str(event.binary_message.message, "utf-8")
                lPrint(message_string)
                # Load message and check values
                jsonmsg = json.loads(message_string)

                lPrint(jsonmsg)

                #if onoff is equal to true/1 then turn on else off
                if jsonmsg['state']['1']['chip.clusters.Objects.OnOff']['chip.clusters.Objects.OnOff.Attributes.OnOff']:
                    lPrint("true turn on")
                    #set current status to bad and update actual value of led output to reported
                    matterDevices.devOn(1)
                else:
                    lPrint("false turn off")
                    #set current status to good and update actual value of led output to reported
                    matterDevices.devOff(1)

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

def exitGracefully():
    # To stop subscribing, close the operation stream.
    if not LOCAL_TEST:
        operation.close()
    lPrint("exiting gracefully")

def subscribeToTopic(topic, handler):
    global operation
    lPrint("Setting up the MQTT Subscription")
    # Setup the MQTT Subscription
    qos = QOS.AT_MOST_ONCE
    request = SubscribeToIoTCoreRequest()
    request.topic_name = topic
    request.qos = qos
    operation = ipc_client.new_subscribe_to_iot_core(handler)
    future = operation.activate(request)
    future.result(TIMEOUT)

def main():
    #global operation2
    global matterDevices

    if not LOCAL_TEST:
        lPrint("Setting up the MQTT Subscription")
        # Setup the MQTT Subscription
        handler = StreamHandler()
        subscribeToTopic(REQUEST_TOPIC, handler)

    lPrint('------------------------run-------------------')
    load_environ()

    topic = '{}/{}'.format(_topic, _thing_name)

    #Setting up the chip repl
    console = Console()
    console.print("Current Working Directory " , os.getcwd())

    matterDevices = iotMatterDeviceController.MatterDeviceController(args)

    if CLEAN:
        matterDevices.cleanStart()

    #make sure we are in correct working directory (so relative paths to certs work)
    os.chdir(workingDir)

    lPrint("Current Working Directory " + os.getcwd())
    matterDevices.MatterInit(args, False)

    if not CLEAN:
        #Discover commissioned devices
        lPrint("Discovering commissioned devices - please wait. May take a while......")
        print(matterDevices.discoverFabricDevices())
        lPrint("Finished Discovering commissioned devices")

    # Keep the main thread alive, or the process will exit.
    x=1

    while True:
        lPrint(x)
        x += 1

        if LOCAL_TEST: # if local testing we will use a file for commissioning
            pollForCommand(_sample_file_name)

        # poll every sleep_time_in_sec for latest device state
        pollForDeviceReports()

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
