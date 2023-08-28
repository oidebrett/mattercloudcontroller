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

"""
To Run Locally:
python3 ../Projects/mattercloudcontroller/src/component/mcc-daemon/src/iotMatterCloudController.py -t True -d /home/ivob/connectedhomeip

Listen for incoming chip requests and publish the results onto response topic
--request-topic - defaults to chip/request
--response-topic - defaults to chip/response

Command message structure (JSON):
{
    "message_id": "1",
    "command": "commission_on_network",
    "args": {
        "setup_pin_code": 20202021
    }
}
- `command` - full string to pass to chip
- `id` - is the IP address when commissioning and the node id when sending a command
- `message_id` - unique id to track status of message, returned as part of response.

Note: New commands cannot use the id of any in-flight operations that have not completed.
- Total payload size must be less than 128KiB in size, including request topic.
- Command will run as default ggc_user unless changed in the recipe file
Response message structure (JSON):
{
    "message_id": "12345ABC",
    "return_code": 0,
    "response": "total 17688\n-rw-r--r--   1 ggc_user  staff     8939 Apr 30 16:37 README.md\n"
}
- If response is greater than 128KiB, exit_code will be set to 255 and "payload too long" response.
- Malformed request with set exit_code  to 255 and "malformed request/missing transaction id/etc" response.
"""

import argparse
import logging
import os
import sys
import time
import datetime
import subprocess
import json
import traceback
from rich.console import Console
import asyncio
import aiohttp
from aiohttp import web, ClientWebSocketResponse
import json
from concurrent.futures import ThreadPoolExecutor
from asyncioUtils import MemQueue, TestFileHandler, CancellableSleeps
import random

parser = argparse.ArgumentParser()
parser.add_argument("-n", "--name", help="Name of the IOT thing (default: mcc-thing-ver01-1)", action="store", default="mcc-thing-ver01-1")
parser.add_argument("-t", "--test", help="true if testing local", action="store", default="False")
parser.add_argument("-m", "--maxdevices", help="number of matter devices", action="store", default=100)
parser.add_argument("-e", "--maxevents", help="number of matter events logged per device", action="store", default=100)
parser.add_argument("-c", "--clean", help="true to clean working directory", action="store", default="False")
parser.add_argument("-s", "--stop", help="true to stop at first resolve fail", action="store", default="False")

#Set up the variables from the arguments (and defaults)
args = parser.parse_args()
LOCAL_TEST_ARG = args.test
LOCAL_TEST = LOCAL_TEST_ARG.lower() == 'true'
CLEAN_ARG = args.clean
CLEAN = CLEAN_ARG.lower() == 'true'
STOP_ARG = args.stop
STOP = STOP_ARG.lower() == 'true'
MAX_EVENTS = args.maxevents
THING_NAME = args.name

#Set up the Websocket client details
HOST='127.0.0.1' 
PORT=5580
URL = f'http://{HOST}:{PORT}/ws'

# create the shared queue for sharing inbound messages between webserver and websocket queues
# queue of 5 MiB max, and 1000 items max
queue = MemQueue(maxsize=1000, maxmemsize=5*1024*1024)
routes = web.RouteTableDef()
sleeps = CancellableSleeps()
shadow_subscriptions = []

curr_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(curr_dir)

sleep_time_in_sec = float(os.environ.get('SLEEP_TIME', '0.1'))
stabilisation_time_in_sec = int(os.environ.get('STABLE_TIME', '10'))

RESPONSE_FORMAT = "json"
TIMEOUT = 5
MSG_TIMEOUT = f"Command timed out, limit of {TIMEOUT} seconds"
MSG_MISSING_ATTRIBUTE = "The attributes 'message_id' and/or 'command' missing from request"
MSG_INVALID_JSON = "Request message was not a valid JSON object"

# Set up request topic and response topic from passed in arguments
REQUEST_TOPIC = "chip/request"
RESPONSE_TOPIC = "chip/response"

def lPrint(msg):
    console = Console()
    console.print(msg)
    logging.info(msg)
    print(msg, file=sys.stdout)
    sys.stderr.flush()

