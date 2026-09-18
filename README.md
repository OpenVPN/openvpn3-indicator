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
This software is packaged on recent Linux distributions usually in the package named `openvpn3-client`.
There are also [pre-built packages](https://community.openvpn.net/openvpn/wiki/OpenVPN3Linux) prepared for popular distributions by OpenVPN.

## Installation instructions (from standard repositories)

Package `openvpn3-indicator` can be installed on some recent Linux distributions using standard repositories.

### Ubuntu

Since Ubuntu stonking, `openvpn3-indicator` is packaged in `universe` repository and can be installed using
```sh
sudo apt install openvpn3-indicator
```

### Debian

Since Debian forky, `openvpn3-indicator` is packaged in standard repository and can be installed using
```sh
sudo apt install openvpn3-indicator
```
For Debian trixie the package is available in the [Fast Forward](https://fastforward.debian.net) repository.

## Installation instructions (from development repositories)

We provide package repositories with the latest development version of `openvpn3-indicator` for Ubuntu and Fedora users.

### Ubuntu

Packages are hosted in [Ubuntu Launchpad repository](https://launchpad.net/~grzegorz-gutowski/+archive/ubuntu/openvpn3-indicator).
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

By default a single tray icon represents all connections. Its colour follows the overall state: grey while nothing is connected, orange while a connection is being established, coloured once a connection is up. Every imported configuration has its own submenu; a connected one carries a check mark, a paused, connecting or failed one a marker in its label (⏸ … ✗), and its submenu offers Pause, Resume, Restart and Disconnect.

If you prefer one tray icon per running connection, choose *Tray Icon Settings → One Icon per Connection* in the menu, or run:

```
gsettings set net.openvpn.openvpn3_indicator indicator-mode per-session
```

If the tray icon ever disappears while the application is still running (for example after your desktop's tray support was restarted), start `openvpn3-indicator` again: the running instance re-creates its tray icons instead of starting a second copy. `openvpn3-indicator --repair` does the same from a script.
