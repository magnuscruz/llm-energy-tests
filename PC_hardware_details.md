# PC Hardware Details

## Resumo

- **Motherboard:** ROG STRIX B760-G GAMING WIFI
- **Sistema:** System Product Name (SKU)
- **CPU:** 13th Gen Intel(R) Core(TM) i5-13500
- **Memória total:** 64 GiB (2 × 32 GiB DIMM, 4800 MHz)
- **Discos:** 256GB KINGSTON SKC6002 (`/dev/sda`), 2TB ST2000DM008-2UB1 (`/dev/sdb`)
- **Rede:** Ethernet `I226-V` (eno1), WiFi `AX211` (wlp0s20f3)
- **GPU (integrada):** AlderLake-S GT1

---

## Detalhes principais

### CPU

- Modelo: 13th Gen Intel(R) Core(TM) i5-13500
- CPUs reportados: 20
- Cores por socket: 14
- Threads por core: 2
- Frequência (máx): 4800 MHz, (mín): 800 MHz

### Memória

- Total: 64 GiB System Memory
- DIMMs instaladas:
  - 32 GiB DIMM Synchronous 4800 MHz (slot /0/c/1)
  - 32 GiB DIMM Synchronous 4800 MHz (slot /0/c/3)

### Armazenamento

- `/dev/sda` — 256GB KINGSTON SKC6002
  - `/dev/sda1` — 511 MiB Windows FAT
  - `/dev/sda2` — 237 GiB EXT4
  - `/dev/sda3` — 976 MiB Linux swap
- `/dev/sdb` — 2TB ST2000DM008-2UB1
  - `/dev/sdb1` — 1074 MiB Windows FAT
  - `/dev/sdb2` — 2 GiB EXT4
  - `/dev/sdb3` — 1859 GiB EFI partition

### Rede e Conectividade

- Ethernet: `Intel Ethernet Controller I226-V` (eno1)
- WiFi: `Raptor Lake-S PCH CNVi WiFi` (AX211) — interface `wlp0s20f3`
- USB: Raptor Lake USB 3.2 Gen 2x2 XHCI

### Áudio

- Raptor Lake High Definition Audio Controller (card0)

---

## Saída bruta (raw)

O bloco abaixo contém a saída original usada para compilar este resumo.

```
H/W path       Device     Class          Description
====================================================
                          system         System Product Name (SKU)
/0                        bus            ROG STRIX B760-G GAMING WIFI
/0/0                      memory         64KiB BIOS
/0/c                      memory         64GiB System Memory
/0/c/0                    memory         [empty]
/0/c/1                    memory         32GiB DIMM Synchronous 4800 MHz (0.2 ns)
/0/c/2                    memory         [empty]
/0/c/3                    memory         32GiB DIMM Synchronous 4800 MHz (0.2 ns)
/0/1b                     memory         288KiB L1 cache
/0/1c                     memory         192KiB L1 cache
/0/1d                     memory         7680KiB L2 cache
/0/1e                     memory         24MiB L3 cache
/0/1f                     memory         256KiB L1 cache
/0/20                     memory         512KiB L1 cache
/0/21                     memory         4MiB L2 cache
/0/22                     memory         24MiB L3 cache
/0/23                     processor      13th Gen Intel(R) Core(TM) i5-13500
/0/100                    bridge         Intel Corporation
/0/100/2       /dev/fb0   display        AlderLake-S GT1
/0/100/a                  generic        Platform Monitoring Technology
/0/100/e                  storage        Volume Management Device NVMe RAID Controller
/0/100/14                 bus            Raptor Lake USB 3.2 Gen 2x2 (20 Gb/s) XHCI Host Controller
/0/100/14/0    usb1       bus            xHCI Host Controller
/0/100/14/0/2             input          AURA LED Controller
/0/100/14/0/a             bus            ASM107x
/0/100/14/0/b             bus            USB2.0 Hub
/0/100/14/0/e             communication  AX211 Bluetooth
/0/100/14/1    usb2       bus            xHCI Host Controller
/0/100/14/1/9             bus            ASM107x
/0/100/14.2               memory         RAM memory
/0/100/14.3    wlp0s20f3  network        Raptor Lake-S PCH CNVi WiFi
/0/100/15                 bus            Raptor Lake Serial IO I2C Host Controller #0
/0/100/15.1               bus            Raptor Lake Serial IO I2C Host Controller #1
/0/100/15.2               bus            Raptor Lake Serial IO I2C Host Controller #2
/0/100/16                 communication  Raptor Lake CSME HECI #1
/0/100/17      scsi4      storage        Raptor Lake SATA AHCI Controller
/0/100/17/0    /dev/sda   disk           256GB KINGSTON SKC6002
/0/100/17/0/1  /dev/sda1  volume         511MiB Windows FAT volume
/0/100/17/0/2  /dev/sda2  volume         237GiB EXT4 volume
/0/100/17/0/3  /dev/sda3  volume         976MiB Linux swap volume
/0/100/17/1    /dev/sdb   disk           2TB ST2000DM008-2UB1
/0/100/17/1/1  /dev/sdb1  volume         1074MiB Windows FAT volume
/0/100/17/1/2  /dev/sdb2  volume         2GiB EXT4 volume
/0/100/17/1/3  /dev/sdb3  volume         1859GiB EFI partition
... (output truncated)
```

Para ver a saída completa, consulte o ficheiro original `PC_hardware_details.txt`.
