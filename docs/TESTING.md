<p>Health Warning: this is work in progress</p>

## Testing using the API

1. Find the IOT Endpoint using

    ```
    aws iot describe-endpoint --endpoint-type iot:Data-ATS
    ```

2. Execute API call using CURL

    ```
    curl -XPOST https://XXXXX.execute-api.eu-west-1.amazonaws.com/prod/message/chip-tool/request -H "x-api-key: XXXXX" -H "Content-Type: application/json" -d '{"txid": "123","command":"help"}'
    ```

3. Testing in Postman - Install Postman and import the Curl command above. You will need to set up Postman to generate AWS signature in the Curl requests. You can following this guide: https://blog.knoldus.com/how-to-generate-aws-signature-with-postman/
Note: the APIGateway URL and API key can be parameterised and made as a variable.


## Testing during developement

navigate to the directory above the matter controller

Avahi keeps a cache of old results. To reset the cache, kill the daemon. It will auto-restart.

    ```
sudo avahi-daemon --kill
    ```

or restart each service

    ```
    sudo systemctl restart mdns.service
    sudo systemctl restart avahi-daemon.socket 
    ```

Remove the temporary files (dont do this if checking persistance)

    ```
    sudo rm -rf /tmp/chip_*
    sudo rm -rf /tmp/repl-storage.json 
    ```
Run the controller locally (using the -t flag)

    ```
    python3 mattercloudcontroller/src/component/mcc-daemon/src/iotMatterCloudController.py -t True
    ```

Send commands to the matter controller by saving the following to the sample_data.json file

Command message structure (JSON):

    ```
    {
        "command": "commission",
        "txid": "12345ABC"
    }
    ```

### Testing using iotMatterController.py

1. Add the env && to the greengrass lifecycle run command - this will show you the required environment params to run the iotMatterController python script on the command line

2. Ensure to delete any persistent files

```
sudo rm -rf ~/data/* /data/* /tmp/chip_* ~/.matter_server/*
```

3. Run the dockerised python matter server

```
docker run -d   --name matter-server   --restart=unless-stopped   --security-opt apparmor=unconfined   -v $(pwd)/data:/data   -v /run/dbus:/run/dbus:ro   --network=host   ghcr.io/home-assistant-libs/python-matter-server:stable
```

4. Start the iotMatterController.py script using the flags

```
SVCUID=<FROMSTEP1>  AWS_GG_NUCLEUS_DOMAIN_SOCKET_FILEPATH_FOR_COMPONENT=/greengrass/v2/ipc.socket python3 -u ./src/component/mcc-daemon/src/iotMatterController.py -p /home/ivob/Projects/python-matter-server  -l True
```

-l is to allow for localhost serving of the API

5. DOwnload the Matterdashboard and start using yarn rw dev

## Using AWS for iot rules

1. Create the following iot Rules

```
mccdev_thing_deleted	$aws/things/+/shadow/name/+/delete/accepted	
SELECT topic(3) as thing_name, topic(6) as shadow_name FROM '$aws/things/+/shadow/name/+/delete/accepted'
```

```
mccdev_thing_updated	$aws/things/+/shadow/name/+/update/accepted	
SELECT topic(3) as thing_name, topic(6) as shadow_name, state.reported as reported FROM '$aws/things/+/shadow/name/+/update/accepted'
```

```
mccdev_thing_updated_document		$aws/things/+/shadow/name/+/update/documents
SELECT topic(3) as thing_name, topic(6) as shadow_name, previous as previous, current as current FROM '$aws/things/+/shadow/name/+/update/documents'	
```

2. Create and join to the associated SNS topic

```
for mccdev_thing_deleted: arn:aws:lambda:eu-west-1:XXXX:function:MCCDev-iot-update-db-thing_deletedFunction
for mccdev_thing_updated: arn:aws:lambda:eu-west-1:XXXX:function:MCCDev-iot-update-db-thing_updatedFunction
for mccdev_thing_updated_document: https://matterdashboard.netlify.app/.netlify/functions/shadowUpdateWebhookForAWS
```


