#!/usr/bin/env python

#
#    Copyright (c) 2022 MatterCloudController Authors
#    All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#

#
#    @file
#      This file implements the Python-based Local Chip Device Controller.
#
import signal
import sys
import time
import logging
import argparse
import json
import subprocess
from ttp import ttp
import pprint
import shlex
import MatterTextTemplates

TIMEOUT = 100
RESPONSE_FORMAT = "json"
MSG_INVALID_JSON = "Request message was not a valid JSON obect"
MSG_MISSING_ATTRIBUTE = "The attributes 'txid' and 'command' missing from request"
MSG_TIMEOUT = f"Command timed out, limit of {TIMEOUT} seconds"

messages = []

class RequestsHandler(logging.Handler):
    def emit(self, record):
        """Send the log records (created by loggers) to
        the appropriate destination.
        """
        #print(record.getMessage())
        messages.append(record.getMessage())

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger()
handler = RequestsHandler()
logger.addHandler(handler)



# Register SIGTERM for shutdown of container
def signal_handler(signal, frame) -> None:
    logger.info(f"Received {signal}, exiting")
    sys.exit(0)


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

parser = argparse.ArgumentParser()
parser.add_argument("--request-topic", required=False)
parser.add_argument("--response-topic", required=False)
args = parser.parse_args()

def run_command(command):
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

def main() -> None:
    """Code to execute from script"""
    response = ""
    message = ""
    operation_timeout = TIMEOUT
    response_format = RESPONSE_FORMAT

    logger.info(f"Arguments: {args}")

    try:
###        
#        output = subprocess.run(
#            "chip-tool discover commissionables",
#            timeout=operation_timeout,
#            capture_output=True,
#            shell=True,
#        )
#
#        if output.returncode == 0:
#            response = output.stdout.decode("utf-8")
#        else:
#            response = output.stderr.decode("utf-8")
        command = "chip-tool discover commissionables"
        output = run_command(command)
        print("********")
        lsTtp = MatterTextTemplates.LsTemplater(output)

        lsTtp.parse()

    except subprocess.TimeoutExpired:
        response = MSG_TIMEOUT
        logger.error(
            f"Comand took longer than {operation_timeout} seconds for message: {message}"
        )

    print(response)
    #logger.info(f"Response: {response}")


    #time.sleep(5)
    print(messages)


    template = """
    Long Discriminator {{ ld }}
    """

    parser = ttp(response, template)
    parser.parse()
    pprint.pprint(parser.result(), width=100)

#    while True:
        # Keep app open and running
#        time.sleep(1)

if __name__ == "__main__":
    main()

