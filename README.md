# Matter Cloud Controller (Python)

The Matter Cloud Controller is a python based tool that allows you to commission a Matter device (via the cloud) into the network and to communicate with it using the Zigbee Cluster Library (ZCL) messages.

# Control Device Setup

1. On raspberry pi 4 (4GB). Download Ubuntu Server 21.10 using RPI imager on a 64 GB micro SD card. Note 21.04 is no longer available.

2. Follow build instructions "Building Matter" from GitHub.com/NRFConnect/sdk-connectedhomeip
Note: ensure that the versions are aligned between nrf app and chip controller
e.g. if nrf version is v1.9.0 then git checkout v1.9.0 of sdk-connectedhomeip

2.1 In order to speed up the compilation and reduce risk of pi hanging you might consider adding 4GB as swap as per https://www.linuxtut.com/en/71e3874cb83ed12ec405/

3. Ensure router advertising is enabled on raspberry pi controller
```
sudo sysctl -w net.ipv6.conf.wlan0.accept_ra=2
sudo sysctl -w net.ipv6.conf.wlan0.accept_ra_rt_info_max_plen=64
```
4. If having difficulties try these steps:

Remove temp files
```
sudo rm -rf /tmp/chip*
```

Clear out MDNS cache on OTBR
```
sudo systemctl restart mdns.service 
```

Clear out avahi MDNS cache on Raspberry Pi
```
sudo systemctl restart avahi-daemon.socket 
```

# The stack provisioning is loosely based on "AWS IoT Greengrass OnBoarding and Data Logging using AWS CDK" https://github.com/aws-samples/aws-iot-greengrass-v2-using-aws-cdk

## Solution Architecture

- Thing Installer: provide Greengrass ver2 Installer with a customized IAM Role(output-thing-installer-stack-MCCDev.json)
- Component Upload/Deployments: deploy component's logic(sampl)

![solution-arcitecture](docs/asset/solution-architecture.png)
