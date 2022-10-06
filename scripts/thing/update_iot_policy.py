import os
import json
import argparse
import datetime
import boto3

def convert_datetime(o):
    if isinstance(o, datetime.datetime):
        return o.__str__()

if __name__ == '__main__':
    print('--->Start<---')

    parser = argparse.ArgumentParser(description='Update IOT policy')
    parser.add_argument('-a', '--app', required=True, help='app-config.json')
    parser.add_argument('-p', '--policy', required=True, help='policy document')
    args = parser.parse_args()
    print('==>Input: ', args.app, args.policy)

    with open(args.app) as f:
        app = json.load(f)

    project_name = app['Project']['Name']
    project_stage = app['Project']['Stage']
    project_account = app['Project']['Account']
    profile_name = app['Project']['Profile']
    project_prefix = project_name + project_stage
    policy_file = args.policy

    os.environ['AWS_PROFILE'] = profile_name

    if (args.policy):
        client = boto3.client('iot')
        response = client.create_policy_version(policyName='GreengrassV2IoTThingPolicy',policyDocument=args.policy, setAsDefault=True)
        print(response)

    print('--->Finish<---')
