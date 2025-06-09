#!/usr/bin/env python3
# vim:ts=4:sts=4:sw=4:expandtab

#
# openvpn3-indicator - Simple GTK indicator GUI for OpenVPN3.
# Copyright (C) 2024 Grzegorz Gutowski <grzegorz.gutowski@uj.edu.pl>
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License,
# or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.
# If not, see <https://www.gnu.org/licenses/>.
#

import argparse
import os
import pathlib
import re
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--scriptdir', default=os.getcwd())
parser.add_argument('--outdir', default=os.getcwd())
args = parser.parse_args()
scriptdir=pathlib.Path(args.scriptdir)
outdir=pathlib.Path(args.outdir)
gitdir=scriptdir.parent



os.environ['TZ'] = 'UTC'
os.environ['LC_ALL'] = 'en_US.UTF-8'

subprocess.run(['git', 'config', '--global', '--add', 'safe.directory', str(gitdir)])

timestamp_run = subprocess.run(['git', '-C', str(gitdir), 'log', '-n', '1', '--format=format:%cd', '--date=format-local:%Y%m%d%H%M%S'], capture_output=True)
TIMESTAMP = str(timestamp_run.stdout, 'utf-8').strip()

icon_path = gitdir / 'share' / 'icons'
ICON_THEMES = [ str(p.relative_to(icon_path)) for p in icon_path.glob('*') if p.is_dir() ]
ICONS = [ str(p.relative_to(icon_path.parent)) for p in icon_path.glob('**/*.svg') if p.is_file() ]

mime_path = gitdir / 'share' / 'mime'
MIMES = [ str(p.relative_to(mime_path.parent)) for p in mime_path.glob('**/*.xml') if p.is_file() ]

app_path = gitdir / 'share' / 'applications'
APPS = [ str(p.relative_to(app_path.parent)) for p in app_path.glob('**/*.desktop') if p.is_file() ]

man_path = gitdir / 'share' / 'man'
MANS = [ str(p.relative_to(man_path.parent)) for p in man_path.glob('**/*.[1-8]') if p.is_file() ]

NAME      = 'openvpn3-indicator'
VERSION   = f'0.1.{TIMESTAMP}'
RELEASE   = '1' #'1%{?dist}'
SUMMARY   = 'Simple GTK indicator GUI for OpenVPN3'
DESCRIPTION = '''
This project adds a simple GTK indicator application that can be used to control OpenVPN3 tunnels.
It is based on D-Bus interface provided by OpenVPN3 Linux client and does not require elevated privileges to use.
It should be considered as a temporary work-around until Network Manager implements support for OpenVPN 3, or OpenVPN provides a graphical interface for Linux users.
'''
LICENSE   = 'AGPL-3.0'
URL       = 'https://github.com/OpenVPN/openvpn3-indicator'
BUILDARCH = 'noarch'
BUILDREQUIRES = ' '.join(sorted([
        'desktop-file-utils',
        'make',
        'python3',
        'sed',
        'zip',
    ]))
REQUIRES  = ' '.join(sorted([
        'openvpn3-client',
        'python3-dbus',
        'python3-secretstorage',
        'python3-setproctitle',
        'gnome-shell-extension-appindicator',
    ]))

SOURCES = [
    'src',
    'scripts',
    'Makefile',
    'LICENSE',
    'README.md',
    'share',
]
SOURCECODE = outdir / f'openvpn3-indicator-{VERSION}.tar.gz'
source_run = subprocess.run(['tar', '--create', '--auto-compress', '--file', SOURCECODE, '--transform', f'flags=r;s|^|openvpn3-indicator-{VERSION}/|', '--directory', str(gitdir) ] + SOURCES)

PREP = '\n'.join([
        '%setup'
    ])

BUILD = '\n'.join([
        'make DESTDIR=%{buildroot} BINDIR=%{_bindir} DATADIR=%{_datadir} HARDCODE_PYTHON=/usr/bin/python3 all',
    ])

INSTALL = '\n'.join([
        'make DESTDIR=%{buildroot} BINDIR=%{_bindir} DATADIR=%{_datadir} package',
    ] + [
        'desktop-file-validate %{buildroot}%{_datadir}/'+path for path in APPS
    ])

POST = '\n'.join([
        'touch --no-create %{_datadir}/icons/'+theme+' || :' for theme in ICON_THEMES
    ] + [
        'xdg-mime install --mode system %{_datadir}/'+mime for mime in MIMES
    ])

POSTTRANS = '\n'.join([
        'update-desktop-database %{_datadir}/applications || :',
        'update-mime-database %{_datadir}/mime || :',
    ] + [
        'gtk-update-icon-cache --silent %{_datadir}/icons/'+theme+' || :' for theme in ICON_THEMES
    ])

PREUN = '\n'.join([
        'xdg-mime uninstall --mode system %{_datadir}/'+mime for mime in MIMES
    ])

POSTUN = '\n'.join([
        'update-desktop-database %{_datadir}/applications || :',
        'update-mime-database %{_datadir}/mime || :'
    ] + [
        'touch --no-create %{_datadir}/icons/'+theme+' || :' for theme in ICON_THEMES
    ] + [
        'gtk-update-icon-cache --silent %{_datadir}/icons/'+theme+' || :' for theme in ICON_THEMES
    ])

FILES = '\n'.join([
        '%license LICENSE',
        '%doc README.md',
        '%{_bindir}/%{name}',
        '/etc/xdg/autostart/%{name}.desktop'
    ] + [
        '%{_datadir}/'+path for path in APPS + ICONS + MIMES
    ] + [
        '%{_datadir}/'+path+'.gz' for path in MANS
    ])


changelog_run = subprocess.run(['git', '-C', str(gitdir), 'log', '-n', '1', '--format=format:* %cd %an <%ae> - '+VERSION+'-'+re.sub(r'%','%%',RELEASE)+'%n- %s%b%n', '--date=format-local:%a %b %d %Y'], capture_output=True)
CHANGELOG = str(changelog_run.stdout, 'utf-8').strip()

(outdir / 'openvpn3-indicator.spec').write_text(f'''
Name: {NAME}
Version: {VERSION}
Release: {RELEASE}
Summary: {SUMMARY}
License: {LICENSE}
URL: {URL}
BuildArch: {BUILDARCH}
BuildRequires: {BUILDREQUIRES}
Requires: {REQUIRES}
Source: {SOURCECODE}

%description

{DESCRIPTION}

%prep

{PREP}

%build

{BUILD}

%install

{INSTALL}

%post

{POST}

%posttrans

{POSTTRANS}

%preun

{PREUN}

%postun

{POSTUN}

%files

{FILES}

%changelog

{CHANGELOG}

''')
