# NCT6687D Akmod RPM Spec - NVIDIA-style approach
%global _debugsource_packages 0
%global _debuginfo_packages 0
%global debug_package %{nil}
%global _dracut_conf_d /usr/lib/dracut/dracut.conf.d

# Upstream Fred78290/nct6687d ships no release tags:
# the package version is pinned to an upstream commit, and the release
# encodes the packaging date plus the short commit (Fedora git-snapshot
# convention), so every upstream sync is a new, uniquely named build.
%global nct6687d_commit 5f12dd1b0b3c8f79f31d309749862d986ff9efa7
%global nct6687d_release 20260924git5f12dd1

Name:           nct6687d
Version:        1.0
Release:        %{nct6687d_release}%{?dist}
Summary:        Nuvoton NCT6687 hardware monitoring kernel module (akmod)

License:        GPL-2.0-or-later
URL:            https://github.com/Fred78290/nct6687d
Source0:        %{url}/archive/%{nct6687d_commit}.tar.gz#/%{name}-%{nct6687d_commit}.tar.gz
Source1:        nct6687-load.service
Source2:        Makefile.akmod
Source3:        nct6687.conf
Source4:        nct6687d-kmod.spec.in

# NCT6687 is a PC Super-I/O chip: x86 only
ExclusiveArch:  x86_64 i686

# Akmod BuildRequires
BuildRequires:  kmodtool
BuildRequires:  akmods
BuildRequires:  rpm-build
BuildRequires:  systemd-rpm-macros

# Runtime Requirements
Requires:       systemd
%ifarch x86_64 i686
Requires:       mokutil
%endif
Requires:       %{name}-kmod = %{?epoch:%{epoch}:}%{version}-%{release}
Requires:       %{name}-kmod-common = %{?epoch:%{epoch}:}%{version}-%{release}

# Generate akmod metadata
%{expand:%(kmodtool --target %{_target_cpu} --kmodname %{name} --pattern ".*" --akmod 2>/dev/null) }

%description
nct6687d is a kernel module for the hardware monitoring functionality of
Nuvoton NCT6687 Super-I/O chips, exposing voltage, temperature and fan
sensors through the Linux hwmon subsystem (visible via lm-sensors).
The chip is present on many B550/B460/Z690-class motherboards.

This package provides the systemd service, modprobe configuration and the
akmod source for the 'nct6687' kernel module with full automation
including Secure Boot support.

IMPORTANT: After installation, a REBOOT is required for the kernel module
to be compiled and loaded automatically.

%package -n akmod-%{name}
Summary:        Akmod package for %{name} kernel module(s)
Requires:       kmodtool
Requires:       akmods
Provides:       %{name}-kmod = %{?epoch:%{epoch}:}%{version}-%{release}
Requires:       %{name}-kmod-common = %{?epoch:%{epoch}:}%{version}-%{release}

%description -n akmod-%{name}
This package provides the akmod package for the %{name} kernel modules.

%package kmod-common
Summary:        Common files for %{name} kernel module
Requires:       %{name} = %{?epoch:%{epoch}:}%{version}-%{release}
Provides:       %{name}-kmod-common = %{?epoch:%{epoch}:}%{version}-%{release}

%description kmod-common
This package provides the common files for the %{name} kernel modules.

%prep
# codeload names a commit tarball's top-level directory <repo>-<full sha>
# (verified against the live codeload output), so pin that exact name.
%setup -q -n %{name}-%{nct6687d_commit}

# Replace the upstream Makefile (manual install / dkms / deb / akmod noise
# that keeps drifting between upstream commits) with the packaging-owned
# akmod driver. The kmod SRPM tarball inherits this Makefile, so the
# per-kernel build is fully determined by this packaging.
cp Makefile Makefile.orig
cp %{SOURCE2} Makefile

%install
# --- Install runtime components ---
install -D -m 0644 %{SOURCE3} %{buildroot}%{_sysconfdir}/modprobe.d/nct6687.conf
install -D -m 0644 %{SOURCE1} %{buildroot}%{_unitdir}/nct6687-load.service

# --- Create and install the kmod SRPM for akmods ---
install -d %{buildroot}%{_usrsrc}/akmods/

SRPM_TOPDIR=$(mktemp -d)
mkdir -p "$SRPM_TOPDIR"/{SOURCES,SPECS}

sed -e 's|@NCT6687D_VERSION@|%{version}|g' \
    -e 's|@NCT6687D_RELEASE@|%{release}|g' \
    %{SOURCE4} > "$SRPM_TOPDIR"/SPECS/nct6687d-kmod.spec

tar -czf "$SRPM_TOPDIR"/SOURCES/nct6687d-kmod-%{version}.tar.gz \
    --transform "s|^%{name}-%{nct6687d_commit}|nct6687d-kmod-%{version}|" \
    -C %{_builddir} \
    %{name}-%{nct6687d_commit}

rpmbuild -bs \
  --define "_topdir $SRPM_TOPDIR" \
  "$SRPM_TOPDIR"/SPECS/nct6687d-kmod.spec

