PROGRAM := openvpn3-indicator
PREFIX ?= /usr/local
AUTOSTART ?= /etc/xdg/autostart

SHARES := $(shell find share -type f -not -iname "*.[1-8]" -not -iname "*.desktop" -not -iname "*.bak" -not -iname "*.swp")
MANS := $(shell find share -type f -iname "*.[1-8]")
APPLICATIONS := $(shell find share -type f -iname "*.desktop")

INSTALL_SHARES := $(patsubst %,$(PREFIX)/%,$(SHARES))
INSTALL_MANS := $(patsubst %,$(PREFIX)/%.gz,$(MANS))
INSTALL_APPLICATIONS := $(patsubst %,$(PREFIX)/%,$(APPLICATIONS))
INSTALL_AUTOSTART := $(AUTOSTART)/$(PROGRAM).desktop

DEVEL_SHARES := $(patsubst %,$(HOME)/.local/%,$(SHARES))
#DEVEL_MANS := 
DEVEL_APPLICATIONS := $(patsubst %,$(HOME)/.local/%,$(APPLICATIONS))
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

.PHONY: install
install: $(PREFIX)/bin/$(PROGRAM) $(INSTALL_SHARES) $(INSTALL_MANS) $(INSTALL_AUTOSTART)
	gtk-update-icon-cache $(PREFIX)/share/icons/*

$(PREFIX)/bin/$(PROGRAM) : $(PROGRAM)
	@install --directory $(dir $@)
	install --mode 0755 $< $@

$(INSTALL_SHARES): $(PREFIX)/% : %
	@install --directory $(dir $@)
	install --mode 0644 $< $@

$(INSTALL_MANS): $(PREFIX)/%.gz : %
	@install --directory $(dir $@)
	gzip --stdout $< > $@
	@chmod 0644 $@

$(INSTALL_APPLICATIONS): $(PREFIX)/% : %
	@install --directory $(dir $@)
	sed -E -e "s|/usr/|$(PREFIX)/|g" $< > $@
	@chmod 0644 $@

$(INSTALL_AUTOSTART) : $(PREFIX)/share/applications/$(PROGRAM).desktop
	@install --directory $(dir $@)
	ln --force --symbolic $< $@

.PHONY: uninstall
uninstall:
	rm -f $(PREFIX)/bin/$(PROGRAM) $(INSTALL_SHARES) $(INSTALL_MANS) $(INSTALL_APPLICATIONS) $(INSTALL_AUTOSTART)
	gtk-update-icon-cache $(PREFIX)/share/icons/*

.PHONY: devel
devel: $(HOME)/.local/bin/$(PROGRAM) $(DEVEL_SHARES) $(DEVEL_APPLICATIONS) $(DEVEL_AUTOSTART)
	gtk-update-icon-cache $(HOME)/.local/share/icons/*

$(HOME)/.local/bin/$(PROGRAM) : $(PROGRAM)
	@install --directory $(dir $@)
	ln --force --symbolic $(abspath $<) $@

$(DEVEL_SHARES): $(HOME)/.local/% : %
	@install --directory $(dir $@)
	ln --force --symbolic $(abspath $<) $@

$(DEVEL_APPLICATIONS): $(HOME)/.local/% : %
	@install --directory $(dir $@)
	sed -E -e "s|/usr/|$(HOME)/.local/|g" $< > $@
	@chmod 0644 $@

$(DEVEL_AUTOSTART) : $(HOME)/.local/share/applications/$(PROGRAM).desktop
	@install --directory $(dir $@)
	ln --force --symbolic $(abspath $<) $@

.PHONY: undevel
undevel:
	rm -f $(HOME)/.local/bin/$(PROGRAM) $(DEVEL_SHARES) $(DEVEL_APPLICATIONS) $(DEVEL_AUTOSTART)
	gtk-update-icon-cache $(HOME)/.local/share/icons/*

.PHONY: spellcheck
spellcheck: README.md share/applications/*.desktop share/man/*/*.1
	for file in $^; do aspell --home-dir=. --save-repl --lang=en_US.UTF-8 check $$file; done
