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

At the DEI there is a dedicated test network, so the Pi can be reached over
Wi-Fi as it is here, and NTP works. **Add that SSID before the Pi leaves your
desk** -- once it is at the site with no keyboard and no known network, there
is no way in:

```bash
sudo nmcli con add type wifi con-name DEI ifname wlan0 ssid "<SSID>" \
     wifi-sec.key-mgmt wpa-psk wifi-sec.psk "<password>" \
     connection.autoconnect yes
nmcli -g NAME,AUTOCONNECT con show
```

Both networks can stay configured; NetworkManager picks whichever is in range.
If the DEI network is enterprise (802.1X) rather than a plain pre-shared key,
it needs `802-1x` settings instead, and that is worth testing before the trip.

The USB link stays as the fallback that depends on no site network at all --
worth having working, because a Wi-Fi that changes under you mid-campaign
otherwise ends the collection. Connect the Pi's **data** micro-USB — the middle one, not `PWR IN` — to the
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

The Pi has no real-time clock. On a network with NTP it corrects itself at
boot and this is only a verification; over the USB link alone there is no NTP
and it keeps whatever time it had, so the step is load-bearing. Run it either
way -- it costs a second, and a drifting clock pairs ambient readings with the
wrong inference events and reports nothing wrong.

The script takes the Pi's address, so give it the Wi-Fi one when that is how
it is reachable:

```bash
./scripts/sync_pi_clock.sh magnuspi@<pi-ip>
```

Then restart the logger so the file begins with the campaign:

```bash
ssh magnuspi@192.168.7.2 'sudo systemctl restart ambient-logger'
```

The ambient log must span the **whole** campaign — four models in sequence is
about eight days, roughly 700,000 samples and 17 MB. Do not stop it between
models.

---

### Do not pip in the node's venv

`~/git/llm-energy-tests/venv` on the node holds **both** `tapo`, which the
power logger imports, and `pandas`. An upgrade was interrupted at some point
and left two dist-info directories for each of `numpy`, `pandas` and `tapo`,
so `import pandas` now fails outright:

    ImportError: Can't determine version for pytz

The temptation is to repair it before a campaign. Do not. `tapo` currently
imports and logs power correctly, and any `pip install` in that venv operates
on the same site-packages: a reinstall can resolve `tapo` to a different
version and the first sign of it would be a `*_physical.csv` containing only
a header, 48 hours later. The smoke test is what proves the venv works, and
the state it proved is the state to leave alone.

Run the analysis on the laptop instead. `build_data_analysis.py` needs only
the CSVs, which `scp` copies in seconds, and the laptop's `.venv` is clean.
Repair the node's venv between campaigns, never before one, and re-run a
two-cell smoke test afterwards to confirm the power logger still works.

## 4. Run

```bash
sudo nohup ./scripts/run_benchmark_pair.sh 172800 --throttle 75 \
     > benchmark_run_pair.log 2>&1 &
```

`172800` is 48 hours per model. Root is required for the governor and the page
cache. The script reads the applied cap back from sysfs and **aborts** if it
does not match the request — the defence against the two campaigns that ran for
months without an effective cap.

### Check on the ambient logger while it still matters

The ambient file is collected only after the campaign ends, so a logger that
died on day two is discovered on day eight -- when there is no campaign left
to repeat. Check it every day or so. It costs one command and needs no copy:

```bash
ssh magnuspi@192.168.7.2 'systemctl is-active ambient-logger; \
    grep -c "^[0-9]" ~/ambient.csv; date +%s'
```

At 1 Hz the sample count must track the seconds elapsed since the logger
started. Falling behind means dropped reads; running ahead means duplicate
stamps, which should no longer be possible but is worth seeing. Growth stopped
altogether means the process is gone or the sensor is off the bus, and
`journalctl -u ambient-logger -n 20` says which.

The log grows about 2 MB a day, so eight days is roughly 17 MB -- the card is
not the risk. Power is: anything that cuts the Pi's supply ends the collection
silently. Never power it from the node's USB port or from a laptop, both of
which drop power when the machine suspends. That is how 17 hours went missing
here on 2026-09-07.

### Recovering from an interruption

A campaign that loses power — a building move, a supply failure, an accidental
reboot — cannot be resumed. The affected model's 48 h must be re-run whole.

The premise of the measurement is continuous sustained load, and the phenomenon
under study is accumulated state, which a reboot clears. Splicing a partial
window onto its continuation produces a campaign that looks complete and is
not, which is the failure mode this project has already met twice from a
different cause.