install -m 0644 "$SRPM_TOPDIR"/SRPMS/*.src.rpm %{buildroot}%{_usrsrc}/akmods/

SRPM_NAME=$(basename "$SRPM_TOPDIR"/SRPMS/*.src.rpm)
ln -s "$SRPM_NAME" %{buildroot}%{_usrsrc}/akmods/%{name}-kmod.latest

rm -rf "$SRPM_TOPDIR"

# --- Dracut configuration ---
install -d -m 0755 %{buildroot}%{_dracut_conf_d}
cat > %{buildroot}%{_dracut_conf_d}/99-nct6687d.conf << EOF
# Do not include the nct6687 module in the initramfs.
omit_drivers+=" nct6687 "
EOF

%post
# Generate akmods signing key if it doesn't exist
# This uses the official kmodgenca tool from akmods package
if [ ! -f /etc/pki/akmods/certs/public_key.der ]; then
    echo "Generating akmods signing keys..."
    /usr/sbin/kmodgenca -a 2>/dev/null || true
fi

# === SMART MOK DETECTION ===
smart_mok_check() {
    local akmods_key="/etc/pki/akmods/certs/public_key.der"

    # Early exit: Not a UEFI system
    if [ ! -d /sys/firmware/efi/efivars ]; then
        return 0
    fi

    # Early exit: mokutil not available
    if ! command -v mokutil >/dev/null 2>&1; then
        return 0
    fi

    # Check if Secure Boot is enabled
    local sb_state
    sb_state=$(mokutil --sb-state 2>/dev/null)

    if ! echo "$sb_state" | grep -q "SecureBoot enabled"; then
        return 0
    fi

    # At this point: UEFI + Secure Boot enabled

    # Key should exist now (we just generated it)
    if [ ! -f "$akmods_key" ]; then
        cat << 'EOF'

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  SECURE BOOT WARNING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Failed to generate akmods key. After reboot, run:
  sudo mokutil --import /etc/pki/akmods/certs/public_key.der
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF
        return 1
    fi

    # Check if key is already enrolled
    if mokutil --list-enrolled 2>/dev/null | grep -q "CN=akmods" || \
       mokutil --test-key "$akmods_key" 2>&1 | grep -qi "already.*enrolled"; then
        return 0
    fi

    # Key exists but NOT enrolled - show instructions
    cat << 'EOF'

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔐 SECURE BOOT DETECTED - ACTION REQUIRED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
To use NCT6687D with Secure Boot, enroll the MOK key NOW (before reboot):

  sudo mokutil --import /etc/pki/akmods/certs/public_key.der

You'll be asked to create a password. Remember it for the next reboot.

After rebooting:
  1. MOK Manager will appear
  2. Select "Enroll MOK"
  3. Enter the password you just created
  4. Reboot again

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF
}

smart_mok_check

# Register service with systemd
%systemd_post nct6687-load.service
systemctl enable nct6687-load.service >/dev/null 2>&1 || true

cat << EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ NCT6687D Installation Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  REBOOT REQUIRED

The kernel module will be compiled during the next boot.
After rebooting, the NCT6687 sensors are exposed through hwmon:

  sensors

To check the module / service status:
  systemctl status nct6687-load.service

Board-specific sensor examples (labels/compute) are installed in:
  %{_docdir}/sensors.d/
Copy the one matching your board to /etc/hwmon.d/ to activate it.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF

%preun
# Stop service before uninstall/upgrade
%systemd_preun nct6687-load.service

if [ $1 -eq 0 ]; then
    # Complete uninstall: try to remove the kernel module
    # (May fail if in use - that's OK, reboot will clear it)
    /sbin/modprobe -r nct6687 >/dev/null 2>&1 || true
fi

%postun
%systemd_postun nct6687-load.service

if [ $1 -ne 0 ]; then
    # Upgrade scenario: show message
    cat << 'EOF'

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ NCT6687D Upgraded
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  REBOOT REQUIRED

The kernel module needs to be recompiled for the new version.
Please reboot your system to complete the upgrade.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF
fi

%files
%license LICENSE
%doc README.md TESTING_RESULTS.md sensors.d
%config(noreplace) %{_sysconfdir}/modprobe.d/nct6687.conf
%{_unitdir}/nct6687-load.service
%{_dracut_conf_d}/99-nct6687d.conf

%files -n akmod-%{name}
%{_usrsrc}/akmods/nct6687d-kmod-%{version}-*.src.rpm
%{_usrsrc}/akmods/nct6687d-kmod.latest

%files kmod-common
# Empty dependency anchor package

%changelog
* Thu Sep 24 2026 Sunny <yxh9956@gmail.com> - 1.0-20260924git5f12dd1
- nct6687.conf: replace the bare module-name line (invalid modprobe.d
  syntax - libkmod logs "ignoring bad line" on every kmod tool run) with a
  comments-only options template

* Wed Sep 23 2026 Sunny <yxh9956@gmail.com> - 1.0-20260923git5f12dd1
- Rebuild Fedora packaging on the coreFreq-rpm-fedora akmod framework:
  single spec as source of truth, build-time generated kmod SRPM,
  dracut omit conf, MOK/Secure Boot automation
- Replace upstream's MAKEFILE_PKGVER/MAKEFILE_COMMITHASH placeholder
  specs; version now pinned to an upstream commit (nct6687d_commit)
  with a Fedora git-snapshot style release
- Add nct6687-load.service (oneshot modprobe unit) and nct6687 modprobe conf
- Ship board-specific hwmon.d examples from upstream sensors.d/ as docs
- Drive the per-kernel build from a packaging-owned Makefile.akmod; the
  upstream Makefile stays the manual/dkms/deb workflow and is swapped out
  in %prep before the kmod SRPM tarball is generated
- %setup pins codeload's actual top-level directory name
  (<repo>-<full sha>, verified against live codeload output), and
  %changelog dates use the RPM standard format
- Align the loader unit with the gddr7-temp pattern: renamed to
  nct6687-load.service and ordered After akmods.service, so on first boot
  the module is only modprobed after akmods has compiled it (fixes the
  first-boot race of the previous unit ordering); unload via ExecStop
