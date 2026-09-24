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
- `nct6687d.service` - oneshot unit that ensures the module is loaded
- `nct6687.conf` - modprobe.d configuration
- `.github/workflows/check-upstream-commit.yml` - tracks the upstream
  default branch and auto-bumps the pinned commit + release

## Versioning

Upstream ships no release tags, so the package pins an upstream commit
(`nct6687d_commit` in the spec) and encodes it in the RPM release using the
Fedora git-snapshot convention, e.g. `1.0-20260923git5f12dd1.fc42`.

## Notes

- Board-specific hwmon.d examples from upstream are shipped in
  `%{_docdir}/nct6687d/sensors.d/`; copy the one matching your board to
  `/etc/hwmon.d/` to activate it
- A REBOOT is required after (re)installation: the module is compiled by
  akmods during the next boot, then loaded by the service
- Secure Boot: the post-install scriptlet detects unenrolled MOK keys and
  prints the `mokutil --import` steps

## License

This packaging work is licensed under GPL-2.0, same as the upstream nct6687d project.
