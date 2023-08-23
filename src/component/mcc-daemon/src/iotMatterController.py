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

parser = argparse.ArgumentParser()
parser.add_argument("-n", "--name", help="Name of the IOT thing (default: mcc-thing-ver01-1)", action="store", default="mcc-thing-ver01-1")
parser.add_argument("-t", "--test", help="true if testing local", action="store", default="False")
parser.add_argument("-m", "--maxdevices", help="number of matter devices", action="store", default=10)
parser.add_argument("-e", "--maxevents", help="number of matter events logged per device", action="store", default=10)
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

curr_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(curr_dir)

sleep_time_in_sec = float(os.environ.get('SLEEP_TIME', '0.1'))
stabilisation_time_in_sec = int(os.environ.get('STABLE_TIME', '10'))

RESPONSE_FORMAT = "json"
TIMEOUT = 10
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
                    #lPrint("Result:", message_respone["result"])
                    #lPrint(message_respone["result"])
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

        lPrint('message from rest api {}: '.format(message_from_rest))

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
    controller_name = request.match_info['name'] 

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
                nodes = []
                #We are looking for the result
                if "result" in message_respone:
                    for node in message_respone["result"]:
                        nodes.append(node["node_id"])
                    await session.close()
                    return web.json_response(nodes)
                    break
                    

            if msg.type in (aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR):
                resp["response"] = "SERVER ERROR"
                resp["return_code"] = 500

    response_message = {
        "message": "ListNamedShadowsForThing",
        "response": resp["response"],
        "return_code": resp["return_code"]
        }
    await session.close()
    return web.json_response(response_message)


@routes.get('/shadow/{name}/{node}')
async def return_node(request):
    controller_name = request.match_info['name'] 
    node_id = int(request.match_info['node']) 

    resp = {}
    resp["response"] = "OK"
    resp["return_code"] = 200
    messageObject = {
        "message_id": "2",
        "command": "get_node",
        "args": {
            "node_id": node_id
        }
    }


    session = aiohttp.ClientSession()
    async with session.ws_connect(URL) as ws:

        await ws.send_json(messageObject)

        async for msg in ws:
            if msg.type in (aiohttp.WSMsgType.TEXT, aiohttp.WSMsgType.BINARY):
                message_respone = json.loads(msg.data)
                nodes = []
                #We are looking for the result
                if "result" in message_respone:
                    #lPrint("Result:", message_respone["result"])
                    #lPrint(message_respone["result"])
                    await session.close()
                    return web.json_response(message_respone["result"])
                    break
                    

            if msg.type in (aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR):
                resp["response"] = "SERVER ERROR"
                resp["return_code"] = 500

    response_message = {
        "message": "shadow",
        "response": resp["response"],
        "return_code": resp["return_code"]
        }
    await session.close()
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
    lPrint(command)

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
        loop = None
        def __init__(self, loop):
            self.loop = loop
            super().__init__()

        def on_stream_event(self, event: IoTCoreMessage) -> None:
            lPrint("on_stream_event")
            lPrint(event)
            try:
                # Handle message.
                respond(event, self.loop)
            except:
                traceback.print_exc()

        def on_stream_error(self, error: Exception) -> bool:
            # Handle error.
            lPrint("on_stream_error")
            return True  # Return True to close stream, False to keep stream open.

        def on_stream_closed(self) -> None:
            # Handle close.
            pass

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

#Get the shadow from the local IPC
def get_thing_shadow_request(thingName, shadowName):
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
def update_thing_shadow_request(thingName, shadowName, payload):
    lPrint("in update_thing_shadow_request")
    lPrint(payload)
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
    lPrint("thingName: "+ str(thingName))

    #Here we are going to create multiple shadows - per nodeid/endpointid 
    for endpoint in findEndpointsPerNode(nodeResult):
        filteredNodeResult = filterNodesByEndpoint(nodeResult, endpoint)
            
        #set the device shadow for test
        shadowName = str(nodeId) + "_" + str(endpoint)
        lPrint("shadowName: " + str(nodeId))

        newStr = '{"state": {"reported": '+json.dumps(filteredNodeResult)+'}}'

        lPrint("Updating Thing Shadow Now.......")

        lPrint("thingName:")
        lPrint(thingName)

        lPrint("shadowName:")
        lPrint(shadowName)

#        lPrint("document:")
#        lPrint(bytes(newStr, "utf-8"))

        if not LOCAL_TEST:
            update_thing_shadow_request(thingName, shadowName, bytes(newStr, "utf-8"))


def OnEventChange(nodeId, eventReadResult)-> None:
    lPrint("Saw event change inside Cloud Controller! for nodeId: "+ str(nodeId))
    thingName = args.name 
    lPrint("thingName: "+ str(thingName))

    lPrint("shadowName: " + "events_" + str(nodeId))
    if not LOCAL_TEST:
        shadowName = "events_" + str(nodeId)
        #First read the existing events and then add to it
        lPrint("Calling get thing shadow request for events")

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

        
async def mainLoopTask(ws:ClientWebSocketResponse):
    loop = asyncio.get_running_loop()
    running = True
    
    if not LOCAL_TEST:
        lPrint("Setting up the MQTT Subscription")
        # Get the current running loop
        loop = asyncio.get_event_loop()
        # Setup the MQTT Subscription
        handler = StreamHandler(loop)
        subscribeToTopic(REQUEST_TOPIC, handler)

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
            #lPrint(msg.data)

            if msg.type == aiohttp.WSMsgType.TEXT:
                message_response = msg.json()
                #lPrint('Message received from server:')
                #lPrint(json.dumps(message_response))

                # Here we will look for the type of message (event,message response or start up message)
            
                # Look for start up message like this 
                # {"fabric_id": 1, "compressed_fabric_id": 7869426522387137316, 
                # "schema_version": 4, "min_supported_schema_version": 2, "sdk_version": "0.0.0", 
                # "wifi_credentials_set": false, "thread_credentials_set": false}
                if "fabric_id" in message_response:
                    print("compressed_fabric_id:", message_response["compressed_fabric_id"])

                elif "message_id" in message_response:
                    lPrint("message_id:" + message_response["message_id"])
                    #check that we have results before processing them
                    if (not isinstance(message_response["result"], type(None))):
                        results = message_response["result"]

                        #Check if the results are for a single node (dict) or
                        #list of nodes (array)
                        if isinstance(results, dict):
                            #if we got a single then go here
                            print("Message Response with single node update")
                            node_id = results["node_id"]
                            print("node_id:", node_id)
                            OnNodeChange(node_id, results)
                        else:
                            #if we got a list of nodes we go here
                            for result in results:
                                if "node_id" in result:
                                    #Here we are dealing with an update on all the node
                                    print("Message Response with nodes update")
                                    node_id = result["node_id"]
                                    print("node_id:", node_id)
                                    OnNodeChange(node_id, result)
                                if "Path" in result:
                                    #Here we are dealing with an update on all the node
                                    print("Message Response with path attribute updates")

                elif "event" in message_response:
                    print("event:", message_response)
                    if (message_response["event"] == 'node_added' 
                        or message_response["event"] == 'node_updated'
                        or message_response["event"] == 'node_removed'
                        or message_response["event"] == 'node_event'):
                        node_id = message_response["data"]['node_id']
                        message_response.pop('data') #Get rid of the data as its too big for events
                    else:    
                        node_id = message_response["data"][0]
                        #await updateNode(node_id)
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
        # check for stop signal
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
                    await main()
        
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

