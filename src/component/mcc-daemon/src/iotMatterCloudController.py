import argparse
import logging
import os
import sys
import time
import datetime
import subprocess
import json

parser = argparse.ArgumentParser()
parser.add_argument("-p", "--storagepath", help="Path to persistent storage configuration file (default: /tmp/repl-storage.json)", action="store", default="/tmp/repl-storage.json")
parser.add_argument("-t", "--test", help="true if testing local", action="store", default="False")
parser.add_argument("-c", "--clean", help="true to clean working directory", action="store", default="False")
parser.add_argument("-s", "--stop", help="true to stop at first resolve fail", action="store", default="False")

args = parser.parse_args()
LOCAL_TEST_ARG = args.test
LOCAL_TEST = LOCAL_TEST_ARG.lower() == 'true'
CLEAN_ARG = args.clean
CLEAN = CLEAN_ARG.lower() == 'true'
STOP_ARG = args.stop
STOP = STOP_ARG.lower() == 'true'


curr_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(curr_dir)
import iotMatterDeviceController

sleep_time_in_sec = int(os.environ.get('SLEEP_TIME', '10'))
stabilisation_time_in_sec = int(os.environ.get('STABLE_TIME', '5'))

RESPONSE_FORMAT = "json"
TIMEOUT = 10
MSG_TIMEOUT = f"Command timed out, limit of {TIMEOUT} seconds"
MSG_MISSING_ATTRIBUTE = "The attributes 'txid' and 'command' missing from request"
MSG_INVALID_JSON = "Request message was not a valid JSON object"
THING_NAME = os.getenv('AWS_IOT_THING_NAME')

# Set up request topic and response topic from passed in arguments
REQUEST_TOPIC = "chip/request"
RESPONSE_TOPIC = "chip/response"

def lPrint(msg):
    logging.info(msg)
    print(msg, file=sys.stdout)
    sys.stderr.flush()

if not LOCAL_TEST:
    lPrint("not LOCAL_TEST")
    workingDir = "/home/ubuntu/connectedhomeip"
    ipc_client = awsiot.greengrasscoreipc.connect()
else:
    lPrint("is LOCAL_TEST")
    #workingDir = "/home/ivob/Projects/connectedhomeip"
    workingDir = "/home/ivob/Projects/sdk-connectedhomeip"
    _sample_file_name = 'sample_data.json'

def load_environ():
    global _topic, _thing_name, _version
    _topic = os.environ.get('RULE_TOPIC', 'test/rule/topic')
    _thing_name = os.environ.get('AWS_IOT_THING_NAME', 'DevLocal')
    _version = os.environ.get('FUNCTION_VERION', 'not-defined')
    lPrint('--->load_environ: topic- {}'.format(_topic))
    lPrint('--->load_environ: lambda version- {} at {}--==<<'.format(_version, str(datetime.datetime.now())))

#This function allows us to run unix commands
#TBD - we need to put some protections in here e.g. only chip-tool commands are allowed
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
        lPrint(
            f"Comand took longer than {TIMEOUT} seconds for message"
        )

def OnValueChange(nodeId) -> None:
    lPrint("Saw value change inside Cloud Controller! for nodeId: "+ str(nodeId)+ ":"+str(type(nodeId)))
    changedNodeIds.append(nodeId)

def pollForDeviceReports():
    thingName = 'mcc-thing-ver01-1'
    lPrint("pollForDeviceReports.........")
    
    #deviceNodeIds = matterDevices.getCommissionedDevices()
    #we only need to look at the devices that were changed (as indicated by a subscription change)
    deviceNodeIds = changedNodeIds

    for nodeId in deviceNodeIds:
        deviceNodeIds.remove(nodeId) #first remove this nodeId so we dont call it again unless its changed
        #check device to read current state
        #currentStateStr = matterDevices.readDevAttributesAsJsonStr(nodeId)
        currentStateStr = matterDevices.readEndpointZeroAsJsonStr(nodeId)

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



