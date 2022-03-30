"""
Listen for incoming chip-tool requests and publish the results onto response topic
--request-topic - defaults to chip-tool/request
--response-topic - defaults tochip-tool/response

Command message structure (JSON):
{
    "command": "onoff toggle 1",
    "txid": "12345ABC",
    "format": "json|text",
    "timeout": 10
}
- `command` - full string to pass to chip-tool
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
    PublishToIoTCoreRequest
)

curr_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(curr_dir)
sleep_time_in_sec = int(os.environ.get('SLEEP_TIME', '30'))

logger.info('---> Current Directory- {}'.format(curr_dir))

RESPONSE_FORMAT = "json"
TIMEOUT = 10
MSG_TIMEOUT = f"Command timed out, limit of {TIMEOUT} seconds"
MSG_MISSING_ATTRIBUTE = "The attributes 'txid' and 'command' missing from request"
MSG_INVALID_JSON = "Request message was not a valid JSON object"
THING_NAME = os.getenv('AWS_IOT_THING_NAME')
#BASE_COMMAND = "chip-tool"
BASE_COMMAND = ""

# Set up bucket, request topic and response topic from passed in arguments
BUCKET = ""
REQUEST_TOPIC = "chip-tool/request"
RESPONSE_TOPIC = "chip-tool/response"
if sys.argv[1:]:
    BUCKET = sys.argv[1]
    REQUEST_TOPIC = sys.argv[2]
    RESPONSE_TOPIC = sys.argv[3]

logger.info('---> REQUEST_TOPIC- {}'.format(REQUEST_TOPIC))
logger.info('---> RESPONSE_TOPIC- {}'.format(RESPONSE_TOPIC))

ipc_client = awsiot.greengrasscoreipc.connect()

_topic = None
_thing_name = None
_version = None
_sample_file_name = 'sample_data.json'

def publish_data(topic, message: str):
    logger.info('--->publish_data: topic- {}'.format(topic))
    logger.info('--->publish_data: message- {}'.format(message))

    TIMEOUT = 10
    qos = QOS.AT_LEAST_ONCE

    request = PublishToIoTCoreRequest()
    request.topic_name = topic
    request.payload = bytes(message, "utf-8")
    request.qos = qos

    operation = ipc_client.new_publish_to_iot_core()
    operation.activate(request)
    
    future = operation.get_response()
    future.result(TIMEOUT)


def utc_time():
    return datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def create_data(sample, count):
    sample['ThingName'] = _thing_name
    sample['MessageID'] = str(uuid.uuid1())
    sample['RequestTopic'] = str(REQUEST_TOPIC)

    sample['@timestamp'] = utc_time()
    sample['FuncionVersion'] = _version
    
    sample['Message']['Count'] = count
    sample['Message']['Value'] = datetime.datetime.utcnow().second
    
    message = json.dumps(sample)
    logger.info('--->create_data: data- {}'.format(message))
    return message


def load_sample_data(file_name: str):
    with open(curr_dir + '/' + file_name) as f:
        sample = json.load(f)
        return sample


def load_environ():
    global _topic, _thing_name, _version
    _topic = os.environ.get('RULE_TOPIC', 'test/rule/topic')
    _thing_name = os.environ.get('AWS_IOT_THING_NAME', 'DevLocal')
    _version = os.environ.get('FUNCTION_VERION', 'not-defined')
    logger.info('--->load_environ: topic- {}'.format(_topic))
    logger.info('--->load_environ: lambda version- {} at {}--==<<'.format(_version, str(datetime.datetime.now())))

def respond(event):
    resp = {}
    resp["return_code"] = 200
    resp["response"] = ""
    response_format = RESPONSE_FORMAT
    operation_timeout = TIMEOUT
    
    # validate message and attributes
    try:
        message_from_core = json.loads(event.message.payload.decode())

        logger.info('message from core {}: '.format(message_from_core))

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
            logger.info('{} for message: '.format(MSG_MISSING_ATTRIBUTE))
            logger.info('for message: '.format(message))
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
        logger.info(f"{MSG_INVALID_JSON} for message: {message}")
        return
    except Exception as e:
        raise
    
    command = BASE_COMMAND + " " + message_from_core["command"]
    command = command.lstrip()
    logger.info(command)
    
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
        logger.info(resp["response"])
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
    logger.info("event.message.payload:" + str(event.message.payload))

    # Publish to our topic
    response = PublishToIoTCoreRequest()
    response.topic_name = RESPONSE_TOPIC
    response.payload = bytes(json.dumps(response_message), "utf-8")
    response.qos = QOS.AT_MOST_ONCE
    response_op = ipc_client.new_publish_to_iot_core()
    response_op.activate(response)

class StreamHandler(client.SubscribeToIoTCoreStreamHandler):
    def __init__(self):
        super().__init__()

    def on_stream_event(self, event: IoTCoreMessage) -> None:
        logger.info("on_stream_event")
        try:
            # Handle message.
            respond(event)
        except:
            traceback.print_exc()

    def on_stream_error(self, error: Exception) -> bool:
        # Handle error.
        logger.info("on_stream_error")
        return True  # Return True to close stream, False to keep stream open.

    def on_stream_closed(self) -> None:
        # Handle close.
        pass


message = "Hello; bucket %s!" % BUCKET;
message+= "; " + REQUEST_TOPIC;
message += "; " + RESPONSE_TOPIC;
message += "; " + THING_NAME;

# Print the message to stdout, which Greengrass saves in a log file.
logger.info(message)

# Setup the MQTT Subscription
qos = QOS.AT_MOST_ONCE
request = SubscribeToIoTCoreRequest()
request.topic_name = REQUEST_TOPIC
request.qos = qos
handler = StreamHandler()
operation = ipc_client.new_subscribe_to_iot_core(handler)
future = operation.activate(request)
future.result(TIMEOUT)


logger.info('------------------------run-------------------')
load_environ()

sample = load_sample_data(_sample_file_name)
topic = '{}/{}'.format(_topic, _thing_name)

count = 0

# Keep the main thread alive, or the process will exit.
while True:
#    message = create_data(sample, count)

#    publish_data(topic, message)
#    logger.info('--->run: sleep- {}'.format(sleep_time_in_sec))
    time.sleep(sleep_time_in_sec)


# To stop subscribing, close the operation stream.
operation.close()
