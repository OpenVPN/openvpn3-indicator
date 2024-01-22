# openvpn3-indicator

Simple GTK indicator GUI for OpenVPN3.

## Description

This project adds a simple GTK indicator that can be used to control OpenVPN3 tunnels.
It is based on D-Bus interface provided by OpenVPN3 Linux client and does not require elevated provileges to use.
It should be considered as a temporary work-around until Network Manager implements support for OpenVPN 3.

## Prerequisites

To use this project you have to install `openvpn3-linux` (https://github.com/OpenVPN/openvpn3-linux).
You can use [pre-built packages](https://community.openvpn.net/openvpn/wiki/OpenVPN3Linux) for popular distributions.
You also need afe python libraries that are usually present in usual desktop installations.

## Installation instructions

You can use provided `Makefile` to install the program in `/usr`.

```sh
make -B install
```

## Usage instructions

Simply click the indicator icon to control OpenVPN3 tunnels: import configurations, connect, pause, resume, and disconnect sessions.