if not LOCAL_TEST:
    #Set up the IoT communication to AWS IoT Core
    import awsiot.greengrasscoreipc
    import awsiot.greengrasscoreipc.client as client
    from awsiot.greengrasscoreipc.clientv2 import GreengrassCoreIPCClientV2

    from awsiot.greengrasscoreipc.model import (
        IoTCoreMessage,
        QOS,
        SubscribeToIoTCoreRequest,
        PublishToIoTCoreRequest,
        SubscribeToTopicRequest,
        SubscriptionResponseMessage,
        ListNamedShadowsForThingRequest,
        GetThingShadowRequest,
        UpdateThingShadowRequest,
        DeleteThingShadowRequest,
        InvalidArgumentsError,
        ResourceNotFoundError,
        ServiceError,
        ConflictError,
        UnauthorizedError
    )

    lPrint("not LOCAL_TEST")
    ipc_client = awsiot.greengrasscoreipc.connect()
else:
    lPrint("is LOCAL_TEST")
    _sample_file_name = 'sample_data.json'




#######################################################################################
##
## The following are the HTTP Rest API end points
##
#######################################################################################
@routes.get('/nodes')
async def return_nodes(request):
    resp = {}
    resp["response"] = "OK"
    resp["return_code"] = 200
    messageObject = {
            "message_id": "5",
            "command": "get_nodes"
        }

    session = aiohttp.ClientSession()
    async with session.ws_connect(URL) as ws:

        await ws.send_json(messageObject)

        async for msg in ws:
            if msg.type in (aiohttp.WSMsgType.TEXT, aiohttp.WSMsgType.BINARY):
                message_respone = json.loads(msg.data)
                #We are looking for the result
                if "result" in message_respone:
                    await session.close()
                    return web.json_response(message_respone["result"])
                    break
                    

            if msg.type in (aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR):
                resp["response"] = "SERVER ERROR"
                resp["return_code"] = 500

    response_message = {
        "message": "nodes",
        "response": resp["response"],
        "return_code": resp["return_code"]
        }
    await session.close()
    return web.json_response(response_message)


#Respond to a http REST message
@routes.get('/chip-request')
async def return_command(request):
    json_str = request.rel_url.query.get('json', '')

    resp = {}
    resp["return_code"] = 200
    resp["response"] = ""
    response_format = RESPONSE_FORMAT
    operation_timeout = TIMEOUT

    # validate message and attributes
    try:
        message_from_rest = json.loads(json_str)

        # Verify required keys are provided
        if not all(k in message_from_rest for k in ("message_id", "command")):
            resp["response"] = MSG_MISSING_ATTRIBUTE
            resp["return_code"] = 255
            response_message = {
                "message": str(json_str),
                "response": resp["response"],
                "return_code": resp["return_code"]
                }
            lPrint(f"{MSG_MISSING_ATTRIBUTE} for message")
            return web.json_response(response_message)
        
    except json.JSONDecodeError as e:
        resp["response"] = MSG_INVALID_JSON
        resp["return_code"] = 255
        response_message = {
            "timestamp": int(round(time.time() * 1000)),
            "message": str(json_str),
            "response": resp["response"],
            "return_code": resp["return_code"]
            }
        lPrint(f"{MSG_INVALID_JSON} for message")
        return web.json_response(response_message)
    except Exception as e:
        raise
    
    command = message_from_rest["command"]
    command = command.lstrip()

    nodeId = None
    resp["response"] = "accepted"
    resp["return_code"] = 200
    resp["message_id"] = message_from_rest["message_id"]

    # add to the queue
    await queue.put(json_str)

    # Dummy response message
    response_message = {
        "timestamp": int(round(time.time() * 1000)),
        "message": str(json_str),
        "message_id": str(resp["message_id"]),
        "response": resp["response"],
        "return_code": resp["return_code"]
        }

    return web.json_response(response_message)


@routes.get('/api/things/shadow/ListNamedShadowsForThing/{name}')
async def return_node(request):
    thingName = request.match_info['name'] 

    resp = {}
    resp["response"] = "OK"
    resp["return_code"] = 200

    shadow_list = []
    next_token = None

    named_shadow_list, next_token, timestamp = list_named_shadows_request(thingName, next_token)
    shadow_list.extend(named_shadow_list)

    while next_token != None:
        named_shadow_list, next_token, timestamp = list_named_shadows_request(thingName, next_token)
        shadow_list.extend(named_shadow_list)

    result = {
        "results": shadow_list,
        "timestamp": time.time()
    }

    return web.json_response(result)



