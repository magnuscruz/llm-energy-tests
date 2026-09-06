# Runbook — measurement campaigns

Two machines take part. The **node** runs the models and is the subject of
measurement; the **Pi** watches the room and touches nothing on the node. Every
stream is stamped in UNIX epoch, which is the only reason they can be fused
afterwards.

Sections 1 and 2 are done once. Section 3 onward is per campaign.

---

## 1. Prepare the Pi (once)

### 1.1 Flash the card

Raspberry Pi Imager, **Raspberry Pi OS Lite (64-bit)**. Not the desktop image:
the Pi Zero 2 W has 512 MB of RAM and a desktop leaves it swapping, on a device
meant to read a sensor for eight days unattended.

In the advanced options set the username, password, Wi-Fi, SSH, locale and
timezone, and paste your public key.

### 1.2 Apply what the Imager does not

```bash
sudo mount -t drvfs D: /mnt/d          # or wherever the boot partition appears
./scripts/prepare_pi_card.sh /mnt/d ~/.ssh/id_ed25519.pub
sudo umount /mnt/d
```

Six changes, two of which fail silently if skipped:

| Change | Why |
|---|---|
| `dtparam=i2c_arm=on` | no I2C bus, so no `/dev/i2c-1` and no sensor |
| `dtoverlay=dwc2` + `modules-load=dwc2,g_ether` | USB gadget: reaches the node without any site network |
| `usb0` static `192.168.7.2/24` | deterministic address, no DHCP needed |
| `sudo: ALL=(ALL) NOPASSWD:ALL` | the Imager writes `sudo: null`, leaving the account unable to administer anything |
| group `i2c` | without it the sensor needs root |
| authorized keys | the Imager often sets `ssh_pwauth: false`, making keys the only way in |

The script is idempotent and validates the YAML before finishing. That check
matters: a malformed `user-data` stops cloud-init creating the account at all,
and with password auth off that means no way in.

### 1.3 Wire the sensor

SHT3x over I2C, on the four pins nearest the corner:

| Sensor | Pi physical pin |
|---|---|
| `VIN` | **1** — 3.3 V, never 2 or 4 (those are 5 V) |
| `SDA` | **3** |
| `SCL` | **5** |
| `GND` | **6** |

Solder them. A pin pushed into an unsoldered hole holds mechanically and
conducts intermittently, which produces gaps in a 48-hour log rather than an
error.

Mount the sensor on a lead, 1.5–2 m from the node, at intake height and never in
the exhaust. A sensor near warm hardware measures the hardware.

### 1.4 First boot

```bash
ssh magnuspi@<pi>
id                                 # i2c must be listed
ls /dev/i2c-*                      # /dev/i2c-1
sudo /usr/sbin/i2cdetect -y 1      # 44 (or 45)
```

`i2cdetect` lives in `/usr/sbin`, which is not on the PATH of a
non-interactive SSH session. It works when you are logged in and appears
missing when you run it as `ssh host 'i2cdetect -y 1'`.

**Check the network config actually reached NetworkManager.** This is the one
that will cost you an afternoon:

```bash
ls /etc/NetworkManager/system-connections/
```

The `network-config` written to the card is correct and still may never be
converted into a connection profile. An empty directory means the Pi has
nothing to connect to: `nmcli dev status` shows `wlan0 disconnected` and
`usb0 unavailable`, no interface gets an address, and from the outside the
Pi is indistinguishable from dead hardware -- absent over Wi-Fi and over USB
at the same time, with the LEDs on. Create the profiles by hand:

```bash
sudo nmcli dev wifi connect <SSID> --ask
sudo nmcli con add type ethernet con-name usb0 ifname usb0 \
     ipv4.method manual ipv4.addresses 192.168.7.2/24 \
     ipv4.never-default yes connection.autoconnect yes
nmcli -g NAME,AUTOCONNECT con show      # both must say yes
```

`never-default` stops a point-to-point link with no gateway from taking the
default route away from Wi-Fi.

**Power the Pi from a real supply, not a PC port.** Associating the Wi-Fi radio
is the largest current spike the board makes. On a marginal supply it resets
instead of reporting an error, so the reboot looks like the configuration
failing rather than the power. A keyboard on the OTG port draws from the Pi
and is enough on its own to cause this: use a 5 V 2.5 A supply on the outer
`PWR IN` connector and a short cable.

Then, while the Pi still has internet — over USB at the lab it will not:

```bash
sudo apt update && sudo apt install -y python3-smbus2 i2c-tools avahi-daemon
mkdir -p ~/ambient && cd ~/ambient
git clone --depth 1 --filter=blob:none --sparse <repo-url> .
git sparse-checkout set src scripts
```

The sparse checkout takes about 16 KB. A full clone is 2.5 GB of campaign data
the Pi has neither room for nor use for.

