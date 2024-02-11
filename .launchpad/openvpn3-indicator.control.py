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
parser.add_argument('--distro', default='jammy')
args = parser.parse_args()
scriptdir=pathlib.Path(args.scriptdir)
outdir=pathlib.Path(args.outdir)
gitdir=scriptdir.parent

DISTROS = ['focal','jammy','mantic','noble']


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


for DISTRO in DISTROS:

    NAME      = 'openvpn3-indicator'
    MAINTAINER = 'Grzegorz Gutowski <grzegorz.gutowski@uj.edu.pl>'
    PRIORITY  = 'optional'
    SECTION   = 'net'
    VERSION   = f'0.1.{TIMESTAMP}'
    RELEASE   = DISTRO
    SUMMARY   = 'Simple GTK indicator GUI for OpenVPN3'
    DESCRIPTION = '''This project adds a simple GTK indicator application that can be used to control OpenVPN3 tunnels.
It is based on D-Bus interface provided by OpenVPN3 Linux client and does not require elevated privileges to use.
It should be considered as a temporary work-around until Network Manager implements support for OpenVPN 3, or OpenVPN provides a graphical interface for Linux users.
'''
    LICENSE   = 'AGPL-3.0'
    URL       = 'https://github.com/grzegorz-gutowski/openvpn3-indicator'
    BUILDARCH = 'noarch'
    COMPAT = '10'
    BUILDREQUIRES = [
            'desktop-file-utils',
            'make',
            'sed',
            f'debhelper (>= {COMPAT})',
        ]
    REQUIRES  = [
            'openvpn3',
            'python3-dbus',
            'python3-secretstorage',
            'python3-gi',
            'gir1.2-ayatanaappindicator3-0.1',
        ]

    SOURCES = [
        'openvpn3-indicator',
        'Makefile',
        'LICENSE',
        'README.md',
        'share',
    ]
    SOURCECODE = outdir / f'openvpn3-indicator_{VERSION}.orig.tar.gz'
    SOURCECODE.parent.mkdir(parents=True, exist_ok=True)
    source_run = subprocess.run(['tar', '--create', '--auto-compress', '--file', SOURCECODE, '--transform', f'flags=r;s|^|openvpn3-indicator-{VERSION}/|', '--directory', str(gitdir) ] + SOURCES)

    PREP = '\n'.join([
            '%setup'
        ])

    BUILD = '\n'.join([
            'make DESTDIR=%{buildroot} BINDIR=%{_bindir} DATADIR=%{_datadir} all',
        ] + [
            'desktop-file-validate %(buildroot}%{_datadir}'+path for path in APPS
        ])

    INSTALL = '\n'.join([
            'make DESTDIR=%{buildroot} BINDIR=%{_bindir} DATADIR=%{_datadir} package',
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

    NEWLINE='\n'

    changelog_run = subprocess.run(['git', '-C', str(gitdir), 'log', '-n', '1', '--format=format:'+NAME+' ('+VERSION+'-'+re.sub(r'%','%%',RELEASE)+') '+DISTRO+'; urgency=medium%n%n  * %s%b%n%n -- %an <%ae>  %cd', '--date=format-local:%a, %d %b %Y %H:%M:%S +0000'], capture_output=True)
    CHANGELOG = str(changelog_run.stdout, 'utf-8').strip()

    pkgdir = outdir / f'openvpn3-indicator-{VERSION}'

    debdir = pkgdir / 'debian'

    debdir.mkdir(parents=True, exist_ok=True)

    (debdir / 'control').write_text(
f'''Source: {NAME}
Maintainer: {MAINTAINER}
Priority: {PRIORITY}
Section: {SECTION}
Build-Depends: {", ".join(sorted(BUILDREQUIRES))}
Standards-Version: 4.0.0
Homepage: {URL}

Package: {NAME}
Architecture: all
Depends: {", ".join(sorted(REQUIRES))}
Description: 
{NEWLINE.join(["  "+line for line in DESCRIPTION.split(NEWLINE)])}
''')
    (debdir / 'source').mkdir(parents=True, exist_ok=True)
    (debdir / 'source' / 'format').write_text(
f'''3.0 (quilt)
''')
    (debdir / 'rules').write_text(re.sub(r'    ','\t',
f'''#!/usr/bin/make -f
clean:

build:
    make DESTDIR=debian/{NAME} BINDIR=/usr/bin DATADIR=/usr/share all

binary:
    make DESTDIR=debian/{NAME} BINDIR=/usr/bin DATADIR=/usr/share package
    dh_gencontrol
    dh_builddeb
'''))
    (debdir / 'changelog').write_text(
f'''{CHANGELOG}
''')
    (debdir / 'compat').write_text(
f'''{COMPAT}
''')
    (debdir / 'copyright').write_text( (gitdir / 'LICENSE').read_text() )

    subprocess.run(['dpkg-buildpackage', '-us', '-uc', '-ui', '-S'], cwd=pkgdir)
