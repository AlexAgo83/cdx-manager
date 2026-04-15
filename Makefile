.PHONY: install uninstall

install:
	npm link

uninstall:
	npm unlink -g cdx-manager