### 1.5 Install the logger as a service

```bash
sudo cp scripts/ambient-logger.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ambient-logger
journalctl -u ambient-logger -n 20 --no-pager
```

Leave it running for a few hours and confirm the line count matches the elapsed
seconds. Cadence drift and flaky contacts only show over time.

---

## 2. Prepare the link (once)

Connect the Pi's **data** micro-USB — the middle one, not `PWR IN` — to the
node. On the node:

```bash
sudo ip addr add 192.168.7.1/24 dev usb0 && sudo ip link set usb0 up
ssh magnuspi@192.168.7.2 'echo ok'
```

For the node to set the Pi's clock unattended it needs its own key on the Pi:

```bash
ssh-keygen -t ed25519 -N "" -C "edge-node"      # on the node, no passphrase
ssh-copy-id magnuspi@192.168.7.2                # or append it manually
```

---

## 3. Before each campaign

```bash
./scripts/sync_pi_clock.sh
```

Not optional. The Pi has no real-time clock; over the USB link there is no NTP,
so it keeps whatever time it had at boot. A drifting clock pairs ambient
readings with the wrong inference events and reports nothing wrong.

Then restart the logger so the file begins with the campaign:

```bash
ssh magnuspi@192.168.7.2 'sudo systemctl restart ambient-logger'
```

The ambient log must span the **whole** campaign — four models in sequence is
about eight days, roughly 700,000 samples and 17 MB. Do not stop it between
models.

---

## 4. Run

```bash
sudo nohup ./scripts/run_benchmark_pair.sh 172800 --throttle 75 \
     > benchmark_run_pair.log 2>&1 &
```

`172800` is 48 hours per model. Root is required for the governor and the page
cache. The script reads the applied cap back from sysfs and **aborts** if it
does not match the request — the defence against the two campaigns that ran for
months without an effective cap.

---

## 5. After

```bash
./scripts/collect_ambient.sh logs/<campaign>
cd logs/<campaign>/deep_aging
python3 ../../../src/build_data_analysis.py
```

`collect_ambient.sh` reports coverage per model and distinguishes three
outcomes: full, partial (the logger stopped early — report the limitation), and
no overlap at all (wrong file or disagreeing clocks — the collection is void).

Then verify the campaign before building anything on it. Six checks, in this
order — the first that fails makes the rest moot:

1. **Span.** Actual first-to-last timestamp of `*_physical.csv`, per model.
   Filenames always say 48 h; one existing run holds 40.1 h.
2. **Gaps.** Largest hole in the 1 Hz power stream. A power cut mid-campaign
   shows up here and nowhere else.
3. **Cap adherence.** `throttle_percentage` in `run_config.log` against the
   `[Verify]` line's `scaling_max_freq`. Two campaigns ran for months without
   an effective cap.
4. **Logger failures.** Non-empty `*_error.log`, and inference counts that
   collapse partway.
5. **Fusion.** Row count and non-null ambient coverage in the merged CSV.
6. **Against the previous run of the same condition.** Throughput and power
   within a few percent, or explain why not.

The `campaign-check` command in `claude-workspace` automates these; the list
above is what it checks, so the verification does not depend on having it.

Once accepted, update **both** selection lists together — `REPORTED_CAMPAIGNS`
in `generate_paper_numbers.py` and `EXCLUDED_CAMPAIGNS` in
`generate_results.py` — plus `logs/MANIFEST.md`. Desynchronising them once put a
reported total 63 % above the sum of the table it summarised.

---

## Troubleshooting

**`i2cdetect` shows only dashes.** The bus works but nothing answers. Check
`VIN` is on pin 1 and not 2 or 4; check `SDA` and `SCL` are not swapped; reseat
all four wires. If `VIN`–`GND` measures 0 V at the module, the pins are not
soldered. A board labelled only `SHT3X` may be the analog `ARP` variant, which
never appears on I2C at all.

**Ambient temperature reads unexpectedly high.** The sensor is picking up the
Pi or the node's exhaust. Move it and re-check.

**`raspberrypi.local` does not resolve.** The hostname is whatever the Imager
set, and mDNS needs `avahi-daemon` installed. Find the address from the router,
or from `arp -a` filtered on the Raspberry Pi OUIs (`b8:27:eb`, `dc:a6:32`,
`e4:5f:01`, `28:cd:c1`, `2c:cf:67`, `d8:3a:dd`).

**The Pi's card fills up.** At 1 Hz the log grows about 2 MB a day. After a
verified collection, truncate it:

```bash
ssh <pi> 'sudo systemctl stop ambient-logger && : > ~/ambient.csv && sudo systemctl start ambient-logger'
```

**Filenames say nothing about what completed.** Every file is named
`*_48.00h_*` whatever happened. One existing run holds 40.1 h of power
telemetry under that name. Check spans, never the filename.
