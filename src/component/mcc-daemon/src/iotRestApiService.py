import aiohttp
from aiohttp import web
import json 
import time


MSG_MISSING_ATTRIBUTE = "The attributes 'message_id' and/or 'command' missing from request"
MSG_INVALID_JSON = "Request message was not a valid JSON object"

class RestHandler():
    routes = web.RouteTableDef()

    def __init__(self):
        pass

    async def initialization(self, queue, url, shadow_functions, message_router):
        app = web.Application()
        app.add_routes(self.routes)
        app['queue'] = queue
        app['url'] = url
        app['shadow_functions'] = shadow_functions
        app['message_router'] = message_router
        
        return app

    #######################################################################################
    ##
    ## The following are the HTTP Rest API end points
    ##
    #######################################################################################
    @routes.get('/nodes')
    async def return_nodes(request):
        url = request.app['url']

        resp = {}
        resp["response"] = "OK"
        resp["return_code"] = 200
        message_object = {
                "message_id": "5",
                "command": "get_nodes"
            }

        session = aiohttp.ClientSession()
        async with session.ws_connect(url) as ws:

            await ws.send_json(message_object)

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
        queue = request.app['queue']
        message_router = request.app['message_router']

        json_str = request.rel_url.query.get('json', '')

        resp = {}
        resp["return_code"] = 200
        resp["response"] = ""

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
                #lPrint(f"{MSG_MISSING_ATTRIBUTE} for message")
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
            #lPrint(f"{MSG_INVALID_JSON} for message")
            return web.json_response(response_message)
        except Exception as e:
            raise
        
        command = message_from_rest["command"]
        command = command.lstrip()

        nodeId = None
        resp["response"] = "accepted"
        resp["return_code"] = 200
        resp["message_id"] = message_from_rest["message_id"]

        message_router(message_from_rest)

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
        list_named_shadows_request = request.app['shadow_functions']['list_named_shadows_request']
        thing_name = request.match_info['name'] 

        resp = {}
        resp["response"] = "OK"
        resp["return_code"] = 200

        shadow_list = []
        next_token = None

        named_shadow_list, next_token, timestamp = list_named_shadows_request(thing_name, next_token)
        shadow_list.extend(named_shadow_list)

        while next_token != None:
            named_shadow_list, next_token, timestamp = list_named_shadows_request(thing_name, next_token)
            shadow_list.extend(named_shadow_list)

        result = {
            "results": shadow_list,
            "timestamp": time.time()
        }

        return web.json_response(result)



    @routes.get('/shadow/{name}/{shadow}')
    async def return_named_shadow(request):
        get_thing_shadow_request = request.app['shadow_functions']['get_thing_shadow_request']

        thing_name = request.match_info['name'] 
        shadow_name = request.match_info['shadow'] 

        response_message = get_thing_shadow_request(thing_name, shadow_name)

        resp = {}
        resp["response"] = "OK"
        resp["return_code"] = 200

        if isinstance(response_message, list) and not response_message:
            #List is empty. No JSON to parse
            response = response_message
        else:
            response = json.loads(response_message)

        return web.json_response(response)

    @routes.get('/deleteshadow/{name}/{shadow}')
    async def return_named_shadow(request):
        delete_named_shadow_request = request.app['shadow_functions']['delete_named_shadow_request']

        thing_name = request.match_info['name'] 
        shadow_name = request.match_info['shadow'] 

        response_message = delete_named_shadow_request(thing_name, shadow_name)
        resp = {}
        resp["response"] = "OK"
        resp["return_code"] = 200

        response_message = {
            "message": "DeleteNamedShadowForThing",
            "response": resp["response"],
            "return_code": resp["return_code"]
            }
        return web.json_response(response_message)

    #Respond to a http POST REST message
    @routes.post('/message/chip/request')
    async def return_chip_request(request):
        queue = request.app['queue']
        message_router = request.app['message_router']
        json_str = "{}"
        if request.body_exists:
            bytes_value = await request.read()
            json_str = bytes_value.decode('utf8').replace("'", '"')

        resp = {}
        resp["return_code"] = 200
        resp["response"] = ""

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
                #lPrint(f"{MSG_MISSING_ATTRIBUTE} for message")
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
            #lPrint(f"{MSG_INVALID_JSON} for message")
            return web.json_response(response_message)
        except Exception as e:
            raise
        
        command = message_from_rest["command"]
        command = command.lstrip()

        nodeId = None
        resp["response"] = "accepted"
        resp["return_code"] = 200
        resp["message_id"] = message_from_rest["message_id"]

        message_router(message_from_rest)

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
