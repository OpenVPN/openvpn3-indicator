# ![logo](https://raw.githubusercontent.com/OpenVPN/openvpn3-indicator/main/share/icons/hicolor/scalable/apps/openvpn3-indicator.svg) openvpn3-indicator

Simple indicator application for OpenVPN3.

## Description

This is a simple indicator application that controls OpenVPN3 tunnels.
It is based on D-Bus interface provided by OpenVPN3 Linux client.
It is a temporary solution until Network Manager supports OpenVPN3.

## Example use

[![example](https://raw.githubusercontent.com/OpenVPN/openvpn3-indicator/main/docs/example.png)](https://raw.githubusercontent.com/OpenVPN/openvpn3-indicator/main/docs/example.webm)

https://github.com/OpenVPN/openvpn3-indicator/assets/5970093/b9245e81-7896-4b53-b2c2-e03e00cbc35c

## Prerequisites

This application requires the installation of `openvpn3-linux` (https://github.com/OpenVPN/openvpn3-linux).
There are [pre-built packages](https://community.openvpn.net/openvpn/wiki/OpenVPN3Linux) prepared for popular distributions by OpenVPN.

## Installation instructions (from repositories)

Package `openvpn3-indicator` can be installed on popular Linux distributions using the provided repositories.

### Ubuntu

Packages are hosted in [Ubuntu Launchpad repository](https://launchpad.net/~grzegorz-gutowski/+archive/ubuntu/openvpn3-indicator) .
Installation instructions:

```sh
sudo add-apt-repository ppa:grzegorz-gutowski/openvpn3-indicator
sudo apt install openvpn3-indicator
```

### Fedora + RHEL

Packages are hosted in [Fedora Copr repository](https://copr.fedorainfracloud.org/coprs/grzegorz-gutowski/openvpn3-indicator/) .
Installation instructions:

```
sudo dnf copr enable grzegorz-gutowski/openvpn3-indicator
sudo dnf install openvpn3-indicator
```

## Installation instructions (from sources)

### Prerequisites

Application requires some standard python libraries that are usually present in desktop installations.
On Ubuntu/Debian systems it should be enough to use the following install command:
```sh
sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1 python3-secretstorage python3-setproctitle
```
On Fedora:
```sh
sudo dnf install python3-secretstorage python3-setproctitle gnome-shell-extension-appindicator
```

### Installation

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
