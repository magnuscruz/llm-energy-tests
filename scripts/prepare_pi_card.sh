#!/usr/bin/env bash
# Apply the ambient-logger configuration to a freshly flashed Raspberry Pi card.
#
# The Raspberry Pi Imager sets the user, password, Wi-Fi, SSH and locale. It does
# not set the five things this deployment needs, and two of them fail silently:
#
#   1. dtoverlay=dwc2            USB gadget, so the Pi reaches the measurement
#   2. modules-load=dwc2,g_ether node over a point-to-point link and needs no
#   3. usb0 static address       site network at all
#   4. sudo for the user         Imager writes "sudo: null"; without this the
#                                user cannot install, enable services, or let
#                                the node set the clock
#   5. i2c group membership      without it, reading /dev/i2c-1 needs root and
#                                the logger runs privileged for no reason
#
# Idempotent: safe to run twice. Backs up every file it touches.
#
# Public keys may be supplied so the Pi accepts key-based SSH from first boot.
# Give one file with one key per line; the local ~/.ssh/id_ed25519.pub is used
# when nothing is passed. The measurement node's key belongs here too: it needs
# non-interactive access to set the Pi's clock before each campaign.
#
#   ./prepare_pi_card.sh /mnt/d [keys-file]

set -uo pipefail
BOOT="${1:?usage: $0 <path-to-boot-partition> [keys-file]}"
KEYS_FILE="${2:-$HOME/.ssh/id_ed25519.pub}"

for f in config.txt cmdline.txt user-data network-config; do
  [ -f "$BOOT/$f" ] || { echo "[!] $BOOT/$f not found -- is this the boot partition?" >&2; exit 1; }
done

STAMP=$(date +%Y%m%d-%H%M%S)
for f in config.txt cmdline.txt user-data network-config; do
  cp -n "$BOOT/$f" "$BOOT/$f.bak-$STAMP" 2>/dev/null
done
echo "[+] backups: *.bak-$STAMP"

KEYS=""
if [ -f "$KEYS_FILE" ]; then
  KEYS=$(grep -E "^(ssh-|ecdsa-)" "$KEYS_FILE" 2>/dev/null)
  [ -n "$KEYS" ] && echo "[+] authorized keys from $KEYS_FILE: $(echo "$KEYS" | wc -l)"
else
  echo "[!] no key file at $KEYS_FILE -- password login only" >&2
fi

"${PY:-python3}" - "$BOOT" "$KEYS" <<'PYEOF'
import re, sys, time
boot, keys = sys.argv[1], sys.argv[2]

def read(f):  return open(f"{boot}/{f}").read()
def write(f, s): open(f"{boot}/{f}", "w").write(s)

# 1. USB OTG driver, under the final [all] so it applies to every revision.
s = read("config.txt")
if re.search(r"^\s*dtoverlay=dwc2\s*$", s, re.M):
    print("    config.txt      dwc2 already present")
else:
    write("config.txt", s.rstrip("\n") +
          "\n\n# USB gadget: the Pi appears as a network interface to the machine it is\n"
          "# plugged into, giving a link that depends on no site network.\n"
          "dtoverlay=dwc2\n")
    print("    config.txt      dtoverlay=dwc2 added")

# 1b. I2C bus. Not enabled by default on a stock image: without it there is no
#     /dev/i2c-1 and the sensor cannot be read at all. Easy to assume present,
#     because a card that has previously been through raspi-config already has
#     it -- which is exactly how it was missed once.
s = read("config.txt")
if re.search(r"^\s*dtparam=i2c_arm=on\s*$", s, re.M):
    print("    config.txt      i2c already enabled")
else:
    write("config.txt", s.rstrip("\n") + "\ndtparam=i2c_arm=on\n")
    print("    config.txt      dtparam=i2c_arm=on added")

# 2. Ethernet gadget module. This file MUST remain a single line; split in two,
#    the Pi does not boot.
s = read("cmdline.txt").strip()
if "\n" in s:
    sys.exit("[!] cmdline.txt has more than one line already -- refusing to touch it")
if "g_ether" in s:
    print("    cmdline.txt     g_ether already present")