## Testing using a local all clusters app
    ```
    sudo sysctl -w net.ipv6.conf.wlo1.accept_ra=2
    sudo sysctl -w net.ipv6.conf.wlan0.accept_ra=2
    sudo sysctl -w net.ipv6.conf.wlan0.accept_ra_rt_info_max_plen=64
    cd connectedhomeip/
    cd examples/all-clusters-app/linux/
    sudo rm -rf /tmp/ch*
    sudo rm -rf /tmp/repl-storage.json
    avahi-browse -rt _matter._tcp
    sudo out/debug/chip-all-clusters-app
    sudo rm -rf /tmp/ch*
    avahi-browse -rt _matter._tcp
    sudo rm -rf /tmp/repl-storage.json
    avahi-browse -rt _matter._tcp
    sudo systemctl restart mdns.service
    avahi-browse -rt _matter._tcp
    sudo systemctl restart avahi-daemon.socket
    avahi-browse -rt _matter._tcp
    avahi-browse -rt _matterc._udp
    sudo out/debug/chip-all-clusters-app
    sudo rm -rf /tmp/repl-storage.json
    sudo rm -rf /tmp/ch*
    sudo systemctl restart avahi-daemon.socket
    avahi-browse -rt _matter._tcp
    sudo out/debug/chip-all-clusters-app
    sudo rm -rf /tmp/repl-storage.json
    sudo rm -rf /tmp/ch*
    sudo systemctl restart avahi-daemon.socket 
   ```
 

# Testing the OTA requestor / Provider

##Terminal 1 (run esp2 ota requestor app)
```
cd connectedhomeip/examples/ota-requestor-app/esp32
idf.py menuconfig #here I set the wifi access point ssid and password
idf.py build
idf.py -p /dev/ttyUSB1 flash monitor
```

##Terminal 2 (run the linux OTA provider)
I create an ota image from the esp32 lighting app and start the linux OTA provider

```
./src/app/ota_image_tool.py create -v 0xDEAD -p 0xBEEF -vn 1 -vs "1.0" -da sha256 examples/lighting-app/esp32/build/ota_data_initial.bin /tmp/esp2-image.bin
./src/app/ota_image_tool.py show /tmp/esp2-image.bin
out/chip-ota-provider-app --discriminator 22 --secured-device-port 5565 --KVS /tmp/chip_kvs_provider --filepath /tmp/esp2-image.bin 

```

##Terminal 3 (run the chip tool)
I join the esp32 OTA-requestor to the fabric and then I join the OTA-provider to the same fabric
I set the appropriate ACL on the OTA provider
I then initiate the sw update on the OTA requestor

```
examples/chip-tool/out/debug/chip-tool pairing onnetwork-long 0x1234567890 20202021 3840
examples/chip-tool/out/debug/chip-tool pairing onnetwork-long 0xDEADBEEF 20202021 22
examples/chip-tool/out/debug/chip-tool accesscontrol write acl '[{"fabricIndex": 1, "privilege": 5, "authMode": 2, "subjects": [112233], "targets": null}, {"fabricIndex": 1, "privilege": 3, "authMode": 2, "subjects": null, "targets": [{"cluster": 41, "endpoint": null, "deviceType": null}]}]' 0xDEADBEEF 0
examples/chip-tool/out/debug/chip-tool otasoftwareupdaterequestor announce-ota-provider 0xDEADBEEF 0 0 0 0x1234567890 0
```


This results in
OTA Provider receiveing QueryImage
Generating an updateToken
Generating an URI: bdx://00000000DEADBEEF//tmp/esp2-image.bin
Sending the response message

However, the esp32 ota-requestor app receives a response but does not show any logging for updating the image or compatible software version