@routes.get('/shadow/{name}/{shadow}')
async def return_named_shadow(request):
    thingName = request.match_info['name'] 
    shadowName = request.match_info['shadow'] 

    response_message = get_thing_shadow_request(thingName, shadowName)
    resp = {}
    resp["response"] = "OK"
    resp["return_code"] = 200

    response = json.loads(response_message)
    return web.json_response(response)

@routes.get('/deleteshadow/{name}/{shadow}')
async def return_named_shadow(request):
    thingName = request.match_info['name'] 
    shadowName = request.match_info['shadow'] 

    response_message = delete_named_shadow_request(thingName, shadowName)
    resp = {}
    resp["response"] = "OK"
    resp["return_code"] = 200

    response_message = {
        "message": "DeleteNamedShadowForThing",
        "response": resp["response"],
        "return_code": resp["return_code"]
        }
    return web.json_response(response_message)

#######################################################################################
##
## The following are the MQTT handlers end points
##
#######################################################################################

#Respond to a MQTT message
def respond(event, loop):
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
        if not all(k in message_from_core for k in ("message_id", "command")):
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
            return
        

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
        lPrint(f"{MSG_INVALID_JSON} for message")
        return
    except Exception as e:
        raise
    
    command = message_from_core["command"]
    command = command.lstrip()

    nodeId = None
    resp["response"] = "accepted"
    resp["return_code"] = 200
    resp["message_id"] = message_from_core["message_id"]

    # add to the queue
    messageObject = json.dumps(message_from_core)
    loop.create_task(queue.put(messageObject))

    # Dummy response message
    response_message = {
        "timestamp": int(round(time.time() * 1000)),
        "message": str(event.message.payload),
        "message_id": str(resp["message_id"]),
        "response": resp["response"],
        "return_code": resp["return_code"]
        }

    # Print the message to stdout, which Greengrass saves in a log file.
    #lPrint("event.message.payload:" + str(event.message.payload))

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
        loop = None
        def __init__(self, loop):
            self.loop = loop
            super().__init__()

        def on_stream_event(self, event: IoTCoreMessage) -> None:
            try:
                # Handle message.
                respond(event, self.loop)
                return True
            except:
                traceback.print_exc()

        def on_stream_error(self, error: Exception) -> bool:
            # Handle error.
            return True  # Return True to close stream, False to keep stream open.

        def on_stream_closed(self) -> None:
            # Handle close.
            pass

    #Handler for subscription callback
    class SubHandler(client.SubscribeToTopicStreamHandler):
        loop = None
        shadow = None
        def __init__(self, shadow, loop):
            self.loop = loop
            self.shadow = shadow
            super().__init__()

        def on_stream_event(self, event: IoTCoreMessage) -> None:  

            lPrint("Handler for subscription callback for " + self.shadow)
            lPrint(event)

            current_shadow = json.loads(get_thing_shadow_request(THING_NAME, self.shadow))

            try:
                if (isinstance(event, IoTCoreMessage)):
                    message = str(event.message.payload, 'utf-8')
                elif (isinstance(event, SubscriptionResponseMessage)):
                    message = str(event.binary_message.message, 'utf-8')
                else:
                    return True
                
                # Load message and check values
                jsonmsg = json.loads(message)

                stateChanges = jsonmsg['state']
                for iterator in stateChanges:

                    #If we have already changed then do nothing
                    reportedStates= current_shadow["state"]["reported"]
                    if reportedStates[iterator] == stateChanges[iterator]:
                        break

                    tempNodeId = int(self.shadow.split('_')[0])
                    tempEndpoint = int(iterator.split('/')[0])
                    randMessageId = str(random.randint(1, 9999999) )
                    lPrint(iterator + ":" + str(stateChanges[iterator]))

                    # add to the queue
                    lPrint("adding messageObject to queue")
                    messageObject = {
                                    "message_id": randMessageId, 
                                    "command": "write_attribute", 
                                    "args": {"endpoint_id": tempEndpoint, 
                                            "node_id": tempNodeId, 
                                            "attribute_path": iterator, 
                                            "value": stateChanges[iterator]
                                            }
                                    }
                    messageObjectStr = json.dumps(messageObject)
                    lPrint(messageObjectStr)

                    self.loop.create_task(queue.put(messageObjectStr))
                    self.loop.create_task(asyncio.sleep(0.1))

                return True

            except:
                traceback.print_exc()

        def on_stream_error(self, error: Exception) -> bool:
            # Handle error.
            return True  # Return True to close stream, False to keep stream open.

        def on_stream_closed(self) -> None:
            # Handle close.
            pass

