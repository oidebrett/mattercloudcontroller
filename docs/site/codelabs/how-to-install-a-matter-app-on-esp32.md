summary: How to install a matter app on esp32
id: how-to-install-a-matter-app-on-esp32
categories: Sample
tags: matter
status: Published 
authors: MatterCoder
Feedback Link: https://mattercoder.com

# How to Install a Matter sample app on esp32
<!-- ------------------------ -->
## Overview 
Duration: 25

In this codelab we will show you how to build and install a Matter sample app on the ESP32.

### What You’ll Build 
In this codelab, you will:
- Build a sample Matter Accessory on the ESP32
- Use the chip-tool as a Matter controller to controller the accessory.

### Architecture
![alt-architecture-here](assets/matter_esp32_setup.png)

in this CodeLab we will run the Matter Accessory on an ESP32 microcontroller and the Matter Controller on a Linux Host. This will allow us to create a simple Matter Network very quickly and we will learn how to commission Matter devices over BLE.

### What You’ll Learn 
- What you will need (Pre-requisities)
- Where to get the latest version of ESP-IDF toolchain
- How to build a sample matter app on the ESP32
- Basic testing with sample app and chip-tool

<!-- ------------------------ -->
## What you will need (Pre-requisities)
Duration: 2

This set of Codelabs will use `Ubuntu 22.04` on a Amd64 based architecture.

You will need
- an ESP32 microcontroller. ESP32 DEV KIT C
- a laptop or PC running `Ubuntu 22.04` with a Bluetooth interface
- Visual Studio Code IDE
- a basic knowledge of Linux shell commands

The total codelab will take approximately a `Duration of 30 minuates` to complete. 

<!-- ------------------------ -->
## Where to get the latest version of ESP-IDF 
Duration: 2