```
chip[DMG]: Received Command Response Data, Endpoint=0 Cluster=0x0000_0029 Command=0x0000_0001
echo-devicecallbacks: PostAttributeChangeCallback - Cluster ID: '0x0000_002A', EndPoint ID: '0x00', Attribute ID: '0x0000_0002'
echo-devicecallbacks: Unhandled cluster ID: 0x0000_002A
```

# Testing on the local linux server using chip-repl and the matter controller code

```
import time, os
import subprocess
import sys
import re
import asyncio
import json

sys.path.append(os.path.abspath("/home/ivob/Projects/mattercloudcontroller/src/component/mcc-daemon/src"))
import iotMatterDeviceController
matterDevices = iotMatterDeviceController.MatterDeviceController(args)

devices = devCtrl.DiscoverCommissionableNodes(filterType=chip.discovery.FilterType.LONG_DISCRIMINATOR, filter=3840, stopOnFirst=True, timeoutSecond=2)
devices[0].Commission(2, 20202021)

nodeId = 2
data = (asyncio.run(devCtrl.ReadAttribute(nodeId, [0, Clusters.Identify])))

jsonStr = matterDevices.jsonDumps(data)

#If you have changed the code base in the DeviceController you can reload it this way

del sys.modules['iotMatterDeviceController']src/component/mcc-daemon/src/iotMatterCloudController.py
import iotMatterDeviceController
matterDevices = iotMatterDeviceController.MatterDeviceController(args)

```

# Testing lightswitch binging to light bulb using chip-repl and the ESP32 (running light bulb) and NRF52840 (running light switch) as per https://github.com/project-chip/connectedhomeip/tree/master/examples/light-switch-app/nrfconnect

```
devices = devCtrl.DiscoverCommissionableNodes(filterType=chip.discovery.FilterType.LONG_DISCRIMINATOR, filter=3840, stopOnFirst=True, timeoutSecond=2)

devices[0].Commission(1, 20202021)

await devCtrl.SendCommand(1, 1, Clusters.OnOff.Commands.On())

devCtrl.CommissionThread(3840, 20202021, 2, bytes.fromhex("0e080000000000010000000300000f35060004001fffe0020811111111222222220708fdac0186760ae20c051000112233445566778899aabbccddeeff030e4f70656e54687265616444656d6f010212340410445f2b5ca6f2a93a55ce570a70efeecb0c0402a0f7f8"))

await devCtrl.ReadAttribute(2, [(0, Clusters.Basic)])

acl = [ Clusters.AccessControl.Structs.AccessControlEntry(
            fabricIndex = 1,
            privilege = Clusters.AccessControl.Enums.Privilege.kAdminister,
            authMode = Clusters.AccessControl.Enums.AuthMode.kCase,
            subjects = [112233] )
            ]

acl.append(Clusters.AccessControl.Structs.AccessControlEntry(
            fabricIndex = 1,
            privilege = Clusters.AccessControl.Enums.Privilege.kAdminister,
            authMode = Clusters.AccessControl.Enums.AuthMode.kCase,
            subjects = [2],
            targets = [
                Clusters.AccessControl.Structs.Target(
                    cluster=6,
                    endpoint = 1,
                ),
                Clusters.AccessControl.Structs.Target(
                    cluster=8,
                    endpoint =1
                )
            ]
        )
    )

await devCtrl.WriteAttribute(1, [ (0, Clusters.AccessControl.Attributes.Acl( acl ) ) ] )

targets = [Clusters.Binding.Structs.TargetStruct(
    fabricIndex = 1,
    node=1,
    endpoint=1,
    cluster=6),
    Clusters.Binding.Structs.TargetStruct(
        fabricIndex = 1,
        node=1,
        endpoint=1,
        cluster=8) ]

await devCtrl.WriteAttribute(2, [ (1, Clusters.Binding.Attributes.Binding( targets ) ) ] )

```


## How to setup the ubuntu environment properly for the matter cloud controller pi

after you have cloned the repo and installed the submodules then