The models that already closed are unaffected and stay where they are.

**Before the power goes**, if you get warning:

```bash
sudo pkill -f run_benchmark_pair                 # clean stop, no half-written rows
cd logs/<campaign>/deep_aging
mkdir -p ../interrupted
mv <model>_48.00h_* ../interrupted/              # keep the partial run as evidence
ssh magnuspi@<pi> 'sudo systemctl stop ambient-logger'
```

Archiving matters: the loggers open their outputs with `>`, so a re-run
overwrites the partial files rather than appending to them. Nothing is spliced,
but nothing is kept either.

**After power returns**, in this order:

```bash
uname -r                                         # must be the campaign's kernel
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
ssh magnuspi@<pi> 'systemctl is-active ambient-logger; date'
./scripts/sync_pi_clock.sh magnuspi@<pi>         # no RTC; NTP may not have run yet
```

Then re-run the one model, into the campaign it belongs to:

```bash
sudo nohup ./scripts/run_benchmark_pair.sh 172800 \
     --models "deepseek-v2:lite" \
     --log-dir "$PWD/logs/<campaign>" \
     > benchmark_<model>_restart.log 2>&1 &
```

`--log-dir` is what keeps the re-run beside the models that completed; without
it the script writes to a directory named for today's date and splits one
campaign across two. Confirm the new `run_config.log` entries carry the same
governor, EPP and kernel as the earlier ones — a reboot resets the governor,
and the script re-applies it, but the log is where you verify that it did.

**The ambient record will have a gap**, and that is correct rather than
something to hide. `collect_ambient.sh` reports it as partial coverage, and the
campaign's ambient-adjusted claims are weakened for the affected window. Report
the interruption rather than papering over it.

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
`SDA` and `SCL` are not swapped and reseat all four wires. A board labelled
only `SHT3X` may be the analog `ARP` variant, which never appears on I2C at
all.

**The sensor answers but never measures.** `i2cdetect` finds `0x44`, the status
register reads back cleanly and with a valid CRC, and every measurement command
fails with `Errno 5` or returns `0xff` bytes. Bus speed makes no difference.

This is `VIN` not powering the sensor. The chip runs parasitically off the I2C
pull-ups, through the protection diodes on `SDA` and `SCL`: microamperes, which
is enough for the digital core to acknowledge its address and return registers,
and nowhere near enough to run an ADC conversion. Every symptom follows from
that, which is why the bus looks healthy while nothing reads.

Measure between `VIN` and `GND` **on the module**, not at the Pi header. It
must read 3.3 V. Zero, or a few tenths, confirms it. In order of likelihood: a
cold solder joint on `VIN` -- it holds mechanically and does not conduct, and
it is invisible; the wire on the wrong pin -- `VIN` belongs on pin **1**, since
pins 2 and 4 are 5 V and would put the module's pull-ups above what the Pi's
GPIO tolerate; or a Dupont socket not fully seated.

If `VIN` reads 3.3 V and measurements still fail, the sensing element is dead
while the digital interface survived. Replace the module.

To tell these apart, read the status register directly:

```bash
sudo /usr/sbin/i2ctransfer -y 1 w2@0x44 0xF3 0x2D && \
sudo /usr/sbin/i2ctransfer -y 1 r3@0x44
```

A CRC-valid answer (`0x80 0x10 0xe1` is a normal post-reset status) proves the
chip is an SHT3x and its interface is alive, which narrows the fault to power
or to the sensing element.

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

## Ambient logging over Bluetooth (ThermoPro TP351S)

The SHT31-D over I2C has been the weak link in the ambient record: a loose
VDD/GND contact once produced 30,449 consecutive failed reads and left
coverage at 73.5 %. The BLE sensor replaces the wire, and with it the whole
class of failure, because nothing is opened: the sensor broadcasts and the
logger listens. No pairing, no GATT connection, no session to lose.

**It runs on the node.** That is a decision with a cost and it is worth being
clear about it. Ambient measurement belongs outside the machine under test,
and the Pi was that outside; running it on the node puts a second collector
inside the measured envelope, beside the 1 Hz power poll already there. Two
things keep that small and, more importantly, **constant across scenarios so
that it cancels in every comparison**: the scan is passive, and the radio is
on for eight seconds a minute rather than continuously. Constant is what
matters. Zero stopped being available the moment the collector moved in.

