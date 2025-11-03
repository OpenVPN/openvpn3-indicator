PROGRAM := openvpn3-indicator
DESTDIR ?=
PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
DATADIR ?= $(PREFIX)/share
AUTOSTART ?= /etc/xdg/autostart
VERSION ?= $(shell git log -n 1 --format=format:devel-%cd-%h  --date=format-local:%Y%m%d%H%M%S)
PREPAREDIR ?= build/prepare

DESTDIR := $(DESTDIR:/=)
PREFIX := $(PREFIX:/=)
BINDIR := $(BINDIR:/=)
DATADIR := $(DATADIR:/=)
AUTOSTART := $(AUTOSTART:/=)
PREPAREDIR := $(PREPAREDIR:/=)

SOURCES := $(shell find src -iname tests -prune -o -iname __pycache__ -prune -o -iname about.py -o -type f -print)
ABOUT := $(shell find src -type f -iname about.py)
SHARES := $(shell find share -type f -not -iname "*.[1-8]" -not -iname "*.desktop" -not -iname "*.bak" -not -iname "*.swp")
SHARES := $(patsubst share/%,%,$(SHARES))
MANS := $(shell find share -type f -iname "*.[1-8]")
MANS := $(patsubst share/%,%,$(MANS))
APPLICATION := $(shell find share -type f -iname "*.desktop")
APPLICATION := $(patsubst share/%,%,$(APPLICATION))

PREPARE_SOURCES := $(patsubst src/%,$(PREPAREDIR)/%,$(SOURCES))
PREPARE_ABOUT := $(patsubst src/%,$(PREPAREDIR)/%,$(ABOUT))

INSTALL_SHARES := $(patsubst %,$(DESTDIR)$(DATADIR)/%,$(SHARES))

INSTALL_SHARES := $(patsubst %,$(DESTDIR)$(DATADIR)/%,$(SHARES))
INSTALL_MANS := $(patsubst %,$(DESTDIR)$(DATADIR)/%.gz,$(MANS))
INSTALL_APPLICATION := $(patsubst %,$(DESTDIR)$(DATADIR)/%,$(APPLICATION))
INSTALL_AUTOSTART := $(DESTDIR)$(AUTOSTART)/$(PROGRAM).desktop

DEVEL_SHARES := $(patsubst %,$(HOME)/.local/share/%,$(SHARES))
#DEVEL_MANS := 
DEVEL_APPLICATION := $(patsubst %,$(HOME)/.local/share/%,$(APPLICATION))
DEVEL_AUTOSTART := $(HOME)/.config/autostart/$(PROGRAM).desktop

.PHONY: default
default:
	@echo "This is Makefile for $(PROGRAM). It does nothing by default."
	@echo
	@echo "Use  ***  sudo make install  ***  to install $(PROGRAM) in $(PREFIX) for all users."
	@echo
	@echo "Use  ***  make devel  ***  to install symlinks to $(PROGRAM) in the current folder for the current user only."
	@echo "This is the way for developers."
	@echo
	@echo "Use  ***  sudo make uninstall  ***  or  ***  make undevel  ***  to uninstall $(PROGRAM)."
	@echo
	@echo "Use  ***  make DESTDIR=debian/openvpn3-indicator BINDIR=/usr/bin DATADIR=/usr/share HARDCODE_PYTHON=/usr/bin/python3 package  ***  to build for packaging."
	@echo
	@echo "Program version is $(VERSION)"
	@echo

.PHONY: all
all: $(PROGRAM)


$(PROGRAM): $(PREPARE_SOURCES) $(PREPARE_ABOUT) Makefile scripts/build_executable
ifeq ($(HARDCODE_PYTHON),)
	scripts/build_executable --directory $(PREPAREDIR) --executable $@
else
	scripts/build_executable --directory $(PREPAREDIR) --executable $@ --python $(HARDCODE_PYTHON)
endif

$(PREPARE_SOURCES): $(PREPAREDIR)/% : src/%
	@install --directory $(dir $@)
	install --mode 0644 $< $@