'''
scripts/build_python.sh -m platform -i separate
'''

then on a seperate laptop build the all clusters app variant that has only ipv6 (this is to simulate what will be the most probably interface for all devices post commissioning by other fabric)

'''
./scripts/run_in_build_env.sh "./scripts/build/build_examples.py --target linux-x64-all-clusters-no-ble-asan-clang build"

'''

then we have to 

Activate the Python virtual environment:

'''
source out/python_env/bin/activate
'''

Verify the install by Launching the REPL.

'''
sudo out/python_env/bin/chip-repl
'''


# Preventing  docker image from overwriting the persistent storage

We had 2 options:
Option 1: preventing the host raspberry pi from clear /tmp and mounting the /tmp directory as volume between host and docker container
Option 2: specifying the persistent storage as a file in the /var/tmp directory which is not cleared on reboot

We decided for Option 2 so as not to change the defauld file handling procedures of ubuntu

Option 1
By default the persistent storage (containing info on all commissioned devices) is stored in /tmp/repl-storage.txt. 
When the docker image is restarted the tmp directory is cleared
To avoid this we have pervented the tmp directory being cleared on the host raspberry pi by following these steps:
1. Copied /usr/lib/tmpfiles.d/tmp.conf to /etc/tmpfiles.d/tmp.conf
2. Edited /etc/tmpfiles.d/tmp.conf

changed
D /tmp 1777 root root -
to
d /tmp 1777 root root -

Then we have mounted the \tmp as a volume in the docker compose so that the host and the image container share the same \tmp file
This ensures that 1) the tmp isnt cleared when the raspberry pi is restarted and 2) that the docker image picks up the persisted info on commissioned devices

Option 2:
We specify the persistent storage as a command argument in the python script for the greengrasss component



# Testing the OTA requestor / Provider

##Terminal 1 (run esp2 ota requestor app)
```
cd connectedhomeip/examples/ota-requestor-app/esp32
idf.py menuconfig #here I set the wifi access point ssid and password
idf.py build
idf.py -p /dev/ttyUSB1 flash monitor
```

##Terminal 2 (run the linux OTA provider)
I create an ota image from the esp32 lighting app and start the linux OTA provider

```
./src/app/ota_image_tool.py create -v 0xDEAD -p 0xBEEF -vn 1 -vs "1.0" -da sha256 examples/lighting-app/esp32/build/ota_data_initial.bin /tmp/esp2-image.bin
./src/app/ota_image_tool.py show /tmp/esp2-image.bin
out/chip-ota-provider-app --discriminator 22 --secured-device-port 5565 --KVS /tmp/chip_kvs_provider --filepath /tmp/esp2-image.bin 

```

##Terminal 3 (run the chip tool)
I join the esp32 OTA-requestor to the fabric and then I join the OTA-provider to the same fabric
I set the appropriate ACL on the OTA provider
I then initiate the sw update on the OTA requestor

```
examples/chip-tool/out/debug/chip-tool pairing onnetwork-long 0x1234567890 20202021 3840
examples/chip-tool/out/debug/chip-tool pairing onnetwork-long 0xDEADBEEF 20202021 22
examples/chip-tool/out/debug/chip-tool accesscontrol write acl '[{"fabricIndex": 1, "privilege": 5, "authMode": 2, "subjects": [112233], "targets": null}, {"fabricIndex": 1, "privilege": 3, "authMode": 2, "subjects": null, "targets": [{"cluster": 41, "endpoint": null, "deviceType": null}]}]' 0xDEADBEEF 0
examples/chip-tool/out/debug/chip-tool otasoftwareupdaterequestor announce-ota-provider 0xDEADBEEF 0 0 0 0x1234567890 0
```


This results in
OTA Provider receiveing QueryImage
Generating an updateToken
Generating an URI: bdx://00000000DEADBEEF//tmp/esp2-image.bin
Sending the response message

However, the esp32 ota-requestor app receives a response but does not show any logging for updating the image or compatible software version