else:
    if "rootwait" not in s:
        sys.exit("[!] rootwait not found in cmdline.txt -- aborting")
    write("cmdline.txt", s.replace("rootwait", "rootwait modules-load=dwc2,g_ether", 1) + "\n")
    print("    cmdline.txt     modules-load=dwc2,g_ether added")

# 3. Deterministic address on the USB link, so the node always finds the Pi
#    without a DHCP server. mDNS stays available as a fallback.
s = read("network-config")
if "usb0" in s:
    print("    network-config  usb0 already present")
else:
    if "  ethernets:" not in s:
        sys.exit("[!] no ethernets block in network-config -- aborting")
    write("network-config", s.replace("  ethernets:",
          "  ethernets:\n"
          "    usb0:\n"
          "      addresses: [192.168.7.2/24]\n"
          "      optional: true", 1))
    print("    network-config  usb0 static 192.168.7.2 added")

# 4, 5 & 6. Privileges, groups and authorized keys.
#
# Edited through the parsed structure, not with regular expressions. The layout
# of this file is the Imager's, not ours: it places ssh_authorized_keys before
# sudo, and quotes key strings. Appending text at the end of the user block
# produced orphaned list items and an unparseable file -- which would leave
# cloud-init unable to create the account at all. With ssh_pwauth commonly set
# to false by the Imager, that means no way in whatsoever.
import yaml

raw = read("user-data")
header = "#cloud-config"
doc = yaml.safe_load(raw)
u = doc.setdefault("user", {})
changed = False

if u.get("sudo") != "ALL=(ALL) NOPASSWD:ALL":
    u["sudo"] = "ALL=(ALL) NOPASSWD:ALL"
    changed = True
    print("    user-data       sudo granted")

groups = u.get("groups") or []
if isinstance(groups, str):
    groups = [g.strip() for g in groups.split(",")]
want = ["adm", "sudo", "dialout", "audio", "video", "plugdev",
        "users", "input", "netdev", "i2c", "gpio", "spi"]
missing = [g for g in want if g not in groups]
if missing:
    u["groups"] = groups + missing
    changed = True
    print(f"    user-data       groups added: {', '.join(missing)}")

if keys.strip():
    have = u.get("ssh_authorized_keys") or []
    # Compare on type+material only: the Imager quotes entries and comments vary.
    seen = {" ".join(str(k).strip().strip('"').split()[:2]) for k in have}
    added = 0
    for k in keys.strip().splitlines():
        k = k.strip()
        if " ".join(k.split()[:2]) not in seen:
            have.append(k)
            seen.add(" ".join(k.split()[:2]))
            added += 1
    if added:
        u["ssh_authorized_keys"] = have
        changed = True
        print(f"    user-data       {added} authorized key(s) added")

if changed:
    body = yaml.safe_dump(doc, default_flow_style=False, sort_keys=False,
                          width=4096, allow_unicode=True)
    write("user-data", f"{header}\n{body}")
    print("    user-data       written")
else:
    print("    user-data       already configured")
PYEOF
rc=$?
[ $rc -ne 0 ] && { echo "[!] aborted; restore from *.bak-$STAMP" >&2; exit $rc; }

echo
echo "[+] verifying"
printf "    cmdline.txt is one line : "; [ "$(wc -l < "$BOOT/cmdline.txt")" -le 1 ] && echo yes || { echo "NO -- RESTORE THE BACKUP"; exit 1; }
python3 - "$BOOT" <<'PYEOF' 2>/dev/null || echo "    yaml check skipped (pyyaml not installed)"
import sys, yaml
boot = sys.argv[1]
for f in ("user-data", "network-config"):
    yaml.safe_load(open(f"{boot}/{f}"))
d = yaml.safe_load(open(f"{boot}/user-data"))
u = d.get("user", {})
print(f"    user                    : {u.get('name')}")
print(f"    sudo                    : {u.get('sudo')}")
print(f"    i2c group               : {'yes' if 'i2c' in (u.get('groups') or []) else 'NO'}")
n = yaml.safe_load(open(f"{boot}/network-config"))["network"]["ethernets"]
print(f"    usb0                    : {n.get('usb0', {}).get('addresses')}")
PYEOF
echo
echo "[+] done. Eject the card, boot the Pi, then check on it:"
echo "      id            # i2c must appear"
echo "      ls /dev/i2c-*"