$(PREPARE_ABOUT): $(PREPAREDIR)/% : src/%
	@install --directory $(dir $@)
	install --mode 0644 $< $@
	sed -E -e "s|^( *APPLICATION_VERSION *= *)'[^']*'$$|\1'$(VERSION)'|" -i $@

.PHONY: package
package: $(DESTDIR)$(BINDIR)/$(PROGRAM) $(INSTALL_SHARES) $(INSTALL_MANS) $(INSTALL_AUTOSTART)


.PHONY: install
install: package
	update-desktop-database $(DESTDIR)$(DATADIR)/applications
	update-mime-database $(DESTDIR)$(DATADIR)/mime
	glib-compile-schemas $(DESTDIR)$(DATADIR)/glib-2.0/schemas
	gtk-update-icon-cache -f -t $(DESTDIR)$(DATADIR)/icons/*

$(DESTDIR)$(BINDIR)/$(PROGRAM) : $(PROGRAM)
	@install --directory $(dir $@)
	install --mode 0755 $< $@

$(INSTALL_SHARES): $(DESTDIR)$(DATADIR)/% : share/%
	@install --directory $(dir $@)
	install --mode 0644 $< $@

$(INSTALL_MANS): $(DESTDIR)$(DATADIR)/%.gz : share/%
	@install --directory $(dir $@)
	gzip --stdout $< > $@
	@chmod 0644 $@

$(INSTALL_APPLICATION): share/$(APPLICATION)
	@install --directory $(dir $@)
	sed -E -e "s|/usr/bin/|$(BINDIR)/|g" $< > $@
	@chmod 0644 $@

$(INSTALL_AUTOSTART) : $(INSTALL_APPLICATION)
	@install --directory $(dir $@)
	install --mode 0644 $< $@

.PHONY: uninstall
uninstall:
	rm -f $(DESTDIR)$(BINDIR)/$(PROGRAM) $(INSTALL_SHARES) $(INSTALL_MANS) $(INSTALL_APPLICATION) $(INSTALL_AUTOSTART)
	update-desktop-database $(DESTDIR)$(DATADIR)/applications
	update-mime-database $(DESTDIR)$(DATADIR)/mime
	glib-compile-schemas $(DESTDIR)$(DATADIR)/glib-2.0/schemas
	gtk-update-icon-cache -f -t $(DESTDIR)$(DATADIR)/icons/*

.PHONY: devel
devel: $(HOME)/.local/bin/$(PROGRAM) $(DEVEL_SHARES) $(DEVEL_APPLICATION) $(DEVEL_AUTOSTART)
	update-desktop-database $(HOME)/.local/share/applications
	update-mime-database $(HOME)/.local/share/mime
	glib-compile-schemas $(HOME)/.local/share/glib-2.0/schemas
	gtk-update-icon-cache -f -t $(HOME)/.local/share/icons/*

$(HOME)/.local/bin/$(PROGRAM) : src/__main__.py
	@install --directory $(dir $@)
	ln --force --symbolic $(abspath $<) $@

$(DEVEL_SHARES): $(HOME)/.local/share/% : share/%
	@install --directory $(dir $@)
	ln --force --symbolic $(abspath $<) $@

$(DEVEL_APPLICATION): share/$(APPLICATION)
	@install --directory $(dir $@)
	sed -E -e "s|/usr/|$(HOME)/.local/|g" $< > $@
	@chmod 0644 $@

$(DEVEL_AUTOSTART) : $(DEVEL_APPLICATION)
	@install --directory $(dir $@)
	ln --force --symbolic $(abspath $<) $@

.PHONY: undevel
undevel:
	rm -f $(HOME)/.local/bin/$(PROGRAM) $(DEVEL_SHARES) $(DEVEL_APPLICATION) $(DEVEL_AUTOSTART)
	update-desktop-database $(HOME)/.local/share/applications
	update-mime-database $(HOME)/.local/share/mime
	glib-compile-schemas $(HOME)/.local/share/glib-2.0/schemas
	gtk-update-icon-cache -f -t $(HOME)/.local/share/icons/*

.PHONY: spellcheck
spellcheck: README.md share/applications/*.desktop share/man/*/*.1
	for file in $^; do aspell --home-dir=. --save-repl --lang=en_US.UTF-8 check $$file; done