#This code is to allow for local testing 
#where it polls for a command that is written into the sample_data.json file
#this file carries the same json format as that that comes from the MQTT bus

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
                changedNodeIds.append(nodeId)
                time.sleep(stabilisation_time_in_sec)
                '''
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
                '''

                #Set up a subscription that will call OnValueChange when ever we get a change
                lPrint("Settting Up Subscription on nodeId:")
                matterDevices.subscribeForAttributeChange(nodeId, OnValueChange)


        if command == "discover": # we always have to update the discoveredCommissionableDevices after we commission
            discoveredCommissionableNodes = matterDevices.discoverCommissionableDevices()
            commissionableNodesJsonStr = matterDevices.jsonDumps(discoveredCommissionableNodes)
            lPrint(commissionableNodesJsonStr)
            if not LOCAL_TEST:
                #set the device shadow for commissionableNodes
                shadowName = "commissionableNodes"
                thingName = 'mcc-thing-ver01-1'
                newStr = '{"state": {"reported": '+commissionableNodesJsonStr+'}}'
                #lPrint(newStr)
                #newState = json.loads(newStr)
                #sample_update_thing_shadow_request(thingName, shadowName, bytes(json.dumps(newState), "utf-8"))
                sample_update_thing_shadow_request(thingName, shadowName, bytes(newStr, "utf-8"))
            else:
                pass

        elif command == "write":
            id = sample["id"]
            lPrint("Writing Attribute / Node Labal")
            nodeId = int(id)
            matterDevices.writeNodeLabel(nodeId)
        elif command == "writeAttribute":
            id = sample["id"]
            lPrint("Writing Attribute / Node Labal")
            nodeId = int(id)
            matterDevices.writeAttribute(1,0,"BasicInformation","NodeLabel","TestingGood")
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


def main():
    global matterDevices
    global changedNodeIds
    #Initialize the buffer that will hold the nodes that have changed
    changedNodeIds = []

    if not LOCAL_TEST:
        lPrint("Setting up the MQTT Subscription")
        # Setup the MQTT Subscription
        handler = StreamHandler()
        subscribeToTopic(REQUEST_TOPIC, handler)

    lPrint('------------------------run-------------------')
    load_environ()

    lPrint("LOCAL_TEST: "+str(LOCAL_TEST))
    lPrint("CLEAN: "+str(CLEAN))
    lPrint("STOP: "+str(STOP))

    topic = '{}/{}'.format(_topic, _thing_name)

    #Setting up the chip repl
    #console = Console()
    lPrint("Current Working Directory " + os.getcwd())

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
        if STOP:
            #We will stop discovering at the first resolve failure
            changedNodeIds = matterDevices.discoverFabricDevices(True)
        else:
            changedNodeIds = matterDevices.discoverFabricDevices()

        #Recreate the subscriptions so that we can detect the changes
        for nodeId in changedNodeIds:
            lPrint("Settting Up Subscription on nodeId:"+str(nodeId))
            matterDevices.subscribeForAttributeChange(nodeId, OnValueChange)
        lPrint("Finished Discovering commissioned devices")

    discoveredCommissionableNodes = matterDevices.discoverCommissionableDevices()
    print(discoveredCommissionableNodes)

    # Keep the main thread alive, or the process will exit.
    x=1

    while True:
        lPrint(x)
        x += 1

        if LOCAL_TEST: # if local testing we will use a file for commissioning
            pollForCommand(_sample_file_name)

        # poll every sleep_time_in_sec for latest device state
        pollForDeviceReports()

        #matterDevices.writeNodeLabel(1) 

        lPrint('--->run: sleep- {}'.format(sleep_time_in_sec) + " " + REQUEST_TOPIC)
        time.sleep(sleep_time_in_sec)

def exitGracefully():
    # To stop subscribing, close the operation stream.
    if not LOCAL_TEST:
        operation.close()
    lPrint("exiting gracefully")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        exitGracefully()
        pass