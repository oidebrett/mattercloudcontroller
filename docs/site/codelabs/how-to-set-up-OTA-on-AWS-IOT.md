summary: How to Developer Matter on WSL
id: how-to-set-up-OTA-on-AWS-IOT
categories: Sample
tags: AWS-IOT
status: Published 
authors: MatterCoder
Feedback Link: https://mattercoder.com

# How to Set up OTA on AWS-IOT
<!-- ------------------------ -->
## Overview 
Duration: 25

In this codelab we will show you how to Set up OTA on AWS-IOT

### What You’ll Build 
In this codelab, you will:
- Set up Over The Air Firmware Updates using AWS IOT


### What You’ll Learn 
- What you will need (Pre-requisities)
- How to create an IAM User with the appropriate policies.
- How to create an Amazon S3 bucket to store your update
- How to create an OTA Update service role
- How to create certificate for signing code
- How to create OTA Thing and job
- How to Create OTA JOB to send a Matter binary over OTA ( Optional )

<!-- ------------------------ -->
## What you will need (Pre-requisities)
Duration: 2

You will need
- a laptop or PC running Ubuntu 22.04
- a basic knowledge of Linux shell commands

The total codelab will take approximately a `Duration of 30 minuates` to complete. 

<!-- ------------------------ -->
## Create IAM User (This is used instead of using the ROOT User)
Duration: 5

1- Search and navigate to IAM page

2- Choose User then Add User

3- Select the name "My_OTA_User" for example

4- For access type Select whatever you like (we can use Paragmmatic access)

5- Select attach existence policy and search for and select the following:

      - AmazonFreeRTOSFullAccess

      - AmazonFreeRTOSOTAUpdate
      
      - AWSIoTFullAccess

6- Select Create User and download the credentials CSV file

7- Take note of the account id >> arn:aws:iam::XXXXXXXXXXXX:user/My_OTA_User

Note: These Xs is the account id and we will need it later.

<!-- ------------------------ -->
## Creating Policies and Roles for OTA update/ S3 bucket access:
Duration: 5 

### Create an Amazon S3 bucket to store your update

1- Sign in to the Amazon S3 console at https://console.aws.amazon.com/s3/.

2- Choose Create bucket.

3- Enter a bucket name. (for example  testotabucket123)

4- Under Bucket settings for Block Public Access keep Block all public access selected to accept the default permissions.

5- Under Bucket Versioning, select Enable to keep all versions in the same bucket.

6- Choose Create bucket.
 
<!-- ------------------------ -->
##  Create an OTA Update service role:
Duration: 2

### Sign in to the https://console.aws.amazon.com/iam/.

1- From the navigation pane, choose Roles.

2- Choose Create role.

3- Under Select type of trusted entity, choose AWS Service.

4- Choose IoT from the list of AWS services.

5- Under Select your use case, choose IoT.

6- Choose Next: Permissions.

7- Choose Next: Tags.

8- Choose Next: Review.

9- Enter a role name (OTA_Service_Role for example) and description, and then choose Create role. 
 
### Add OTA update permissions to your OTA service role:

1- Open the Role you just create (OTA_Service_Role)

2- Choose Attach policies.

3- In the Search box, enter "AmazonFreeRTOSOTAUpdate", select AmazonFreeRTOSOTAUpdate and then choose Attach policy to attach the policy to your service role.
 
### Add the required IAM permissions to your OTA service role
1- Open the Role again (OTA_Service_Role)

2- Choose Add inline policy.

3- Choose the JSON tab.

4- Copy and paste the following policy document into the text box:

```shell
  {
    "Version": "2012-10-17",
    "Statement": [
      {
            "Effect": "Allow",
            "Action": [
                "iam:GetRole",
                "iam:PassRole"
            ],
            "Resource": "arn:aws:iam::your_account_id:role/your_role_name"
      }
    ]
  }
```

5- Update "your_account_id" with the user account you created (The Xs), and the "your_role_name" with your ota service role, which in our
  example is OTA_Service_Role, so the line will be like this 

  "Resource": "arn:aws:iam::XXXXXXXXXXXX:role/OTA_Service_Role"

6- Choose Review policy.

7- Enter a name for the policy (for example OTA_Role_IAM_Permission_Policy), and then choose Create policy.
  
<!-- ------------------------ -->
## Add the required Amazon S3 permissions to your OTA service role 
Duration: 2

1- Open the Role again (OTA_Service_Role)

2- Choose Add inline policy.

3- Choose the JSON tab.

4- Copy and paste the following policy document into the text box:

```shell
  {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObjectVersion",
                "s3:GetObject",
                "s3:PutObject"
            ],
            "Resource": [
                "arn:aws:s3:::example-bucket/*"
            ]
        }
    ]
  }
```

5- Upate the example-bucket with the bucket name you created, in our example testotabucket

So it will be "arn:aws:s3:::testotabucket123/*" 

6- Choose Review policy.

7- Enter a name for the policy (for example OTA_Role_S3_Bucket_Permission_Policy ), and then choose Create policy.
  
<!-- ------------------------ -->
##  Create an OTA user policy: 
Duration: 2

