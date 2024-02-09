outdir ?= .

.PHONY: srpm
srpm: openvpn3-indicator.spec
	rpkg srpm --outdir $(outdir) --spec $<

.PHONY: clean
clean:
	rm -f openvpn3-indicator.spec *.tar.gz *.rpm

openvpn3-indicator.spec : openvpn3-indicator.spec.py
	python3 $< > $@
