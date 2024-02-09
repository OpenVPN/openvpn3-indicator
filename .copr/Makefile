outdir ?= .copr

.PHONY: srpm
srpm: .copr/openvpn3-indicator.spec
	rpkg srpm --outdir $(outdir) --spec $<

.PHONY: clean
clean:
	rm -f .copr/openvpn3-indicator.spec .copr/*.tar.gz .copr/*.rpm

.copr/openvpn3-indicator.spec : .copr/openvpn3-indicator.spec.py
	dnf -y install git rpkg
	python3 $< > $@