### This gives the user all the needed permission to perform OTA updates

1- Navigate to IAM page

2- In the navigation pane, choose Policies

3- Choose Create policy.

4- Choose the JSON tab, and copy and paste the following policy document into the policy editor:

```shell
  {
    "Version":"2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:ListAllMyBuckets",
                "s3:CreateBucket",
                "s3:PutBucketVersioning",
                "s3:GetBucketLocation",
                "s3:GetObjectVersion",
                "s3:ListBucketVersions",
                "acm:ImportCertificate",
                "acm:ListCertificates",
                "iot:*",
                "iam:ListRoles",
                "freertos:ListHardwarePlatforms",
                "freertos:DescribeHardwarePlatform"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject"
            ],
            "Resource": "arn:aws:s3:::testotabucket123/*"
        },
        {   
            "Effect": "Allow",
            "Action": "iam:PassRole",
            "Resource": "arn:aws:iam::your-account-id:role/role-name"
        }
    ]
}
```

5- Update the "example-bucket", "your-account-id", and "role-name" as before

6- Choose Review policy.

7- Enter a name for your new OTA user policy (for example OTA_User_Policy), and then choose Create policy.

### To attach the OTA user policy to your IAM user

1- In the IAM console, in the navigation pane, choose Users, and then choose your user.

2- Choose Add permissions.

3- Choose Attach existing policies directly.

4- Search for the OTA user policy you just created (for example OTA_User_Policy) and select the check box next to it.

5- Choose Next: Review.

6- Choose Add permissions.

### To grant your IAM user account permissions for code signing for AWS IoT

1- In the IAM console,  choose Policies.

2- Choose Create Policy.

3- On the JSON tab, copy and paste the following JSON document into the policy editor. 

This policy allows the IAM user access to all code-signing operations.

```shell
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "signer:*"
      ],
      "Resource": "*"
    }
  ]
}
```

4-Choose Review policy.

5- Enter a policy name (for example OTA_Code_Sign_Policy) and description, and then choose Create policy.

6- In the navigation pane, choose Users.

7- Choose your IAM user account.

8- On the Permissions tab, choose Add permissions.

9- Choose Attach existing policies directly, and then select the check box next to the code-signing policy you just created OTA_Code_Sign_Policy.

10- Choose Next: Review.

11- Choose Add permissions.

<!-- ------------------------ -->
## Create certificate for signing the code :
Duration: 5

Note: we are following https://docs.aws.amazon.com/freertos/latest/userguide/ota-code-sign-cert-esp.html

1- Check if openssl is already installed by typing openssl version

2- If not already installed, download and install openssl : https://github.com/openssl/openssl/releases/tag/OpenSSL_1_1_1j

3- Add Openssl to the enviornment variable path

4- Create a directory and name it "Code_Certificate" 

5- In your directory open command line prompt

6- Create a file named cert_config.txt. Add the following contest, Replace test_signer@amazon.com with your email address:

```shell
[ req ]
prompt             = no
distinguished_name = my_dn
                    
[ my_dn ]
commonName = test_signer@amazon.com
                    
[ my_exts ]
keyUsage         = digitalSignature
extendedKeyUsage = codeSigning
```

6- Create an ECDSA code-signing private key using the command:

openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -pkeyopt ec_param_enc:named_curve -outform PEM -out ecdsasigner.key

7- Create an ECDSA code-signing certificate using the command:

openssl req -new -x509 -config cert_config.txt -extensions my_exts -nodes -days 365 -key ecdsasigner.key -out ecdsasigner.crt

8- Import the code-signing certificate, private key, and certificate chain into AWS Certificate Manager:

aws acm import-certificate --certificate fileb://ecdsasigner.crt --private-key fileb://ecdsasigner.key

This command displays an ARN for your certificate. You need this ARN when you create an OTA update job.

==================================================================
<!-- ------------------------ -->
## Create OTA Thing and job
Duration: 10

### Install aws cli:
- You should have python 3.4 or later installed and pip

- Install aws cli using   

```shell
pip install boto3
```

- Configure aws cli with your user:

1- run commnad : aws configure

2- From the CSV file you downloaded while createing the user, find access key ID, secret access key

3- Enter access key ID, secret access key when prompt

4- Keep Default region name [eu-west-1] (just press enter)

5- Keep Default output format [json] (just press enter)

### Now we can start to create the OTA thing and job

1- Preapare FreeRTOS repo and install required packages

2- Create thing using aws cli and update device header files

3- Select OTA Demo to build,  Build and flash OTA Demo 

4- Create OTA JOB

the following 3 sections need to be changed for

1- Clone the esp-aws-iot repo https://github.com/espressif/esp-aws-iot/tree/master 

2- Prepare FreeRTOS repo and install required packages

- You should have python 3.4 or later installed and pip

- Download esp-aws-iot.git repo 

```shell
      git clone https://github.com/espressif/esp-aws-iot.git --recurse-submodules
```

and then switch to the latest release

```shell
      git fetch --all --tags
      git checkout master
```

- Go to your ESP idf tools folder and 

```shell
      git fetch --all --tags
      git checkout master
```

- in command prompt run:

