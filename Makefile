PROGRAM := openvpn3-indicator
PREFIX ?= /usr
AUTOSTART ?= /etc/xdg/autostart

SHARES := $(shell find share -type f -not -iname "*.[1-8]")
MANS := $(shell find share -type f -iname "*.[1-8]")
APPLICATION := $(shell find share -type f -iname $(PROGRAM).desktop)
INSTALL_SHARES := $(patsubst %,$(PREFIX)/%,$(SHARES))
INSTALL_MANS := $(patsubst %,$(PREFIX)/%.gz,$(MANS))
INSTALL_APPLICATION := $(patsubst %,$(PREFIX)/%,$(APPLICATION))
INSTALL_AUTOSTART := $(AUTOSTART)/$(PROGRAM).desktop

.PHONY: all

all:


.PHONY: install

install: $(PREFIX)/bin/$(PROGRAM) $(INSTALL_SHARES) $(INSTALL_MANS) $(INSTALL_AUTOSTART)


$(PREFIX)/bin/$(PROGRAM) : $(PROGRAM)
	install -D --mode 0755 $< $@

$(INSTALL_SHARES): $(PREFIX)/% : %
	install -D --mode 0644 $< $@
	update-icon-caches $(PREFIX)/share/icons

$(INSTALL_MANS): $(PREFIX)/%.gz : %
	gzip --stdout $< > $@
	chmod 0644 $@

$(INSTALL_AUTOSTART): $(INSTALL_APPLICATION)
	ln --force --symbolic $< $@
