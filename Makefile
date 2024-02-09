PROGRAM := openvpn3-indicator
PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
DATADIR ?= $(PREFIX)/share
AUTOSTART ?= /etc/xdg/autostart

SHARES := $(shell find share -type f -not -iname "*.[1-8]" -not -iname "*.desktop" -not -iname "*.bak" -not -iname "*.swp")
SHARES := $(patsubst share/%,%,$(SHARES))
MANS := $(shell find share -type f -iname "*.[1-8]")
MANS := $(patsubst share/%,%,$(MANS))
APPLICATIONS := $(shell find share -type f -iname "*.desktop")
APPLICATIONS := $(patsubst share/%,%,$(APPLICATIONS))

INSTALL_SHARES := $(patsubst %,$(DESTDIR)$(DATADIR)/%,$(SHARES))
INSTALL_MANS := $(patsubst %,$(DESTDIR)$(DATADIR)/%.gz,$(MANS))
INSTALL_APPLICATIONS := $(patsubst %,$(DESTDIR)$(DATADIR)/%,$(APPLICATIONS))
INSTALL_AUTOSTART := $(DESTDIR)$(AUTOSTART)/$(PROGRAM).desktop

DEVEL_SHARES := $(patsubst %,$(HOME)/.local/share/%,$(SHARES))
#DEVEL_MANS := 
DEVEL_APPLICATIONS := $(patsubst %,$(HOME)/.local/share/%,$(APPLICATIONS))
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
	@echo "Use  ***  sudo make uninstall  ***  or  ***  make indevel  ***  to uninstall $(PROGRAM)."
	@echo

.PHONY: all
all:

.PHONY: package
package: $(DESTDIR)$(BINDIR)/$(PROGRAM) $(INSTALL_SHARES) $(INSTALL_MANS) $(INSTALL_AUTOSTART)


.PHONY: install
install: package
	update-desktop-database $(DESTDIR)$(DATADIR)/applications
	update-mime-database $(DESTDIR)$(DATADIR)/mime
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

$(INSTALL_APPLICATIONS): $(DESTDIR)$(DATADIR)/% : share/%
	@install --directory $(dir $@)
	sed -E -e "s|/usr/bin|$(BINDIR)/|g" $< > $@
	@chmod 0644 $@

$(INSTALL_AUTOSTART) : $(DESTDIR)$(DATADIR)/applications/$(PROGRAM).desktop
	@install --directory $(dir $@)
	install --mode 0644 $< $@

.PHONY: uninstall
uninstall:
	rm -f $(DESTDIR)$(BINDIR)/$(PROGRAM) $(INSTALL_SHARES) $(INSTALL_MANS) $(INSTALL_APPLICATIONS) $(INSTALL_AUTOSTART)
	update-desktop-database $(DESTDIR)$(DATADIR)/applications
	update-mime-database $(DESTDIR)$(DATADIR)/mime
	gtk-update-icon-cache -f -t $(DESTDIR)$(DATADIR)/icons/*

.PHONY: devel
devel: $(HOME)/.local/bin/$(PROGRAM) $(DEVEL_SHARES) $(DEVEL_APPLICATIONS) $(DEVEL_AUTOSTART)
	update-desktop-database $(HOME)/.local/share/applications
	update-mime-database $(HOME)/.local/share/mime
	gtk-update-icon-cache -f -t $(HOME)/.local/share/icons/*

$(HOME)/.local/bin/$(PROGRAM) : $(PROGRAM)
	@install --directory $(dir $@)
	ln --force --symbolic $(abspath $<) $@

$(DEVEL_SHARES): $(HOME)/.local/share/% : share/%
	@install --directory $(dir $@)
	ln --force --symbolic $(abspath $<) $@

$(DEVEL_APPLICATIONS): $(HOME)/.local/share/% : share/%
	@install --directory $(dir $@)
	sed -E -e "s|/usr/|$(HOME)/.local/|g" $< > $@
	@chmod 0644 $@

$(DEVEL_AUTOSTART) : $(HOME)/.local/share/applications/$(PROGRAM).desktop
	@install --directory $(dir $@)
	ln --force --symbolic $(abspath $<) $@

.PHONY: undevel
undevel:
	rm -f $(HOME)/.local/bin/$(PROGRAM) $(DEVEL_SHARES) $(DEVEL_APPLICATIONS) $(DEVEL_AUTOSTART)
	update-desktop-database $(HOME)/.local/share/applications
	update-mime-database $(HOME)/.local/share/mime
	gtk-update-icon-cache -f -t $(HOME)/.local/share/icons/*

.PHONY: spellcheck
spellcheck: README.md share/applications/*.desktop share/man/*/*.1
	for file in $^; do aspell --home-dir=. --save-repl --lang=en_US.UTF-8 check $$file; done
