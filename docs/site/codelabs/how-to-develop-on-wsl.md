summary: How to Develop for Matter on WSL
id: how-to-develop-on-wsl
categories: Sample
tags: matter
status: Published 
authors: MatterCoder
Feedback Link: https://mattercoder.com

# How to Develop Matter on WSL2
<!-- ------------------------ -->
## Overview 
Duration: 25

In this codelab we will show you how to set up windows for developing Matter using Windows Subsystem for Linux (WSL)

### What You’ll Build 
In this codelab, you will:
- Enable WSL2 on windows
- Set up support for USB to WSL2
- Set up support for mDNS (service discovery)


### What You’ll Learn 
- What you will need (Pre-requisities)
- How to enable WSL2 on Windows
- How to set up support for USB in WSL2
- How to set up mDNS supoort (for service discovery)

<!-- ------------------------ -->
## What you will need (Pre-requisities)
Duration: 2

This set of Codelabs will use `Ubuntu 22.04` on a windows 10 architecture. If you are using Mac OS then you should follow the instructions directly from the [Matter repo](https://github.com/project-chip/connectedhomeip/blob/master/docs/guides/BUILDING.md)

You will need
- a laptop or PC running Windows 10 
- a basic knowledge of Linux shell commands

The total codelab will take approximately a `Duration of 30 minuates` to complete. 

<!-- ------------------------ -->
## How to enable WSL2 on Windows
Duration: 5

To install WSL 2 on Windows 10 OS Build 2004 or later you can open a command prompt (with Administrator permissions) and type in the following command:

```shell
wsl.exe --install
```

Once done, reboot your computer. Log in to Windows 10 and the command prompt will open again. This time you’ll be walked through setting up Ubuntu with a username and password (these don’t need to be the same as your Windows username and password).

Once done you can you can launch the ‘Ubuntu’ app from the Start Menu to get started, or install the Microsoft Terminal app to start exploring your newly-installed Ubuntu install — don’t forget to run an apt update && apt upgrade though — this is a REAL Ubuntu system, after all!

<!-- ------------------------ -->
## How to set up support for USB in WSL2
Duration: 5

## Steps to attach your USB device to the WSL2

Every time an USB device is connected to your PC, you need to do the following steps to make it available for WSL2. You need to share the device on Windows with usbipd first, and attach the shared device to WSL2 with usbip.

#### On Windows

1. Make sure the usbipd server is running on Windows. You can do this by either:

1. Make sure the Windows service `USBIP Device Host` is still running (Right Click `This PC` -> Management -> Service). Usually the service that is always running, but sometimes it crashes and cannot recover quickly. I recommend to execute the server in Powershell command instead. (see below)

2. Run `usbipd server` in Powershell can also run the server, but the console needs to be kept open. I think this is more convenient than the Windows service: you can see if the server is running in command line, and disconnect the devices by terminating the server at any time (CTRL+C), or recover the server quickly.

2. Run `usbipd list` in Windows powershell to see all your USB devices. Remember the BUSID of the desired USB device.

Note: here you will see all the USB devices of this PC. Devices with `Shared` state will be available for WSL2 to attach. Devices with `Attach` state is already attached by WSL2, and cannot be attached by other users.

3. Share your USB device on Windows. Run `usbipd bind -b [busid]` to share the desired device.

Note: step 2 and 3 only needs to be performed once. After this step, the same device connected to the same physical port will be automatically binded (shared). If WSL2 cannot attach any device, check if the usbipd server is running on Windows (step 1).


#### On WSL2

1. Get the ip of Windows system by running `ip route` in WSL2. You will see:
```
$ ip route
default via 172.22.80.1 dev eth0
172.22.80.0/20 dev eth0 proto kernel scope link src 172.22.88.162
```
The ip shown in the default line is the IP of the Windows. You can also get this IP easily by alias a command (`alias win_ip='ip route | grep default | awk '\''{print $3}'\'''`).

2. Check the binded (shared) devices on Windows by running `sudo usbip list -r [windows_ip]`. You will see:
```
$ sudo usbip list -r 172.22.80.1
Exportable USB devices
======================
- 172.22.80.1
1-1: Silicon Labs : CP210x UART Bridge (10c4:ea60)
: USB\VID_10C4&PID_EA60\88E1A435661CEC11AA7FA08DF01C6278
: (Defined at Interface level) (00/00/00)
: 0 - Vendor Specific Class / unknown subclass / unknown protocol (ff/00/00)
```
Here 1-1 is the busid of the device. I guess it will also keep the same value, for the same devices connected to the same physical port.

3. Attach the device to WSL2 by `sudo usbip attach -r [windows_ip] -b [bus_id]`. You can do this easily by alias command (`alias usbc='sudo usbip attach -r $(win_ip) -b '`), and run `usbc 1-1`.

4. You will see your USB device disappear from the Windows device manager. Now you can see the USB devices in WSL2 by calling `dmesg | grep tty`, `lsusb` or `ls /dev | grep ttyUSB*`.

#### Troubleshooting

1. If you see `usbipd: error: Server is currently not running.`, or steps in `On WSL2` is blocked without any log, it means the usbipd server is not running. Go back to `On Windows` step 1, run usbipd server and try again.

2. (Windows 10) If you see information like: `USBIPD is not supported on WSL2`, or `Using wrong WSL version`, it may mean that, the kernel you are using doesn't have the USB support. Go back to `Recompile and replace the WSL2 kernel with USB support` and try it again.

<!-- ------------------------ -->
## How to set up mDNS supoort (for service discovery)
Duration: 2

You will need to set up support for service discovery mDNS which is used by matter devices during commissioning

1. We run these commands

```shell
sudo service dbus start
sudo service avahi-daemon start
```

2. Next we will check that the services are running

```shell
/etc/init.d/dbus status
/etc/init.d/avahi-daemon status
```

Note: you may need to run this everytime you restart your WSL2 instance