def subscribeToTopic(topic, handler):
    global operation
    lPrint("Setting up the MQTT Subscription to subscribe to topic")
    # Setup the MQTT Subscription
    qos = QOS.AT_MOST_ONCE
    request = SubscribeToIoTCoreRequest()
    request.topic_name = topic
    request.qos = qos
    operation = ipc_client.new_subscribe_to_iot_core(handler)
    future = operation.activate(request)
    future.result(TIMEOUT)

#Get the shadow from the local IPC
def get_thing_shadow_request(thingName, shadowName):
    lPrint("getting_thing_shadow_request: "+shadowName)

    try:
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
        return []
        # except ResourceNotFoundError | UnauthorizedError | ServiceError

#Set the local shadow using the IPC
def update_thing_shadow_request(thingName, shadowName, payload):
    lPrint("in update_thing_shadow_request")
    #lPrint(payload)
    try:
        # set up IPC client to connect to the IPC server
        client = GreengrassCoreIPCClientV2()
        result = client.update_thing_shadow(thing_name=thingName, payload=payload, shadow_name=shadowName)
        return result.payload
    except ConflictError as e:
        lPrint("ConflictError: Error update shadow")
        traceback.print_exc()
    except UnauthorizedError as e:
        lPrint("UnauthorizedError: Error update shadow")
        traceback.print_exc()
    except ServiceError as e:
        lPrint("ServiceError: Error update shadow")
        traceback.print_exc()
    except InvalidArgumentsError as e:
        lPrint(e)
        lPrint("InvalidArgumentsError: Error update shadow")
        traceback.print_exc()
    except Exception as e:
        lPrint("Error update shadow")
        traceback.print_exc()

#Get the shadow from the local IPC
def list_named_shadows_request(thingName, nextToken):
    lPrint("list_named_shadows_request: "+thingName)

    try:
        # set up IPC client to connect to the IPC server
        ipc_client = awsiot.greengrasscoreipc.connect()
                            
        lPrint("Creating the ListNamedShadowsForThing request")
        # create the ListNamedShadowsForThingRequest request
        list_named_shadows_for_thing_request = ListNamedShadowsForThingRequest()
        list_named_shadows_for_thing_request.thing_name = thingName
        list_named_shadows_for_thing_request.next_token = nextToken
        #list_named_shadows_for_thing_request.page_size = 10

        lPrint("Retrieving the ListNamedShadowsForThing response")
        # retrieve the ListNamedShadowsForThingRequest response after sending the request to the IPC server
        op = ipc_client.new_list_named_shadows_for_thing()

        lPrint(op)

        lPrint("Activating the ListNamedShadowsForThing response")
        op.activate(list_named_shadows_for_thing_request)
        fut = op.get_response()
                
        list_result = fut.result(TIMEOUT)
        
        # additional returned fields
        timestamp = list_result.timestamp
        next_token = list_result.next_token
        named_shadow_list = list_result.results
        
        #return named_shadow_list
        return named_shadow_list, next_token, timestamp
        
    except Exception as e:
        lPrint("Error listing named shadows")
        return []
        # except ResourceNotFoundError | UnauthorizedError | ServiceError

#Get the shadow from the local IPC
def delete_named_shadow_request(thingName, shadowName):
    lPrint("delete_named_shadow_request - thingName: "+thingName)
    lPrint("delete_named_shadow_request - shadowName: "+shadowName)

    try:
        # set up IPC client to connect to the IPC server
        ipc_client = awsiot.greengrasscoreipc.connect()
                            
        # create the DeleteThingShadowRequest request
        delete_named_shadow_for_thing_request = DeleteThingShadowRequest()
        delete_named_shadow_for_thing_request.thing_name = thingName
        delete_named_shadow_for_thing_request.shadow_name = shadowName

        # retrieve the DeleteThingShadowRequest response after sending the request to the IPC server

        op = ipc_client.new_delete_thing_shadow()
        lPrint(op)

        lPrint("Activating the DeleteThingShadowRequest response")

        op.activate(delete_named_shadow_for_thing_request)
        fut = op.get_response()
                
        lPrint(fut)
        result = fut.result(TIMEOUT)
        lPrint("result")
        lPrint(result)
        
        return result.payload
        
    except Exception as e:
        lPrint("Error deleting named shadow")
        return []
        # except ResourceNotFoundError | UnauthorizedError | ServiceError

