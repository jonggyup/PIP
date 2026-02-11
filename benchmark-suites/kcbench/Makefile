NAME=kcbench

PREFIX?=/usr/local/

all:

install:
	for dir in bin bin/ share/man/man1/ share/doc/$(NAME)/; do mkdir -p $(DESTDIR)$(PREFIX)/$$dir; done
	cp kcbench $(DESTDIR)$(PREFIX)/bin/
	cp kcbenchrate $(DESTDIR)$(PREFIX)/bin/
	cp generated/kcbench.1 $(DESTDIR)$(PREFIX)/share/man/man1/
	cp generated/kcbenchrate.1 $(DESTDIR)$(PREFIX)/share/man/man1/
	cp README.md ChangeLog $(DESTDIR)$(PREFIX)/share/doc/$(NAME)


uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/kcbench $(DESTDIR)$(PREFIX)/bin/kcbenchrate $(DESTDIR)$(PREFIX)/share/man/man1/kcbench.1 $(DESTDIR)$(PREFIX)/share/man/man1/kcbenchrate.1 $(DESTDIR)$(PREFIX)/share/doc/$(NAME)/README.md $(DESTDIR)$(PREFIX)/share/doc/$(NAME)/ChangeLog
	rmdir $(DESTDIR)$(PREFIX)/share/doc/$(NAME)

manpages:
	pandoc --standalone -f markdown-smart --to man kcbench.man1.md -o generated/kcbench.1
	pandoc --standalone -f markdown-smart --to man kcbenchrate.man1.md -o generated/kcbenchrate.1

.PHONY: install uninstall manpages all
