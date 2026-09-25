# nct6687d-rpm-fedora
Fedora RPM packaging (akmod) for the NCT6687D hardware monitoring kernel module

This tool was developed with help of AI.

Upstream driver: https://github.com/Fred78290/nct6687d

## Layout

- `nct6687d-akmod.spec` - main package (systemd service, modprobe conf,
  dracut conf) and the single source of truth for the build: it generates
  the akmod/kmod SRPMs at build time
- `nct6687d-kmod.spec.in` - template for the per-kernel akmod kmod spec
  (`@NCT6687D_VERSION@`/`@NCT6687D_RELEASE@` are filled from the main spec)
- `Makefile.akmod` - packaging-owned driver for the per-kernel module
  build (swapped into the kmod tree in %prep; the upstream Makefile is the
  manual/dkms/deb workflow and keeps drifting between upstream commits)
- `nct6687-load.service` - oneshot loader unit, ordered After
  `akmods.service` so the module is only loaded once akmods has compiled
  it (first-boot safe)
- `nct6687.conf` - modprobe.d configuration

## Versioning

Upstream ships no release tags, so `Source0` is pinned to an explicit
upstream commit (`nct6687d_commit` in the spec; currently 5f12dd1b,
2026-09-15). The RPM release is the commit's stable git-snapshot tag
without a leading `0.` or counter suffix — e.g.
`1.0-20260924git5f12dd1.fc44` (named after the first packaging build
of that commit). A rebuild of the same commit reuses the tag
(install over the previous one with `dnf reinstall` / `rpm -U
--force`), and a new upstream sync mints a new `<date>git<sha>` tag.

## Notes

- Board-specific hwmon.d examples from upstream are shipped in
  `%{_docdir}/nct6687d/sensors.d/`; copy the one matching your board to
  `/etc/hwmon.d/` to activate it
- No reboot after (re)installation: the akmod package's %posttrans
  triggers akmods immediately, so the module is compiled on the fly;
  the loader service picks it up at the next boot (or run
  `systemctl restart nct6687-load` right away)
- Secure Boot: the post-install scriptlet detects unenrolled MOK keys and
  prints the `mokutil --import` steps

## License

This packaging work is licensed under GPL-2.0, same as the upstream nct6687d project.
