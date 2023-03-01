#!/bin/sh

set -e
set +m 

#This file both works for local install and for use with docker compose
#When used with docker compose the config file WILL NOT BE present
#and the information will be held in the ENVIRONMENT variables

echo $CONFIG

#Check if there are arguments which means its being runnning locally and given a json file
#Otherwise we assume the CONFIG environment variable contains the JSON
if [ $# -eq 0 ]
then 
  echo "No arguments - lets try for a config environment variable..."

  PROJECT_PREFIX=$(echo $CONFIG | jq -r '.ProjectPrefix')

  JQ_ARG='.["'$PROJECT_PREFIX'-ThingInstallerStack"].OutputThingNamePrefix'
  THING_NAME=$(echo $CONFIG | jq -r $JQ_ARG) #ex>  

  JQ_ARG='.["'$PROJECT_PREFIX'-ThingInstallerStack"].OutputThingGroupName'
  THING_GROUP=$(echo $CONFIG | jq -r $JQ_ARG) #ex>  

  JQ_ARG='.["'$PROJECT_PREFIX'-ThingInstallerStack"].OutputProjectRegion'
  REGION=$(echo $CONFIG | jq -r $JQ_ARG) #ex>  

  JQ_ARG='.["'$PROJECT_PREFIX'-ThingInstallerStack"].OutputIoTTokenRole'
  ROLE_NAME=$(echo $CONFIG | jq -r $JQ_ARG) #ex>  

  JQ_ARG='.["'$PROJECT_PREFIX'-ThingInstallerStack"].OutputIoTTokenRoleAlias'
  ROLE_ALIAS_NAME=$(echo $CONFIG | jq -r $JQ_ARG) #ex>  

  export AWS_ACCESS_KEY_ID=$(echo $CONFIG | jq -r '.Credentials.AccessKeyId')
  export AWS_SECRET_ACCESS_KEY=$(echo $CONFIG | jq -r '.Credentials.SecretAccessKey')
  export AWS_SESSION_TOKEN=$(echo $CONFIG | jq -r '.Credentials.SessionToken')
  
  SETUPSYSTEMSERVICE=false
  
else
  # In this case we may need to install jq as we arent running from a docker buiklt image
  # that had jq install at image build time.

  sudo apt-get install jq -y

  CONFIG_FILE=$1
  PROJECT_PREFIX=$(cat $CONFIG_FILE | jq -r '.ProjectPrefix')

  JQ_ARG='.["'$PROJECT_PREFIX'-ThingInstallerStack"].OutputThingNamePrefix'
  THING_NAME=$(cat $CONFIG_FILE | jq -r $JQ_ARG) #ex>  

  JQ_ARG='.["'$PROJECT_PREFIX'-ThingInstallerStack"].OutputThingGroupName'
  THING_GROUP=$(cat $CONFIG_FILE | jq -r $JQ_ARG) #ex>  

  JQ_ARG='.["'$PROJECT_PREFIX'-ThingInstallerStack"].OutputProjectRegion'
  REGION=$(cat $CONFIG_FILE | jq -r $JQ_ARG) #ex>  

  JQ_ARG='.["'$PROJECT_PREFIX'-ThingInstallerStack"].OutputIoTTokenRole'
  ROLE_NAME=$(cat $CONFIG_FILE | jq -r $JQ_ARG) #ex>  

  JQ_ARG='.["'$PROJECT_PREFIX'-ThingInstallerStack"].OutputIoTTokenRoleAlias'
  ROLE_ALIAS_NAME=$(cat $CONFIG_FILE | jq -r $JQ_ARG) #ex>  

  export AWS_ACCESS_KEY_ID=$(cat $CONFIG_FILE | jq -r '.Credentials.AccessKeyId')
  export AWS_SECRET_ACCESS_KEY=$(cat $CONFIG_FILE | jq -r '.Credentials.SecretAccessKey')
  export AWS_SESSION_TOKEN=$(cat $CONFIG_FILE | jq -r '.Credentials.SessionToken')

  SETUPSYSTEMSERVICE=true
fi

echo $THING_NAME
echo $THING_GROUP
echo $ROLE_NAME
echo $ROLE_ALIAS_NAME

#Set up the packages that we need
python3 -m pip install awsiotsdk
pip3 install boto3
pip3 install awsiot
pip3 install botocore
pip3 install python-dateutil
pip3 install apscheduler

DEV_ENV=true

java -version

sudo mkdir greengrass
cd greengrass
INSTALL_ROOT=GreengrassCore
#sudo curl -s https://d2s8p88vqu9w66.cloudfront.net/releases/greengrass-nucleus-latest.zip > greengrass-nucleus-latest.zip && sudo unzip greengrass-nucleus-latest.zip -d GreengrassCore
sudo wget https://d2s8p88vqu9w66.cloudfront.net/releases/greengrass-nucleus-latest.zip 
sudo unzip -o greengrass-nucleus-latest.zip -d GreengrassCore

echo $THING_NAME
echo $THING_GROUP
echo $ROLE_NAME
echo $ROLE_ALIAS_NAME

GREENGRASS_ROOT=/greengrass/v2
GREENGRASS_JAR=./GreengrassCore/lib/Greengrass.jar


# If we have not already installed Greengrass
if [ ! -d $GGC_ROOT_PATH/alts/current/distro ]; then
  sudo -E java -Droot=$GREENGRASS_ROOT \
    -Dlog.store=FILE \
    -jar $GREENGRASS_JAR \
    --aws-region $REGION \
    --thing-name $THING_NAME \
    --thing-group-name $THING_GROUP \
    --tes-role-name $ROLE_NAME \
    --tes-role-alias-name $ROLE_ALIAS_NAME \
    --component-default-user ggc_user:ggc_group \
    --provision true \
    --setup-system-service $SETUPSYSTEMSERVICE
else
	echo "Reusing existing Greengrass installation..."
fi

if [ ! $SETUPSYSTEMSERVICE ]; then
  #Make loader script executable
  echo "Making loader script executable..."
  chmod +x $GGC_ROOT_PATH/alts/current/distro/bin/loader

  echo "Starting Greengrass..."

  # Start greengrass kernel via the loader script and register container as a thing
  exec $GGC_ROOT_PATH/alts/current/distro/bin/loader
fi
