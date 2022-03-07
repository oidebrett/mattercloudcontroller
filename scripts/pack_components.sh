#!/bin/sh

# Configuration File Path
APP_CONFIG=$1

PROJECT_NAME=$(cat $APP_CONFIG | jq -r '.Project.Name') #ex> IoTData
PROJECT_STAGE=$(cat $APP_CONFIG | jq -r '.Project.Stage') #ex> Dev
PROJECT_PREFIX=$PROJECT_NAME$PROJECT_STAGE

THING_NAME=$(cat $APP_CONFIG | jq -r '.Stack.ComponentDeployment.Thing.Name') 
THING_PATH=$(cat $APP_CONFIG | jq -r '.Stack.ComponentDeployment.Thing.CodePath') 


echo ==-------ThingComponent---------==
echo $THING_NAME
echo $THING_PATH
COMP_NAME=$THING_NAME
BASE_PATH=$THING_PATH

ZIP_FILE=$PROJECT_PREFIX-$COMP_NAME.zip
cd $BASE_PATH
if [ -d "zip" ]; then
    rm -r "zip"
fi
mkdir zip
cd src
zip -r $ZIP_FILE ./*  -x \*__pycache__\*
mv $ZIP_FILE ../zip
cd ../../../..
echo .
echo .