A guide on how to install ESP-IDF is available on the [Espressif's Matter SDK repo](https://docs.espressif.com/projects/esp-matter)

1. First thing we will do is create a new folder so that we can clone the code

```shell
cd ~
mkdir Project
cd Project
```

2. Next we will clone the ESP-IDF github repo. Note the latest version at the time of writing is below. Upgrading to the latest version is recommended.

```shell
git clone --recursive https://github.com/espressif/esp-idf.git
cd esp-idf; git checkout v5.1.2; git submodule update --init --recursive;
./install.sh
cd ..
```

3. If you have not already done so, you will need top ensure that the Matter ConnectedHomeIP SDK is installed. Do this in the Projects directory.
```shell
git clone --depth 1 https://github.com/espressif/esp-matter.git
cd esp-matter
git submodule update --init --depth 1
cd ..
```

4. Next set up the ESP Matter SDK and the ESP-IDF environments (you should do this step everytime you open a new terminal)

```shell
cd esp-idf
source ./export.sh
cd ..
cd esp-matter
source ./export.sh
```

5. Next we will install the required submodules

### For Linux host:

```shell
cd ./connectedhomeip/connectedhomeip
./scripts/checkout_submodules.py --platform esp32 linux --shallow
cd ../..
./install.sh
cd ..
```

### For Mac OS-X host:

```shell
cd ./connectedhomeip/connectedhomeip
./scripts/checkout_submodules.py --platform esp32 darwin --shallow
cd ../..
./install.sh
cd ..
```

Note: this process can take a while the very 1st time you install matter.


Before building our Matter controller and sample app, we need to install a few OS specific dependencies.


<!-- ------------------------ -->
## How to build a sample matter app for the ESP32 microcontroller
Duration: 10

In this section we will build a sample matter app for the ESP32. 
We will use the sample `Light_switch app` which has all the main capabilities of a matter light switch end device. 

We have previously built the matter controller tool that is provided by Project-Chip. You will need
to go back and complete that codelab

1. We will build the matter application for esp

Run the following commands
```shell
cd ~/Projects/esp-mattee
cd examples/light_switch/
idf.py set-target esp32
```

2. We will confirm the esp build configuration using the idf.py menuconfig command

```shell
idf.py menuconfig
```

3. We then can build the required sample apps using the following commands

```shell
idf.py build
```

4. If everything worked OK you should see an  Executable Linkable Format file called `light_switch.elf` in the `build` directory

Note: if you run into any difficulties in can be useful to clean up the temporary build folder using `rm -rf build` as this can often solve some build issues.

5. Adding User to dialout or uucp on Linux
The currently logged user should have read and write access the serial port over USB. On most Linux distributions, this is done by adding the user to dialout group with the following command:

```shell
sudo usermod -a -G dialout $USER
```

6. You will then flash the image on to the ESP32. But its good practice to erase the flash before hand.

```shell
idf.py -p /dev/ttyUSB0 erase_flash
idf.py -p /dev/ttyUSB0 flash monitor 
```

<!-- ------------------------ -->
## Basic testing with ESP32 sample app and chip-tool
Duration: 10

In this section we will run a ESP32 matter loight application (light switch app) and control with an administrative
tool called the chip-tool that acts as a matter controller.

### Running the CHIP Tool
Firstly we will check if the CHIP Tool runs correctly. Execute the following command in the connectedhomeip directory:

```shell
./out/host/chip-tool
```

As a result, the CHIP Tool will print all available commands. These are called clusters in this context, but not all listed commands correspond to the clusters in the Data Model (for example, pairing or discover commands).

### Using the CHIP Tool
1. Clean the initialization of state using the following command:
```shell
rm -fr /tmp/chip_*
```
Note: removing the /tmp/chip* files can sometimes clear up unexpected behaviours.

2. In the same shell window, try to commission the matter accessory using the the CHIP Tool. Commissioning is what we call the 
process of bringing a Matter Node into a Matter Fabric. We will explain all of these terms in a further codelab. Essentially, we are creating a secure relationship between the Matter Controller (chip-tool) and the Matter Accessory (light switch app).

```shell
./out/host/chip-tool pairing ble-wifi ${NODE_ID_TO_ASSIGN} ${SSID} ${PASSWORD} 20202021 3840
```

If everything is working you should see output logs and you should see that the commissioning was successful

```shell
[1683309736.149316][15:17] CHIP:CTL: Successfully finished commissioning step 'Cleanup'
[1683309736.149405][15:17] CHIP:TOO: Device commissioning completed with success
```

3. Now that we have created a secure relationship by "commissioning" the matter accessory we will now do some simple interaction with the Matter Accessory using the chip-tool as a Matter controller. We will get into further details  of the "interaction model" and "data model" of Matter in later codelabs. But for now, we will do some simple interactions.

In the same shell window, we will read the vendor-name of the Matter accessory using the following command:

```shell
./out/host/chip-tool basicinformation read vendor-name 1 0
```

In the output logs, you should see that the Vendor Name

```shell
[1682445848.220725][5128:5130] CHIP:TOO:   VendorName: TEST_VENDOR
```

4. We can read other information using these commands:
```shell
./out/host/chip-tool basicinformation read product-name 1 0
./out/host/chip-tool basicinformation read software-version 1 0
```

We are using the Basic Information `cluster`. Clusters are logical groupings of Matter functionality.

5. We can read other information from another cluster (General Diagnostics) using these commands:
```shell
./out/host/chip-tool generaldiagnostics read reboot-count 1 0
```

In the output logs, you should see the Reboot Count. Try rebooting the ESP32 by pressing the "EN" button and check that the reboot count increments accordingly.

```shell
[1707327931.613546][60834:60836] CHIP:TOO:   RebootCount: 3
```

6. You can find out the other different clusters that are supported by the chip-tool by running:
```shell
./out/host/chip-tool 
```

### Cleaning Up
You should stop the monitor by using Ctrl-] in the esp32 monitor window and erase the esp32 flash.

It also a great habit to clean up the temporary files after you finish testing by using this command:
```shell
rm -fr /tmp/chip_*
```
Note: removing the /tmp/chip* files can sometimes clear up unexpected behaviours.


<!-- ------------------------ -->
## Further Information
Duration: 1

Checkout the official documentation [Espressif Matter SDK documentation here: ] (https://docs.espressif.com/projects/esp-matter/en/latest/esp32/)

Also check out the Project CHIP Matter SDK repo [Project Chip - ConnectedHomeIp](https://github.com/project-chip/connectedhomeip/tree/master/docs)