```
chip[DMG]: Received Command Response Data, Endpoint=0 Cluster=0x0000_0029 Command=0x0000_0001
echo-devicecallbacks: PostAttributeChangeCallback - Cluster ID: '0x0000_002A', EndPoint ID: '0x00', Attribute ID: '0x0000_0002'
echo-devicecallbacks: Unhandled cluster ID: 0x0000_002A
```

# Testing on the local linux server using chip-repl and the matter controller code

```
import time, os
import subprocess
import sys
import re
import asyncio
import json

sys.path.append(os.path.abspath("/home/ivob/Projects/mattercloudcontroller/src/component/mcc-daemon/src"))
import iotMatterDeviceController
matterDevices = iotMatterDeviceController.MatterDeviceController(args)

devices = devCtrl.DiscoverCommissionableNodes(filterType=chip.discovery.FilterType.LONG_DISCRIMINATOR, filter=3840, stopOnFirst=True, timeoutSecond=2)
devices[0].Commission(2, 20202021)

nodeId = 2
data = (asyncio.run(devCtrl.ReadAttribute(nodeId, [0, Clusters.Identify])))

jsonStr = matterDevices.jsonDumps(data)

#If you have changed the code base in the DeviceController you can reload it this way

del sys.modules['iotMatterDeviceController']src/component/mcc-daemon/src/iotMatterCloudController.py
import iotMatterDeviceController
matterDevices = iotMatterDeviceController.MatterDeviceController(args)

```

# Testing lightswitch binging to light bulb using chip-repl and the ESP32 (running light bulb) and NRF52840 (running light switch) as per https://github.com/project-chip/connectedhomeip/tree/master/examples/light-switch-app/nrfconnect

```
devices = devCtrl.DiscoverCommissionableNodes(filterType=chip.discovery.FilterType.LONG_DISCRIMINATOR, filter=3840, stopOnFirst=True, timeoutSecond=2)

devices[0].Commission(1, 20202021)

await devCtrl.SendCommand(1, 1, Clusters.OnOff.Commands.On())

devCtrl.CommissionThread(3840, 20202021, 2, bytes.fromhex("0e080000000000010000000300000f35060004001fffe0020811111111222222220708fdac0186760ae20c051000112233445566778899aabbccddeeff030e4f70656e54687265616444656d6f010212340410445f2b5ca6f2a93a55ce570a70efeecb0c0402a0f7f8"))

await devCtrl.ReadAttribute(2, [(0, Clusters.Basic)])

acl = [ Clusters.AccessControl.Structs.AccessControlEntry(
            fabricIndex = 1,
            privilege = Clusters.AccessControl.Enums.Privilege.kAdminister,
            authMode = Clusters.AccessControl.Enums.AuthMode.kCase,
            subjects = [112233] )
            ]

acl.append(Clusters.AccessControl.Structs.AccessControlEntry(
            fabricIndex = 1,
            privilege = Clusters.AccessControl.Enums.Privilege.kAdminister,
            authMode = Clusters.AccessControl.Enums.AuthMode.kCase,
            subjects = [2],
            targets = [
                Clusters.AccessControl.Structs.Target(
                    cluster=6,
                    endpoint = 1,
                ),
                Clusters.AccessControl.Structs.Target(
                    cluster=8,
                    endpoint =1
                )
            ]
        )
    )

await devCtrl.WriteAttribute(1, [ (0, Clusters.AccessControl.Attributes.Acl( acl ) ) ] )

targets = [Clusters.Binding.Structs.TargetStruct(
    fabricIndex = 1,
    node=1,
    endpoint=1,
    cluster=6),
    Clusters.Binding.Structs.TargetStruct(
        fabricIndex = 1,
        node=1,
        endpoint=1,
        cluster=8) ]

await devCtrl.WriteAttribute(2, [ (1, Clusters.Binding.Attributes.Binding( targets ) ) ] )

```