```shell
      ./install.sh
```

This will download and install required packages

5- After download all packages sucessfully, run . /export.sh to populate enviornmental variables.
 
6- Manually creating Things with policy as per https://youtu.be/0Lt-bMbJyKc?si=9YQNOVXxZTybGqsv&t=575

7-  Create thing using aws console

- in aws console go to IoT Core - Manage - All Devices

        Create a new Thing:

        thing_name :  to whatever name for your device, for example OTA_Device
                
- Select Auto-generate a new certificate:
    
- Create a new Policy - give it a name such as OTA_Device_policy
    
- Select JSON and paste in the following
    
```shell
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "iot:Connect",
      "Resource": "arn:aws:iot:eu-west-1:your-account-id:client/OTA_Device"
    },
    {
      "Effect": "Allow",
      "Action": "iot:Subscribe",
      "Resource": "arn:aws:iot:eu-west-1:your-account-id:topicfilter/$aws/things/OTA_Device/*"
    },
    {
      "Effect": "Allow",
      "Action": "iot:Receive",
      "Resource": "arn:aws:iot:eu-west-1:your-account-id:topic/$aws/things/OTA_Device/*"
    },
    {
      "Effect": "Allow",
      "Action": "iot:Publish",
      "Resource": "arn:aws:iot:eu-west-1:your-account-id:topic/$aws/things/OTA_Device/*"
    }
  ]
}
```

Note: You can tighten up the wildcards when you have this working
 
- Attach this policy to your Thing and hit create
 
- Download the certificate and keys to your Code_certificate folder
 
- Click Done
 
8. Build new OTA verson and flash

- Select OTA Demo to build,  Build and flash OTA Demo 

    - open folder examples/ota/ota_mqtt/main/certs

        Replace client.crt with the client certificate that you downloaded. Make sure you rename to client.crt

        Replace client.key with the client private key that you downloaded. Make sure you rename to client.key

    - To configure the demo, Open command prompt in examples/ota/ota_mqtt and run:

        idf.py set-target esp32
        idf.py menuconfig

        Change ->Example Configuration-> Client Identifier to OTA_Device (name of your Thing)

        Change ->Example Configuration-> Endpoint of MQTT broker to your endpoint 

        you will find this in AWS Console AWS IoT->Settings (*look for something like youruniqueid-ats.iot.eu-west-1.amazonaws.com)

        Change ->Example Connection Configuration -> Wifi SSID and Password to your SSID and password

    - To build the demo, Open command prompt in examples/ota/ota_mqtt and run:

        idf.py build

    - To flash and monitor the demo run:

        idf.py -p COMx erase_flash flash monitor

          - Replace x in COMx with your ESP32 COM port number
          - you can use erase_flash first time only to make sure flash layout is cleaned before flash OTA demo.
  
9. Create OTA JOB

    - In AWS IOT console, go to manage->Remote Actions-> Jobs

    - Choose create, create OTA update job

    - Select your device, in our example "OTA_Device"
    
    - Keep MQTT as the transfer protocol
    
    - Select "Sign a new file for me"

    - For Code signing profile, choose create, 
      - write the profile name, for example OTA_Sign_Profile

      - Select device : ESP-32

      - For certificate: use an existing Cert (stored previously in ACM)

      - For "Path name of code signing certificate on device", put the following value:
         
         Code Verify Key

    - Select your file in S3 or upload it

        - Select your bucket, in our example: "testotabucket", and upload a file, or select previously uploaded one.
        
        - OTA_Demo bin file is located in examples/ota/ota_mqtt/ota_mqtt.bin
        
        NOTE:
          The new bin file version should be higher than the one on the ESP, for example in 
        
          examples/ota/ota_mqtt/main/demo_config.h
        
          If the version we build and flash was 0.9.2
        
          We should increment the number for example to 0.9.3, and build but not flash using idf.py build (as before)
          
    - Pathname of file on device: just write /

    - IAM role for OTA update job: choose the OTA role you created, in our examle: "OTA_Service_Role", choose Next
    
    - Write and Name for the Job in ID: for exaple ID_001, then chhose create
    
    - If the device is connected, Firmware update should start.
    
    - The esp32 device will restart at least 2 times to complete the software update
    
    You can confirm that your ESP32 is running the updated version by looking at the logs on the idf.py monitor just before when the TLS session is established

```shell
    I (5693) AWS_OTA: OTA over MQTT demo, Application version 0.9.3  <<<<<------- this shows the new version has be flashed over the air
    I (5703) AWS_OTA: Establishing a TLS session to xxxxxxxxx.iot.eu-west-1.amazonaws.com:888
```
    
10. Optional - Create OTA JOB to send a Matter binary over OTA
  - Build the matter lighting esp32 app from the github connectedhomeoverip

  - copy the partitions.csv to the esp-aws-iot examples folder ota_mqtt

  - save the old  partitions_ota_mqtt.csv to  partitions_ota_mqtt.csv.copy

  - move the partitions.csv to partitions_ota_mqtt.csv

  - build the ota_mqtt example and flash

  - follow the steps in 4 to create a job to update the ESP32 with the matter lighting binary






