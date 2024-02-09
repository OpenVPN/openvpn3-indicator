OFFICE = $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
outdir ?= $(OFFICE)

.PHONY: srpm
srpm: $(outdir)/openvpn3-indicator.spec
	rpkg srpm --outdir $(outdir) --spec $<

.PHONY: clean
clean:
	rm -f $(outdir)/openvpn3-indicator.spec $(outdir)/*.tar.gz $(outdir)/*.rpm

$(outdir)/openvpn3-indicator.spec : $(OFFICE)/openvpn3-indicator.spec.py
	dnf -y install git rpkg
	python3 $< --scriptdir $(OFFICE) --outdir $(outdir)
