# ![logo](https://raw.githubusercontent.com/grzegorz-gutowski/openvpn3-indicator/main/share/icons/hicolor/scalable/apps/openvpn3-indicator.svg) openvpn3-indicator

Simple GTK indicator GUI for OpenVPN3.

## Description

This project adds a simple GTK indicator application that can be used to control OpenVPN3 tunnels.
It is based on D-Bus interface provided by OpenVPN3 Linux client and does not require elevated privileges to use.
It should be considered as a temporary work-around until Network Manager implements support for OpenVPN 3, or OpenVPN provides a graphical interface for Linux users.

## Prerequisites

This application requires the installation of `openvpn3-linux` (https://github.com/OpenVPN/openvpn3-linux).
There are [pre-built packages](https://community.openvpn.net/openvpn/wiki/OpenVPN3Linux) prepared for popular distributions by OpenVPN.

It also requires some standard python libraries that are usually present in desktop installations.
On Ubuntu/Debian systems it should be enough to use the following install command:
```sh
sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1 python3-secretstorage
```
On Fedora:
```sh
sudo dnf install python3-secretstorage gnome-shell-extension-appindicator
```

## Installation instructions

You can use provided `Makefile` to install the application in `/usr/local` for all users.

```sh
sudo make install
```

You can also install symlinks to the current directory in `~/.local/` for the current user only.
This is the way for developers, as it allows easy modifications of the application.

```sh
make devel
```

You can uninstall the application by running `sudo make uninstall` or `make undevel`.

## Usage instructions

Simply click the indicator icon to control OpenVPN3 tunnels: import configurations, connect, pause, resume, and disconnect sessions.