**Put the node's IP traffic on Ethernet.** The AX211 is a combined Wi-Fi and
Bluetooth part sharing one radio front end, and the power meter is polled over
the network every second. The node has `eno1` as well as `wlp0s20f3`; leaving
the wired link as the default route keeps the two off each other.

### State of the node, checked remotely on 2026-10-20

Reached over Tailscale as `ubuntu@ubuntu-llm` (100.121.75.122). What is
already done, and what is not:

| | |
|---|---|
| kernel adapter `hci0` | present, driver loaded |
| `bluez` package | **NOT INSTALLED** -- this is the only real gap |
| `bluetooth.service` | inactive, because the package is absent |
| `bleak`, `thermopro-ble` 1.1.4 | installed under `--user` |
| the four scripts | deployed to `~/git/llm-energy-tests`, checksums match |
| logger in simulation | runs, correct schema |
| probe | fails with `org.bluez was not provided by any .service files`, which is the right error for a missing daemon |
| default route | `eno1`, wired, as wanted -- `wlp0s20f3` is up as backup at metric 600 |
| campaign running | none; load average 0.00, Ollama idle |

Two commands need a password and so were left undone:

```bash
sudo apt install -y bluez          # 5.72-0ubuntu5.8, available
sudo systemctl enable --now bluetooth
```

After those, `scripts/ble_probe_thermopro.py` should reach the adapter even
with no sensor present -- it will simply find nothing. That alone is worth
running, because it separates "the stack works" from "the sensor decodes".

**The node's checkout is far behind.** Its HEAD is `d985e86`, from the Zenodo
release work. The four BLE files were copied in directly rather than pulled,
so as not to drag months of changes onto a machine mid-programme. Before the
next campaign, that checkout wants updating deliberately -- the orchestration
there predates the per-campaign version recording.

### One command, on the node, with the sensor beside it

```bash
./scripts/setup_ambient_node.sh --check            # look only
AMBIENT_NAME=C505 ./scripts/setup_ambient_node.sh  # probe, ask, then install
```

`AMBIENT_NAME` binds the service to one sensor by a substring of its
advertised name -- `C505` for `TP351S (C505)`. Without it the logger takes
any TP35 or TP39 device in range, which is right until a second one is ever
within a few metres of the node, and wrong silently when it is. The script
prints which of the two it is about to do. The other knobs are
`AMBIENT_INTERVAL` (60 s), `AMBIENT_SCAN_WINDOW` (8 s), `AMBIENT_LOG` and
`AMBIENT_PYTHON`.

It resolves the user, the paths and the interpreter itself, so there is
nothing to edit first. Step 4 is the one that matters.

### The question step 4 answers

`thermopro-ble` gates on `name.startswith(("TP35", "TP39", "TP96", "TP97"))`,
so **TP351S passes** and falls into the generic TP3 branch -- which that
library's own comments say was written for the TP357S, TP397 and TP393. The
TP351S is untested there. The probe prints, for each advertisement, the raw
manufacturer payload, what `thermopro-ble` makes of it, and what the
documented byte layout gives independently.

**The sensor has no display.** The reference is the vendor phone app showing
it: have the app open on the same reading while the probe runs. The app is the
ground truth here, not either decoder. The probe never connects, so it cannot
interfere with whatever the app is doing.

- All three agree -> answer yes, it installs.
- The two decoders agree with each other but not with the app -> the
  offsets are wrong for this model; keep the hex and the layout gets
  re-derived.
- The library fails and the manual decode works -> drop the dependency.

To run the probe alone, without any of the rest:

```bash
python3 scripts/ble_probe_thermopro.py --seconds 90
```

### Confirmed on 2026-10-20: the TP351S decodes

Probed from Windows with the sensor on the desk. It advertises as
`TP351S (C505)` from `FF:FF:81:1A:C5:05`, company `0x0bc2`, five-byte payload:

```
payload 0136223301  ->  26.7 C, 54 % RH, battery 100 %
```

Both decoders agree, and the arithmetic was redone by hand from the
reassembled frame `c20b0136223301` rather than taken from either of them:
`data[1:3]` = `0b 01` = 267 tenths = 26.7 C, `data[3]` = 54, `data[4] & 3` = 2
= full battery. Seven bytes, above the six the library's TP3 branch requires.
**So the TP357S layout does hold for the TP351S**, and the open question in
this runbook is closed.

**Confirmed differentially, which is stronger than any app.** The sensor was
held under a leg and probed again. Exactly two bytes changed, and they are the
two the layout claims are variable:

```
antes:  c2 0b 01 36 22 33 01   ->  26.7 C, 54 %
depois: c2 21 01 3b 22 33 01   ->  28.9 C, 59 %
         ^^       ^^
         temp     humidity
```

`data[0]`, `data[2]`, and `data[4..6]` held still. Temperature rose 2.2 C and
humidity 5 points, which is what body contact does. The scale factor is
settled by the magnitude alone: at /1 the change would read +22 C, at /100
+0.02 C, and neither is what a leg does to a thermometer. Only /10 gives a
plausible answer.

A second thing falls out of it. The *company id* changed, `0x0bc2` to
`0x21c2`, which a real assigned manufacturer identifier cannot do. That is
direct confirmation of why `decode()` indexes across it: these sensors
broadcast a flat frame and the host stack carves a company id out of its first
two bytes because the manufacturer-data field has nowhere else to put them.
The byte that moved, `0x0b` to `0x21`, is the temperature's low byte sitting
in what Windows and BlueZ both call the company id.

**Bind by name, not by address.** `FF:FF:81:1A:C5:05` has the top bits of a
static random address: it may survive a battery change, it may not, and
nothing promises either way. The advertised name carries its own suffix, so
`--name C505` identifies this unit among several without depending on an
address that is not ours to rely on.

### What the logger guarantees

Same schema as the I2C logger, `timestamp,ambient_c,humidity_pct`, appended
and never rewritten. Three properties worth knowing:

- **One row a minute, radio on for eight seconds of it**, listening at the end
  of each cycle so the row carries a reading taken moments before it. A room
  does not move faster, and `merge_asof` carries the last reading forward to
  every inference regardless of how sparse it is.
- **An interval with no fresh advertisement writes nothing** rather than
  repeating a stale value. Gaps are honest; imputed rows are not. A reading
  older than 90 s counts as absent.
- **The timestamp sequence is strictly increasing**, across restarts too. This
  matters more than it looks: `build_data_analysis.py` *sorts* the ambient log
  before merging rather than rejecting it, so a row written out of order after
  a clock step is not an error there -- it is silently reattributed to the
  wrong moment. The logger drops such rows and says so in the journal. The
  I2C logger has the same exposure and has not been changed.

### Collecting it

The log is local now, so there is nothing to fetch over SSH. Copy it into the
campaign directory when the campaign ends:

```bash
cp ~/ambient_ble.csv logs/<campaign>/deep_aging/ambient_$(date +%Y%m%d).csv
```

**One `*ambient*.csv` per campaign directory.** The fusion globs for that
pattern and takes the most recent; two files there is a silent coin toss.

### The Pi

`scripts/deploy_pi.sh` and `scripts/collect_ambient.sh` still work and are
left in place. They are the path for the I2C sensor if it is ever wanted back,
or for running a second sensor off the node as a cross-check.

### Verifying the sensor from Windows, before going anywhere

The laptop has Bluetooth; WSL2 does not. `bleak` works on Windows, and both
scripts are stdlib plus `bleak`, with nothing Linux-specific in them. So the
decode can be confirmed at home, against the sensor on the desk, days before
the node is touched. In PowerShell:

First check there is a real Python. `py` is often absent, and the `python.exe`
in `WindowsApps` is a two-byte Store stub that opens the Microsoft Store rather
than running anything:

```powershell
python --version        # "Python 3.x.y" is real; opening the Store is not
```

If it is the stub, `winget` installs the real thing and puts both `py` and
`python` on PATH:

```powershell
winget install -e --id Python.Python.3.12
```

Close and reopen PowerShell afterwards, so PATH is picked up. Then:

```powershell
py -m pip install bleak thermopro-ble
$repo = "\\wsl.localhost\Ubuntu-24.04\home\magnus\git\llm-energy-tests"
py "$repo\scripts\ble_probe_thermopro.py" --seconds 90
```

Do not reach for the Python inside LibreOffice, which is on this machine at
3.8: it is that application's, and current `bleak` wants 3.9 or later.

If PowerShell objects to the UNC path, copy the two files somewhere local
first; they have no other dependency on the repository.

Compare what prints against the vendor app's reading. A match here means the
`--install` step on the node is a formality rather than a gamble, which is the
whole point of doing it early. Note that Windows cannot scan in passive mode,
so bleak will scan actively instead -- the sensor is unaffected, it broadcasts
either way, and only the radio behaviour of the laptop differs.

A minute of logging can be exercised there too, without a sensor:

```powershell
py "$repo\src\ambient_logger_ble.py" sample.csv --simulate --interval 2 --scan-window 1
```
