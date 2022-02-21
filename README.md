# Matter Cloud Controller (Python)

The Matter Cloud Controller is a python based tool that allows you to commission a Matter device
(via the cloud) into the network and to communicate with it using the Zigbee Cluster Library
(ZCL) messages.

<hr>

-   [Building The Cloud Controller Tool](#building)

<hr>

<a name="building"></a>

## Building and installing

Before you can use the Matter cloud controller, you must install chip tool wheel package
from the NRFConnect SDK ConnectedHomeIp repository. The script below will do this automatically.

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
    
2. Install the NPM and Upgrade Node version if necessary (see https://www.digitalocean.com/community/tutorials/how-to-install-node-js-on-ubuntu-20-04)
    ```
    sudo apt install npm
    ```

3. Install Docker on the Raspberry Pi by following these instructions: https://brjapon.medium.com/setting-up-ubuntu-20-04-arm-64-under-raspberry-pi-4-970654d12696
    - install docker
    - install docker-compose

4. When bootstrapping CDK you may need to use flag --public-access-block-configuration if you AWS account is not permitted to make s3 public access buckets.

    ```
    --public-access-block-configuration false
    ```

4. Run the Matter Cloud controller with root privileges, which is required to
   obtain access to the Bluetooth interface:

    ```
    python3 local-chip-device-ctrl.py
    ```