def depth(x):
    if type(x) is dict and x:
        return 1 + max(depth(x[a]) for a in x)
    if type(x) is list and x:
        return 1 + max(depth(a) for a in x)
    return 0

def findEndpointsPerNode(nodeResult):
    endpoints = []
    for iterator in nodeResult["attributes"]:
        tempEndpoint = int(iterator.split('/')[0])
        if tempEndpoint not in endpoints:
            endpoints.append(tempEndpoint) # add this attribute to the new sttribute dict
        
    return endpoints

def filterNodesByEndpoint(nodeResult, endpointId):
    filteredResults = nodeResult.copy()
    attributes = {}
    for iterator in filteredResults["attributes"]:
        if iterator.startswith(f"{endpointId}/"):
            attributes[iterator] = filteredResults["attributes"][iterator] # add this attribute to the new sttribute dict
            
    filteredResults["attributes"] = attributes
#    filteredResults["attributes"] = {}
#    return filteredResults
    return attributes

def OnNodeChange(nodeId, nodeResult)-> None:
    lPrint("Saw node change inside Cloud Controller! for nodeId: "+ str(nodeId))
    thingName = args.name 

    #Here we are going to create multiple shadows - per nodeid/endpointid 
    for endpoint in findEndpointsPerNode(nodeResult):
        filteredNodeResult = filterNodesByEndpoint(nodeResult, endpoint)
            
        #set the device shadow for test
        shadowName = str(nodeId) + "_" + str(endpoint)

        newStr = '{"state": {"reported": '+json.dumps(filteredNodeResult)+'}}'

        if not LOCAL_TEST:
            update_thing_shadow_request(thingName, shadowName, bytes(newStr, "utf-8"))

    if not LOCAL_TEST:
        #now that we have created/updated new shadows 
        #we need to subscrive to any deltas
        subscribe_to_shadow_deltas(thingName)
        pass

def OnEventChange(nodeId, eventReadResult)-> None:
    lPrint("Saw event change inside Cloud Controller! for nodeId: "+ str(nodeId))
    thingName = args.name 

    if not LOCAL_TEST:
        shadowName = "events_" + str(nodeId)
        #First read the existing events and then add to it

        #If we get an Exception its because we dont have an event list already
        newList = []
        try:
            response = get_thing_shadow_request(thingName, shadowName)

            prevEvents = json.loads(response)
            
            #Append a new event to the event List - this will push out oldest if full
            if len(prevEvents['state']['reported']['list']) > MAX_EVENTS:
                newList = prevEvents['state']['reported']['list'][1:]
            else:
                newList = prevEvents['state']['reported']['list']

        except:
            prevEvents = {"state": None}
            prevEvents["state"] = {"reported": None}
            prevEvents["state"]["reported"] = {"list": []}

        newList.append(eventReadResult)
        prevEvents['state']['reported']['list'] = newList

        newStr = json.dumps(prevEvents)

        #Calling update thing shadow request for events
        result = update_thing_shadow_request(thingName, shadowName, bytes(newStr, "utf-8"))

def subscribe_to_shadow_deltas(thing_name):
    shadow_list = []
    named_shadow_list, next_token, timestamp = list_named_shadows_request(thing_name, None)
    shadow_list.extend(named_shadow_list)
    while next_token != None:
        named_shadow_list, next_token, timestamp = list_named_shadows_request(thing_name, next_token)
        shadow_list.extend(named_shadow_list)

    # set up IPC client to connect to the IPC server
    ipc_client = awsiot.greengrasscoreipc.connect()

    #Now subscribe to the deltas for every shadow 
    for shadow in named_shadow_list:

        if shadow not in shadow_subscriptions:
            #set up subscription of device shadow update deltas
            subscribeShadowDeltaTopic = "$aws/things/"+thing_name+"/shadow/name/"+shadow+"/update/delta"

            #We dont need to subscribe on the subscription as we now use interactions to change
            #But we will leave this here in case we want to do something when the shadow changes
            lPrint("Setting up the Shadow Subscription for: " + shadow)
            # Setup the Shadow Subscription
            request = SubscribeToTopicRequest()
            request.topic = subscribeShadowDeltaTopic 
            loop = asyncio.get_event_loop()
            # Setup the MQTT Subscription
            handler = SubHandler(shadow, loop)
            operation = ipc_client.new_subscribe_to_topic(handler)
        
            future = operation.activate(request)
            future.result(TIMEOUT)
            subscribeToTopic(subscribeShadowDeltaTopic, handler)

            #We will keep track of the subscriptions that we have created
            #so that we dont recreate them
            shadow_subscriptions.append(shadow)


