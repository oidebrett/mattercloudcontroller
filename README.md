# mattercloudcontroller

# Working with Matter Cloud Controller (Python)

The Matter Cloud Controller is a python based tool that allows you to commission a Matter device
(via the cloud) into the network and to communicate with it using the Zigbee Cluster Library
(ZCL) messages.

<hr>

-   [Building The Cloud Controller Tool](#building)

<hr>

<a name="building"></a>

## Building and installing

Before you can use the Matter cloud controller, you must install chip tool wheel package
from https://github.com/nrfconnect/sdk-connectedhomeip.

> To ensure compatibility, build the Matter Cloud controller and the Matter
> device from the same revision of the connectedhomeip repository.

To build and run the Matter Cloud controller:

1. Build and install the Python CHIP controller:

    ```
    scripts/build_controller.sh
    ```

    > Note: To get more details about available build configurations, run the
    > following command: `scripts/build_controller.sh --help`

<hr>

<a name="running"></a>

## Running the tool

1. Activate the Python virtual environment:

    ```
    source ./env/bin/activate
    ```

2. Run the Matter Cloud controller with root privileges, which is required to
   obtain access to the Bluetooth interface:

    ```
    python3 local-chip-device-ctrl.py
    ```
