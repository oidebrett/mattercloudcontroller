import logger
import awsiot.greengrasscoreipc
import awsiot.greengrasscoreipc.client as client
from awsiot.greengrasscoreipc.model import ListNamedShadowsForThingRequest
from awsiot.greengrasscoreipc.model import GetThingShadowRequest
from awsiot.greengrasscoreipc.model import UpdateThingShadowRequest
import json
import time

TIMEOUT = 10

#Get the shadow from the local IPC
def sample_get_thing_shadow_request(thingName, shadowName):
    logger.info("getting_thing_shadow_request: "+shadowName)

    try:
        logger.info("Getting ipc_client")
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

        #convert string to json object
        jsonmsg = json.loads(result.payload)

#        logger.info("jsonmsg")
        logger.info(jsonmsg)

        #print desired states
#        logger.info(jsonmsg['state']['desired'])    
        
        #if redledon is equal to true/1 then turn on else off
#        if jsonmsg['state']['desired']['redledon']:
#           logger.info("true turn led on")
#        else:
#           logger.info("false turn off")

        return result.payload
        
    except Exception as e:
        logger.info("Error get shadow")
        # except ResourceNotFoundError | UnauthorizedError | ServiceError

def sample_list_named_shadows_for_thing_request(thingName):
    try:
        # set up IPC client to connect to the IPC server
        ipc_client = awsiot.greengrasscoreipc.connect()
                
        # create the ListNamedShadowsForThingRequest request
        list_named_shadows_for_thing_request = ListNamedShadowsForThingRequest()
        list_named_shadows_for_thing_request.thing_name = thingName

        # retrieve the ListNamedShadowsForThingRequest response after sending the request to the IPC server
        op = ipc_client.new_list_named_shadows_for_thing()
        op.activate(list_named_shadows_for_thing_request)
        fut = op.get_response()

        list_result = fut.result(TIMEOUT)
        logger.info(list_result)

        # additional returned fields
        named_shadow_list = list_result.results

        return named_shadow_list

    except Exception as e:
        logger.info("Error List Named shadows")         
        # add error handling
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
        logger.info("Error update shadow")
        # except ConflictError | UnauthorizedError | ServiceError

#initial settings for the reported states of the device
currentstate = json.loads('''{"state": {"reported": {"status": "startup","redledon": false}}}''')


while(True):
    shadowName = 'shadow3'
    thingName = 'mcc-thing-ver01-1'
    logger.info("getting shadow document")
    #check document to see if led states need updating
    response = sample_get_thing_shadow_request(thingName, shadowName)
    time.sleep(5)


    #convert string to json object
    jsonmsg = json.loads(response)

    # logger.info("jsonmsg")
    logger.info(jsonmsg)
        
    try:
        #if redledon is equal to true/1 then turn on else off
        if jsonmsg['state']['desired']['redledon']:
            logger.info("true turn led on")
            #set current status to bad and update actual value of led output to reported
            logger.info("setting shadow value bad")
            currentstate['state']['reported']['status'] = "good"
            currentstate['state']['reported']['redledon'] = 1
            sample_update_thing_shadow_request(thingName, shadowName, bytes(json.dumps(currentstate), "utf-8"))   
        else:
            logger.info("false turn led off")
            #set current status to good and update actual value of led output to reported
            logger.info("setting shadow value good")
            currentstate['state']['reported']['status'] = "good"
            currentstate['state']['reported']['redledon'] = 0
            sample_update_thing_shadow_request(thingName, shadowName, bytes(json.dumps(currentstate), "utf-8"))   
    except Exception as e:
        logger.info("Error setting state"+str(e))
        logger.info("setting shadow value bad")
        currentstate['state']['reported']['status'] = "bad"
        sample_update_thing_shadow_request(thingName, shadowName, bytes(json.dumps(currentstate), "utf-8"))   

    time.sleep(5)


    logger.info("listing named shadows for a thing:"+thingName)
    #check document to see if led states need updating
    logger.info(sample_list_named_shadows_for_thing_request(thingName))
    time.sleep(5)