def delete_all_shadows(thing_name):
    shadow_list = []
    named_shadow_list, next_token, timestamp = list_named_shadows_request(thing_name, None)
    shadow_list.extend(named_shadow_list)
    while next_token != None:
        named_shadow_list, next_token, timestamp = list_named_shadows_request(thing_name, next_token)
        shadow_list.extend(named_shadow_list)

    #Now subscribe to the deltas for every shadow 
    for shadow in named_shadow_list:
        #delete all shadows
        delete_named_shadow_request(thing_name, shadow)


async def mainLoopTask(ws:ClientWebSocketResponse):
    loop = asyncio.get_running_loop()
    running = True
    
    if not LOCAL_TEST:
        lPrint("Setting up the MQTT Subscription for MQTT stream")
        # Get the current running loop
        loop = asyncio.get_event_loop()
        # Setup the MQTT Subscription
        handler = StreamHandler(loop)
        subscribeToTopic(REQUEST_TOPIC, handler)

        #Remove all the named shadows at start up
        #If nodes exists they will be repopulated
        if CLEAN:
            delete_all_shadows(THING_NAME)
            shadow_subscriptions = []

    lPrint('------------------------run-------------------')

    lPrint("LOCAL_TEST: "+str(LOCAL_TEST))
    lPrint("CLEAN: "+str(CLEAN))
    lPrint("STOP: "+str(STOP))

    lPrint("Current Working Directory " + os.getcwd())

    while running:
        if LOCAL_TEST: # if local testing we will use a file for commissioning
            fh = TestFileHandler()
            await fh.pollForCommand(curr_dir + '/' + _sample_file_name, ws, queue)

        await asyncio.sleep(sleep_time_in_sec)

async def websocketListenTask(ws):
    try:
        await ws.send_str('{"message_id": "3","command": "start_listening"}')
    except:
        print("Connect Listening Set Up Error")


    try:
        async for msg in ws:

            if msg.type == aiohttp.WSMsgType.TEXT:
                message_response = msg.json()
                # Here we will look for the type of message (event,message response or start up message)
            
                # Look for start up message like this 
                # {"fabric_id": 1, "compressed_fabric_id": 7869426522387137316, 
                # "schema_version": 4, "min_supported_schema_version": 2, "sdk_version": "0.0.0", 
                # "wifi_credentials_set": false, "thread_credentials_set": false}
                if "fabric_id" in message_response:
                    print("compressed_fabric_id:", message_response["compressed_fabric_id"])

                elif "error_code" in message_response:
                    lPrint(message_response["details"])
                
                elif "message_id" in message_response:
                    #when we get a message_id it could be 1 of 3 things:
                    #1. If could be a simple acknowledge of a message request with no results (type None)
                    #2. It could be a response giving the latest attributes for a single node (results is a dict not a list)
                    #3. It could be a response giving the latest attributes for all nodes (results is a list)
                    #4. Finally it could be a result from a command that is return results non related to nodes such as a open commissioning window request
                    lPrint("message_id:" + message_response["message_id"])

                    #check that we have results before processing them
                    if (not isinstance(message_response["result"], type(None))):
                        results = message_response["result"]

                        #Check if the results are for a single node (dict) or
                        #list of nodes (array)
                        if isinstance(results, dict):
                            #if we got a single then go here
                            lPrint("Message Response with single node update")
                            #Update the node shadows
                            OnNodeChange(results["node_id"], results)
                        else:
                            #if we got a list of nodes we go here
                            for result in results:
                                if isinstance(result, dict):
                                    if "node_id" in result:
                                        #Here we are dealing with an update on all the node
                                        lPrint("Message Response with nodes update")
                                        
                                        #Update the node shadows
                                        OnNodeChange(result["node_id"], result)
                                    elif "Path" in result:
                                        #Here we are dealing with an update on all the node
                                        lPrint("Message Response with path attribute updates")
                                        pass
                                else:
                                    #Here we are dealing with a response such as opening commission
                                    lPrint("Message Response with other result")
                                    pass

                elif "event" in message_response:
                    print("event:", message_response)
                    if (message_response["event"] == 'node_added' 
                        or message_response["event"] == 'node_updated'
                        or message_response["event"] == 'node_removed'
                        or message_response["event"] == 'node_event'):
                        node_id = message_response["data"]['node_id']
                        #if len (message_response["data"])>500:
                        message_response.pop('data') #Get rid of the data as its too big for events shadow
                    else:
                        #This is an attribute change event so we will force
                        #an update of the node shadows by calling get_nodes
                        #which will force the node shadows to be updated when 
                        #the response is received back
                        node_id = message_response["data"][0]
                        messageObject = {
                            "message_id": "2",
                            "command": "get_node",
                            "args": {
                                "node_id": node_id
                            }
                        }
                        # add to the queue
                        await queue.put(json.dumps(messageObject))
                        await asyncio.sleep(sleep_time_in_sec)
                    OnEventChange(node_id, message_response)

                else:
                    print("*****************Unknown/Unhandled message:", message_response)
                    pass
    except:
        print("Connection is Closed")
        await ws.close()

    finally:
        pass

