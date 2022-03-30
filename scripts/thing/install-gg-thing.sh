CONFIG_FILE=$1

sudo apt-get install jq -y
python3 -m pip install awsiotsdk
pip3 install boto3
pip3 install awsiot
pip3 install botocore
pip3 install python-dateutil
pip3 install apscheduler

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

DEV_ENV=true

java -version

sudo mkdir greengrass
cd greengrass
INSTALL_ROOT=GreengrassCore
sudo curl -s https://d2s8p88vqu9w66.cloudfront.net/releases/greengrass-nucleus-latest.zip > greengrass-nucleus-latest.zip && sudo unzip greengrass-nucleus-latest.zip -d GreengrassCore

echo $THING_NAME
echo $THING_GROUP
echo $ROLE_NAME
echo $ROLE_ALIAS_NAME

GREENGRASS_ROOT=/greengrass/v2
GREENGRASS_JAR=./GreengrassCore/lib/Greengrass.jar
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
  --setup-system-service true