async def close(ws):
    await ws.close()


async def queueListenTask(ws):
    lPrint('queueListen: Running')

    # consume work
    while True:
        # get a unit of work
        Item_size, item = await queue.get()
        if item is None:
            break
        # report
        try:
            await ws.send_str(item)
        except:
            lPrint("Caught an exception sending item and now exiting:" + item)
            #sys.exit(0)
    
    # all done
    lPrint('queueListen: Done')


async def initialization():
    app = web.Application()
    app.add_routes(routes)
    return app

async def webserverTask():
    try:
        # set up the local REST API server
        app = await initialization()
        runner = aiohttp.web.AppRunner(app)
        await runner.setup()
        site = aiohttp.web.TCPSite(runner)    
        await site.start()
    finally:
        pass

#This is a callback that is called when the websocket is closed by error
#and this starts a process of reinitializing the websocket as 
# (1) - all outstanding tasks are cancelled
# (2) - this causes a CancellTask exception
# We then restart the main function again
def websocketClosedCB(_fut):
    tasks = [t for t in asyncio.all_tasks() if t is not
            asyncio.current_task()]
    [task.cancel() for task in tasks]

    lPrint(f"Cancelling {len(tasks)} outstanding tasks")
    sleeps.cancel() # cancel all running sleep tasks
                
async def main():
    try:
        # add the websocket client handler to the loop
            
        async with aiohttp.ClientSession().ws_connect(URL) as ws:
            # 1 - the webserver task
            webserver_task = asyncio.create_task(webserverTask())
            # 2 - the websocket listener task
            ws_listen_task = asyncio.create_task(websocketListenTask(ws))
            ws_listen_task.add_done_callback(websocketClosedCB)
            # 3 - the queue listener task
            queue_listen_task = asyncio.create_task(queueListenTask(ws))
            # 4 - the main loop task
            main_loop_task = asyncio.create_task(mainLoopTask(ws))

            tasks = [webserver_task, ws_listen_task, queue_listen_task, main_loop_task]
            try:
                await asyncio.gather(*tasks, return_exceptions=True)

            
            except KeyboardInterrupt as e:
                lPrint("Caught keyboard interrupt. Canceling tasks...")
            except RuntimeError as e:
                lPrint("Caught Runtime Error. Canceling tasks...")
            except ValueError as e:
                lPrint(f"A value error occurred: {str(e)}")
            except Exception as e:
                lPrint(f"Something went wrong: {str(e)}")
            except asyncio.CancelledError as e:
                lPrint(f"Something went wrong with Cancelling: {str(e)}")
                #Close the websocket and restart everything
                session = aiohttp.ClientSession()
                if not session.closed:
                    await session.close()
                    await asyncio.sleep(sleep_time_in_sec)
                    #await main()
        
    except Exception as e:
        lPrint(f"Something went wrong: {str(e)}")



    # wait forever
    await asyncio.Event().wait()
        

def exitGracefully():
    # To stop subscribing, close the operation stream.
    if not LOCAL_TEST:
        operation.close()
    lPrint("exiting gracefully")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        exitGracefully()
        pass

