"""Cross-OS parser tests for ``src/scripts/about_info.py``.

These exercise the parse_* functions directly with captured command
output from real distros and hardware. The point is to prove the
parsers extract the right *value* — not the right rendered string in
QML — across the locales, kernels and DMI placeholders the helper is
asked to digest in the wild.

Every fixture is annotated with where it came from. When adding a new
distro/edge-case, capture the raw output with::

    LC_ALL=C lscpu
    cat /proc/cpuinfo | head -40
    LC_ALL=C lspci -mm -nn
    lsblk -bdno NAME,SIZE,TYPE,MODEL
    cat /etc/os-release
    cat /sys/devices/virtual/dmi/id/sys_vendor
    cat /sys/devices/virtual/dmi/id/product_name
    free -b
    dmidecode -t memory
    cat /proc/meminfo | head -2

and paste it into the fixture dict.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "src/scripts"
sys.path.insert(0, str(SCRIPTS))

# Pure-function imports — no I/O, no live commands.
from about_info import (  # noqa: E402
    collect,
    first_non_empty,
    format_network,
    merge_cpu,
    parse_bios_year,
    parse_cpuinfo,
    parse_default_iface,
    parse_df_root,
    parse_dmi_string,
    parse_dmidecode_cpu,
    parse_dmidecode_memory,
    parse_drm_fallback,
    parse_etc_issue,
    parse_findmnt_root,
    parse_free_bytes,
    parse_glxinfo,
    parse_lsb_release,
    parse_lsblk,
    parse_lscpu,
    parse_lspci_gpu,
    parse_mac,
    parse_meminfo,
    parse_nproc,
    parse_os_release,
    parse_proc_mounts_root,
    parse_proc_route_default,
    parse_uname,
    parse_vendor,
)


# ── lscpu (English, LC_ALL=C) ────────────────────────────────────────────

LSCPU_CACHYOS_AMD_RYZEN9 = """\
Architecture:             x86_64
  CPU op-mode(s):         32-bit, 64-bit
  Address sizes:          48 bits physical, 48 bits virtual
  Byte Order:             Little Endian
CPU(s):                   24
  On-line CPU(s) list:    0-23
Vendor ID:                AuthenticAMD
  Model name:             AMD Ryzen 9 9900X 12-Core Processor
    CPU family:           26
    Model:                68
    Thread(s) per core:   2
    Core(s) per socket:   12
    Socket(s):            1
    Stepping:             0
    Frequency boost:      enabled
    CPU(s) scaling MHz:   62%
    CPU max MHz:          5648.4370
    CPU min MHz:          600.0000
    BogoMIPS:             8983.18
"""

LSCPU_UBUNTU_INTEL_I7 = """\
Architecture:            x86_64
CPU op-mode(s):          32-bit, 64-bit
Byte Order:              Little Endian
CPU(s):                  8
On-line CPU(s) list:     0-7
Vendor ID:               GenuineIntel
Model name:              Intel(R) Core(TM) i7-1165G7 CPU @ 2.80GHz
CPU family:              6
Model:                   140
Thread(s) per core:      2
Core(s) per socket:      4
Socket(s):               1
Stepping:                1
CPU max MHz:             4700.0000
CPU min MHz:             400.0000
"""

LSCPU_FEDORA_INTEL_XEON = """\
Architecture:            x86_64
CPU(s):                  32
Vendor ID:               GenuineIntel
Model name:              Intel(R) Xeon(R) Gold 6242 CPU @ 2.80GHz
Thread(s) per core:      2
Core(s) per socket:      16
Socket(s):               1
"""

LSCPU_OPENSUSE_AMD_THREADRIPPER = """\
Architecture:            x86_64
CPU(s):                  64
Vendor ID:               AuthenticAMD
Model name:              AMD Ryzen Threadripper 3970X 32-Core Processor
Thread(s) per core:      2
Core(s) per socket:      32
Socket(s):               1
"""

# Captured with LANG=fr_FR.UTF-8. Lscpu translates EVERY label. This is
# the exact stdout that broke v0.13.11 for users in non-English locales.
LSCPU_LOCALE_FR = """\
Architecture :              x86_64
Mode(s) opératoire(s) des processeurs : 32-bit, 64-bit
Boutisme :                  Little Endian
Processeur(s) :             8
Liste de processeur(s) en ligne : 0-7
Identifiant constructeur :  GenuineIntel
Nom de modèle :             Intel(R) Core(TM) i7-1165G7 CPU @ 2,80GHz
Famille de processeur :     6
Cœur(s) par socket :        4
Socket(s) :                 1
"""


def test_lscpu_cachyos_amd_ryzen9():
    parsed = parse_lscpu(LSCPU_CACHYOS_AMD_RYZEN9)
    assert parsed["model"] == "AMD Ryzen 9 9900X"
    assert parsed["cores"] == "24 (12 physical)"


def test_lscpu_ubuntu_intel_i7():
    parsed = parse_lscpu(LSCPU_UBUNTU_INTEL_I7)
    assert parsed["model"] == "Intel Core i7-1165G7"
    assert parsed["cores"] == "8 (4 physical)"


def test_lscpu_fedora_intel_xeon():
    parsed = parse_lscpu(LSCPU_FEDORA_INTEL_XEON)
    assert parsed["model"] == "Intel Xeon Gold 6242"
    assert parsed["cores"] == "32 (16 physical)"


def test_lscpu_opensuse_threadripper():
    parsed = parse_lscpu(LSCPU_OPENSUSE_AMD_THREADRIPPER)
    assert parsed["model"] == "AMD Ryzen Threadripper 3970X"
    assert parsed["cores"] == "64 (32 physical)"


def test_lscpu_french_locale_fails_silently():
    """Without LC_ALL=C, the English regex misses every field — proving
    why the helper forces the locale before calling lscpu."""
    parsed = parse_lscpu(LSCPU_LOCALE_FR)
    assert parsed["model"] == ""
    assert parsed["cores"] == ""


# ── /proc/cpuinfo (the locale-proof fallback) ────────────────────────────

CPUINFO_INTEL = """\
processor	: 0
vendor_id	: GenuineIntel
cpu family	: 6
model		: 140
model name	: Intel(R) Core(TM) i7-1165G7 CPU @ 2.80GHz
stepping	: 1
cpu MHz		: 2800.000
cache size	: 12288 KB
physical id	: 0
siblings	: 8
core id		: 0
cpu cores	: 4
apicid		: 0

processor	: 1
vendor_id	: GenuineIntel
model name	: Intel(R) Core(TM) i7-1165G7 CPU @ 2.80GHz
physical id	: 0
cpu cores	: 4

processor	: 2
vendor_id	: GenuineIntel
model name	: Intel(R) Core(TM) i7-1165G7 CPU @ 2.80GHz
physical id	: 0
cpu cores	: 4

processor	: 3
vendor_id	: GenuineIntel
model name	: Intel(R) Core(TM) i7-1165G7 CPU @ 2.80GHz
physical id	: 0
cpu cores	: 4

processor	: 4
vendor_id	: GenuineIntel
model name	: Intel(R) Core(TM) i7-1165G7 CPU @ 2.80GHz
physical id	: 0
cpu cores	: 4

processor	: 5
vendor_id	: GenuineIntel
model name	: Intel(R) Core(TM) i7-1165G7 CPU @ 2.80GHz
physical id	: 0
cpu cores	: 4

processor	: 6
vendor_id	: GenuineIntel
model name	: Intel(R) Core(TM) i7-1165G7 CPU @ 2.80GHz
physical id	: 0
cpu cores	: 4

processor	: 7
vendor_id	: GenuineIntel
model name	: Intel(R) Core(TM) i7-1165G7 CPU @ 2.80GHz
physical id	: 0
cpu cores	: 4
"""

# Raspberry Pi 5 — no model name field, has Hardware/Model instead.
CPUINFO_ARM_RPI5 = """\
processor	: 0
BogoMIPS	: 108.00
Features	: fp asimd evtstrm aes pmull sha1 sha2 crc32
CPU implementer	: 0x41
CPU architecture: 8
CPU variant	: 0x4
CPU part	: 0xd0b
CPU revision	: 1

processor	: 1
BogoMIPS	: 108.00
Features	: fp asimd evtstrm aes pmull sha1 sha2 crc32
CPU implementer	: 0x41
CPU architecture: 8

processor	: 2
processor	: 3

Hardware	: BCM2835
Model		: Raspberry Pi 5 Model B Rev 1.0
"""


def test_cpuinfo_intel_full():
    parsed = parse_cpuinfo(CPUINFO_INTEL)
    assert parsed["model"] == "Intel Core i7-1165G7"
    assert parsed["cores"] == "8 (4 physical)"


def test_cpuinfo_arm_rpi5_falls_back_to_model_line():
    parsed = parse_cpuinfo(CPUINFO_ARM_RPI5)
    assert parsed["model"] == "Raspberry Pi 5 Model B Rev 1.0"
    assert parsed["cores"] == "4"


def test_cpuinfo_empty_returns_empty():
    parsed = parse_cpuinfo("")
    assert parsed == {"model": "", "cores": ""}


def test_merge_cpu_prefers_first_non_empty():
    """``merge_cpu`` keeps the first useful value per field, so a
    locale-blanked lscpu still composes a full result with cpuinfo."""
    merged = merge_cpu(
        {"model": "", "cores": ""},  # lscpu came back blank (fr_FR)
        parse_cpuinfo(CPUINFO_INTEL),
    )
    assert merged["model"] == "Intel Core i7-1165G7"
    assert merged["cores"] == "8 (4 physical)"


def test_merge_cpu_first_source_wins_when_complete():
    merged = merge_cpu(
        {"model": "AMD Ryzen 9 9900X", "cores": "24 (12 physical)"},
        parse_cpuinfo(CPUINFO_INTEL),
    )
    assert merged["model"] == "AMD Ryzen 9 9900X"
    assert merged["cores"] == "24 (12 physical)"


# ── dmidecode CPU / nproc fallbacks ──────────────────────────────────────

def test_dmidecode_cpu_strips_trim():
    assert parse_dmidecode_cpu("AMD Ryzen 7 5800X 8-Core Processor\n") \
        == "AMD Ryzen 7 5800X"


def test_dmidecode_cpu_handles_dmi_chassis_string():
    assert parse_dmidecode_cpu("Intel(R) Core(TM) i9-13900K CPU @ 3.00GHz\n") \
        == "Intel Core i9-13900K"


def test_nproc_simple_line():
    assert parse_nproc("16\n") == "16"


def test_nproc_garbage_returns_empty():
    assert parse_nproc("not a number\n") == ""


# ── memory ───────────────────────────────────────────────────────────────

MEMINFO_64G = """\
MemTotal:       65728500 kB
MemFree:         1322192 kB
MemAvailable:   60111180 kB
"""

# Note: hardware reserves ~280 MiB for the integrated GPU on this Dell
# laptop, so MemTotal reads as ~15.7 GiB instead of 16.
MEMINFO_16G_WITH_HOLE = """\
MemTotal:       16389648 kB
MemFree:         1234567 kB
"""

# Some VPS profiles end up with weird multiples.
MEMINFO_3G = """\
MemTotal:        3145728 kB
"""


def test_meminfo_snaps_to_nearest_sane_size():
    assert parse_meminfo(MEMINFO_64G) == "64 GB"
    assert parse_meminfo(MEMINFO_16G_WITH_HOLE) == "16 GB"
    assert parse_meminfo(MEMINFO_3G) == "3 GB"


def test_meminfo_empty_returns_empty():
    assert parse_meminfo("") == ""
    assert parse_meminfo("NoMatch:    1234\n") == ""


def test_free_bytes_matches_meminfo():
    """``free -b`` and ``/proc/meminfo`` should produce the same snap."""
    free = """\
               total        used        free      shared  buff/cache   available
Mem:     67305984000  3000000000 35000000000   100000000 29000000000 64000000000
Swap:    17179869184           0 17179869184
"""
    assert parse_free_bytes(free) == "64 GB"


def test_dmidecode_memory_sums_populated_slots():
    """Two 32 GB DIMMs populated + 2 empty slots → 64 GB."""
    dmi = """\
Memory Device
	Total Width: 64 bits
	Size: 32 GB
	Locator: DIMM_A1

Memory Device
	Total Width: Unknown
	Size: No Module Installed
	Locator: DIMM_A2

Memory Device
	Total Width: 64 bits
	Size: 32 GB
	Locator: DIMM_B1

Memory Device
	Size: No Module Installed
	Locator: DIMM_B2
"""
    assert parse_dmidecode_memory(dmi) == "64 GB"


def test_dmidecode_memory_handles_mb_dimms():
    """Older boards report DDR2 modules in MB. Sum should round to GB."""
    dmi = """\
Memory Device
	Size: 512 MB
Memory Device
	Size: 512 MB
Memory Device
	Size: 1024 MB
Memory Device
	Size: 1024 MB
"""
    assert parse_dmidecode_memory(dmi) == "3 GB"


# ── GPU ──────────────────────────────────────────────────────────────────

LSPCI_AMD_NAVI = """\
00:00.0 "Host bridge [0600]" "Advanced Micro Devices, Inc. [AMD] [1022]" "Device [14d8]" -rc0 -p00 "" ""
03:00.0 "VGA compatible controller [0300]" "Advanced Micro Devices, Inc. [AMD/ATI] [1002]" "Navi 48 [Radeon RX 9070/9070 XT/9070 GRE] [7550]" -rc0 -p00 "Sapphire Technology Limited [1da2]" "Device [3490]"
"""

LSPCI_INTEL_IRIS_XE = """\
00:02.0 "VGA compatible controller [0300]" "Intel Corporation [8086]" "TigerLake-LP GT2 [Iris Xe Graphics] [9a49]" -ra1 -p00 "Dell [1028]" "Device [099e]"
"""

LSPCI_HYBRID_INTEL_NVIDIA = """\
00:02.0 "VGA compatible controller [0300]" "Intel Corporation [8086]" "AlderLake-P Integrated Graphics Controller [46a8]" -r0c -p00 "Lenovo [17aa]" "Device [22f4]"
01:00.0 "3D controller [0302]" "NVIDIA Corporation [10de]" "GA107M [GeForce RTX 3050 Mobile] [25a2]" -ra1 -p00 "Lenovo [17aa]" "Device [3a4a]"
"""

LSPCI_VM_VIRTIO = """\
00:01.0 "VGA compatible controller [0300]" "Red Hat, Inc. [1af4]" "Virtio 1.0 GPU [1050]" -ra1 -p00 "Red Hat, Inc. [1af4]" "Device [1100]"
"""


def test_lspci_amd_radeon():
    assert parse_lspci_gpu(LSPCI_AMD_NAVI) \
        == "AMD Radeon RX 9070/9070 XT/9070 GRE"


def test_lspci_intel_iris_xe():
    assert parse_lspci_gpu(LSPCI_INTEL_IRIS_XE) \
        == "Intel Iris Xe Graphics"


def test_lspci_hybrid_intel_plus_nvidia():
    out = parse_lspci_gpu(LSPCI_HYBRID_INTEL_NVIDIA)
    assert "Intel" in out
    assert "NVIDIA" in out
    assert "GeForce RTX 3050 Mobile" in out
    assert " + " in out


def test_lspci_virtio_vm():
    assert "Virtio" in parse_lspci_gpu(LSPCI_VM_VIRTIO)


def test_lspci_no_gpu_returns_empty():
    """Headless / dGPU-only-disabled — no VGA/3D/Display class on bus."""
    out = parse_lspci_gpu(
        '00:00.0 "Host bridge [0600]" "Intel Corporation [8086]" "Device [3e20]"\n'
    )
    assert out == ""


def test_drm_fallback_intel_amd_hybrid():
    """Two cards on /sys/class/drm — Intel iGPU + AMD dGPU."""
    vendors = "0x8086\n0x1002\n"
    assert parse_drm_fallback(vendors) == "Intel + AMD"


def test_drm_fallback_unknown_vendor_skipped():
    """Vendors not in the small lookup table just don't contribute —
    they don't crash the parser."""
    assert parse_drm_fallback("0xdead\n0x10de\n") == "NVIDIA"


def test_glxinfo_renderer_string():
    out = """\
name of display: :0
display: :0  screen: 0
direct rendering: Yes
OpenGL vendor string: Intel
OpenGL renderer string: Mesa Intel(R) Xe Graphics (TGL GT2)
OpenGL core profile version string: 4.6 (Core Profile) Mesa 24.0.0
"""
    assert "Intel" in parse_glxinfo(out)
    assert "Xe Graphics" in parse_glxinfo(out)


# ── disk ─────────────────────────────────────────────────────────────────

LSBLK_NVME_PLUS_USB = """\
nvme0n1     512110190592   disk Samsung SSD 970 EVO Plus 500GB
sda          15728640000   disk SanDisk USB 3.2Gen1
sr0                    0   rom
"""


def test_lsblk_matches_root_to_nvme():
    out = parse_lsblk(LSBLK_NVME_PLUS_USB, "/dev/nvme0n1p2")
    assert out.startswith("500 GB") or out.startswith("480 GB") or out.startswith("512 GB")
    assert "Samsung SSD" in out


def test_lsblk_falls_back_to_first_disk_when_no_root():
    out = parse_lsblk(LSBLK_NVME_PLUS_USB, "")
    assert "Samsung SSD" in out


def test_lsblk_handles_mapper_root():
    """LUKS / LVM: root device is /dev/mapper/foo, which doesn't appear
    in lsblk -d output. We fall back to the first disk-type row."""
    out = parse_lsblk(LSBLK_NVME_PLUS_USB, "/dev/mapper/luks-abc-123")
    assert "Samsung SSD" in out


def test_lsblk_partition_suffix_stripped():
    """Both ``nvme0n1p2`` → ``nvme0n1`` and ``sda3`` → ``sda``."""
    out = parse_lsblk(LSBLK_NVME_PLUS_USB, "/dev/sda3")
    assert "SanDisk" in out


LSBLK_TWO_NVMES = """\
nvme0n1     500107862016   disk Samsung SSD 970 EVO Plus 500GB
nvme1n1    2000398934016   disk WD_BLACK SN850X 2000GB
"""


def test_lsblk_picks_correct_nvme_namespace():
    """Two NVMe drives, root on the second — must match nvme1n1, not
    fall back to first. This catches the regression where _base_disk
    stripped the namespace digit (``nvme0n1`` → ``nvme0n``) and the
    matcher silently picked the wrong drive."""
    out = parse_lsblk(LSBLK_TWO_NVMES, "/dev/nvme1n1p3")
    assert "WD_BLACK" in out
    assert "Samsung" not in out


def test_lsblk_emmc_partition_strip():
    """mmcblk follows the ``<base>p<N>`` convention like NVMe."""
    lsblk = "mmcblk0     31268536320 disk SDIN8DE2-32G\n"
    out = parse_lsblk(lsblk, "/dev/mmcblk0p1")
    assert "SDIN8DE2-32G" in out


def test_lsblk_virtio_partition_strip():
    """VirtIO disks (``vda``) follow SCSI-style ``<letters><N>`` naming."""
    lsblk = "vda     53687091200 disk\n"
    out = parse_lsblk(lsblk, "/dev/vda1")
    assert out  # something rendered


def test_lsblk_xen_partition_strip():
    """Xen blkfront uses ``xvda`` — SCSI-style suffix."""
    lsblk = "xvda     21474836480 disk\n"
    out = parse_lsblk(lsblk, "/dev/xvda1")
    assert out


def test_findmnt_root_first_field():
    assert parse_findmnt_root("/dev/nvme0n1p2\n") == "/dev/nvme0n1p2"
    assert parse_findmnt_root("/dev/mapper/luks-x /mnt other\n") \
        == "/dev/mapper/luks-x"


def test_proc_mounts_root_picks_slash_only():
    mounts = """\
proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0
/dev/nvme0n1p2 / btrfs rw,noatime,compress=zstd 0 0
/dev/nvme0n1p1 /boot vfat rw,relatime 0 0
tmpfs /tmp tmpfs rw,nosuid,nodev 0 0
"""
    assert parse_proc_mounts_root(mounts) == "/dev/nvme0n1p2"


def test_df_root_returns_human_size():
    df_out = """1B-blocks
512110190592
"""
    assert parse_df_root(df_out) in ("500 GB", "480 GB", "512 GB")


# ── OS ───────────────────────────────────────────────────────────────────

OSRELEASE_CACHYOS = """\
NAME="CachyOS Linux"
PRETTY_NAME="CachyOS"
ID=cachyos
ID_LIKE=arch
BUILD_ID=rolling
HOME_URL="https://cachyos.org/"
"""

OSRELEASE_UBUNTU = """\
NAME="Ubuntu"
VERSION="24.04.1 LTS (Noble Numbat)"
ID=ubuntu
PRETTY_NAME="Ubuntu 24.04.1 LTS"
VERSION_ID="24.04"
"""

OSRELEASE_FEDORA = """\
NAME="Fedora Linux"
VERSION="41 (Workstation Edition)"
ID=fedora
PRETTY_NAME="Fedora Linux 41 (Workstation Edition)"
"""

OSRELEASE_OPENSUSE = """\
NAME="openSUSE Tumbleweed"
PRETTY_NAME="openSUSE Tumbleweed"
ID="opensuse-tumbleweed"
VERSION_ID="20240515"
"""

OSRELEASE_DEBIAN_OLD = """\
PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"
NAME="Debian GNU/Linux"
VERSION_ID="12"
"""


def test_os_release_cachyos():
    assert parse_os_release(OSRELEASE_CACHYOS) == "CachyOS"


def test_os_release_ubuntu():
    assert parse_os_release(OSRELEASE_UBUNTU) == "Ubuntu 24.04.1 LTS"


def test_os_release_fedora():
    assert parse_os_release(OSRELEASE_FEDORA) \
        == "Fedora Linux 41 (Workstation Edition)"


def test_os_release_opensuse():
    assert parse_os_release(OSRELEASE_OPENSUSE) == "openSUSE Tumbleweed"


def test_os_release_debian():
    assert parse_os_release(OSRELEASE_DEBIAN_OLD) \
        == "Debian GNU/Linux 12 (bookworm)"


def test_lsb_release_etc_file():
    """`/etc/lsb-release` style with DISTRIB_DESCRIPTION."""
    s = 'DISTRIB_ID=Ubuntu\nDISTRIB_RELEASE=22.04\n' \
        'DISTRIB_DESCRIPTION="Ubuntu 22.04.3 LTS"\n'
    assert parse_lsb_release(s) == "Ubuntu 22.04.3 LTS"


def test_lsb_release_bare_line_from_command():
    """`lsb_release -ds` emits the description as a plain line."""
    assert parse_lsb_release("Ubuntu 22.04.3 LTS\n") == "Ubuntu 22.04.3 LTS"


def test_etc_issue_strips_escape_codes():
    """`/etc/issue` contains \\n, \\l, \\r terminal escapes that must
    be stripped before display."""
    issue = "Ubuntu 22.04.3 LTS \\n \\l\n\n"
    assert parse_etc_issue(issue) == "Ubuntu 22.04.3 LTS"


def test_uname_pass_through():
    assert parse_uname("Linux 6.18.25-1-cachyos-lts x86_64\n") \
        == "Linux 6.18.25-1-cachyos-lts x86_64"


# ── DMI: vendor / placeholder / model ────────────────────────────────────

@pytest.mark.parametrize("raw, expected", [
    # ── Taiwan / Korea / Japan / EU desktop majors ───────────────────
    ("ASUSTeK COMPUTER INC.\n", "ASUS"),
    ("ASUSTeK Computer Inc.\n", "ASUS"),
    ("ASUSTeK Computer INC.\n", "ASUS"),
    ("Micro-Star International Co., Ltd.\n", "MSI"),
    ("MICRO-STAR INTERNATIONAL CO., LTD\n", "MSI"),
    ("LENOVO\n", "Lenovo"),
    ("Hewlett-Packard\n", "HP"),
    ("HPE\n", "HPE"),
    ("Dell Inc.\n", "Dell"),
    ("Dell Computer Corporation\n", "Dell"),
    ("Alienware\n", "Alienware"),
    ("Gigabyte Technology Co., Ltd.\n", "Gigabyte"),
    ("Giga-byte Technology\n", "Gigabyte"),
    ("ASRock\n", "ASRock"),
    ("ASRockRack\n", "ASRock Rack"),
    ("Apple Inc.\n", "Apple"),
    ("Apple Computer, Inc.\n", "Apple"),
    ("Acer\n", "Acer"),
    ("Acer Inc.\n", "Acer"),
    ("Framework\n", "Framework"),
    ("Framework Computer Inc\n", "Framework"),
    ("System76\n", "System76"),
    ("System76, Inc.\n", "System76"),
    ("Star Labs\n", "Star Labs"),
    ("Razer\n", "Razer"),
    ("TUXEDO Computers GmbH\n", "TUXEDO"),
    ("Toshiba\n", "Toshiba"),
    ("TOSHIBA\n", "Toshiba"),
    ("Sony Corporation\n", "Sony"),
    ("Samsung Electronics Co., Ltd.\n", "Samsung"),
    ("LG Electronics\n", "LG"),
    ("Fujitsu\n", "Fujitsu"),
    ("FUJITSU CLIENT COMPUTING LIMITED\n", "Fujitsu"),
    ("Panasonic Corporation\n", "Panasonic"),
    ("NEC Corporation\n", "NEC"),
    ("Medion\n", "Medion"),
    ("Clevo\n", "Clevo"),
    ("Eluktronics\n", "Eluktronics"),
    ("Origin PC\n", "Origin PC"),
    ("Sager\n", "Sager"),

    # ── Chinese OEMs (laptops, mini-PCs, tablets, SBCs) ──────────────
    ("HUAWEI\n", "Huawei"),
    ("Huawei\n", "Huawei"),
    ("HONOR\n", "Honor"),
    ("XIAOMI\n", "Xiaomi"),
    ("Timi\n", "Xiaomi"),
    ("TIMI\n", "Xiaomi"),
    ("TONGFANG\n", "Tongfang"),
    ("TongFang\n", "Tongfang"),
    ("Mechrevo\n", "Mechrevo"),
    ("MECHREVO\n", "Mechrevo"),
    ("Hasee\n", "Hasee"),
    ("Hasee Computer\n", "Hasee"),
    ("Jumper\n", "Jumper"),
    ("Teclast\n", "Teclast"),
    ("ALLDOCUBE\n", "ALLDOCUBE"),
    ("Cube\n", "ALLDOCUBE"),
    ("Onda\n", "Onda"),
    ("Chuwi\n", "Chuwi"),
    ("CHUWI Innovation And Technology(ShenZhen)co.,Ltd\n", "Chuwi"),
    ("BMAX\n", "BMAX"),
    ("Beelink\n", "Beelink"),
    ("AZW\n", "Beelink"),
    ("Minisforum\n", "Minisforum"),
    ("MINIX\n", "MINIX"),
    ("Topton\n", "Topton"),
    ("GMK\n", "GMK"),
    ("GMKtec\n", "GMK"),
    ("Maibenben\n", "Maibenben"),
    ("KUU\n", "KUU"),
    ("Vorke\n", "Vorke"),
    ("ZOTAC\n", "ZOTAC"),
    ("ZOTAC International (MCO) Ltd.\n", "ZOTAC"),
    ("INSPUR\n", "Inspur"),
    ("Loongson\n", "Loongson"),
    ("Phytium\n", "Phytium"),
    ("AAEON\n", "AAEON"),
    ("Colorful\n", "Colorful"),
    ("MAXSUN\n", "Maxsun"),
    ("Sapphire\n", "Sapphire"),
    ("BIOSTAR\n", "Biostar"),
    ("BIOSTAR Group\n", "Biostar"),
    ("ECS\n", "ECS"),
    ("Elitegroup Computer Systems\n", "ECS"),
    ("Foxconn\n", "Foxconn"),
    ("Hon Hai Precision Ind. Co., Ltd.\n", "Foxconn"),
    ("Pegatron\n", "Pegatron"),
    ("PEGATRON CORPORATION\n", "Pegatron"),
    ("Compal\n", "Compal"),
    ("Quanta\n", "Quanta"),
    ("Inventec\n", "Inventec"),
    ("Mitac\n", "Mitac"),
    ("MiTAC\n", "Mitac"),
    ("Wistron\n", "Wistron"),

    # ── servers / workstations ───────────────────────────────────────
    ("Supermicro\n", "Supermicro"),
    ("Super Micro Computer, Inc.\n", "Supermicro"),
    ("Tyan\n", "Tyan"),
    ("TYAN Computer Corporation\n", "Tyan"),
    ("IBM Corporation\n", "IBM"),
    ("Cisco Systems Inc\n", "Cisco"),
    ("Intel Corporation\n", "Intel"),
    ("Advanced Micro Devices, Inc.\n", "AMD"),
    ("Oracle Corporation\n", "Oracle"),
    ("ARM Limited\n", "ARM"),
    ("Qualcomm\n", "Qualcomm"),

    # ── SBCs / ARM boards ────────────────────────────────────────────
    ("Raspberry Pi Foundation\n", "Raspberry Pi"),
    ("Raspberry Pi Ltd\n", "Raspberry Pi"),
    ("Pine64\n", "Pine64"),
    ("HARDKERNEL Co., Ltd.\n", "Hardkernel"),
    ("ODROID\n", "Hardkernel"),
    ("Rockchip\n", "Rockchip"),
    ("Allwinner\n", "Allwinner"),
    ("Amlogic\n", "Amlogic"),
    ("Radxa\n", "Radxa"),
    ("FriendlyARM\n", "FriendlyARM"),
    ("FriendlyElec\n", "FriendlyElec"),
    ("Khadas\n", "Khadas"),
    ("Banana Pi\n", "Banana Pi"),
    ("Sipeed\n", "Sipeed"),

    # ── VM / cloud platforms (sys_vendor surface) ────────────────────
    ("innotek GmbH\n", "VirtualBox"),
    ("QEMU\n", "QEMU"),
    ("VMware, Inc.\n", "VMware"),
    ("Microsoft Corporation\n", "Microsoft"),
    ("Parallels Software International Inc.\n", "Parallels"),
    ("Xen\n", "Xen"),
    ("Bochs\n", "Bochs"),
    ("Red Hat\n", "Red Hat"),
    ("Red Hat KVM\n", "Red Hat KVM"),
    ("Amazon EC2\n", "Amazon EC2"),
    ("Amazon Web Services\n", "AWS"),
    ("Google\n", "Google"),
    ("Google Compute Engine\n", "Google Cloud"),
    ("DigitalOcean\n", "DigitalOcean"),
    ("Hetzner\n", "Hetzner"),
    ("OpenStack Foundation\n", "OpenStack"),
    ("Nutanix\n", "Nutanix"),
    ("Proxmox\n", "Proxmox"),
])
def test_vendor_known_shorts(raw, expected):
    assert parse_vendor(raw) == expected


def test_vendor_unknown_passes_through_verbatim():
    """An OEM not in the lookup table is rendered as-is — no smart
    trimming that might mangle a real name. The DMI placeholder filter
    is the only thing that intercepts."""
    assert parse_vendor("Acme Robotics Inc.\n") == "Acme Robotics Inc."
    assert parse_vendor("Tiny Computer Corp.\n") == "Tiny Computer Corp."
    assert parse_vendor("Some Vendor GmbH\n") == "Some Vendor GmbH"
    # An obscure Chinese mini-PC brand we haven't catalogued yet:
    assert parse_vendor("Shenzhen Mumumu Tech Co., Ltd.\n") \
        == "Shenzhen Mumumu Tech Co., Ltd."


def test_vendor_unknown_still_filtered_for_placeholders():
    """Even for unknown vendors, the OEM-placeholder filter applies."""
    assert parse_vendor("Default string\n") == ""
    assert parse_vendor("To Be Filled By O.E.M.\n") == ""


@pytest.mark.parametrize("placeholder", [
    "",
    "\n",
    "None\n",
    "Default string\n",
    "To Be Filled By O.E.M.\n",
    "System Product Name\n",
    "System Version\n",
    "N/A\n",
    "Not Specified\n",
])
def test_dmi_placeholders_treated_as_empty(placeholder):
    assert parse_dmi_string(placeholder) == ""


def test_dmi_real_value_preserved():
    assert parse_dmi_string("PRIME X870-P WIFI\n") == "PRIME X870-P WIFI"


def test_bios_year_first_four_digits():
    assert parse_bios_year("03/14/2025\n") == "2025"
    assert parse_bios_year("2024-09-01\n") == "2024"
    assert parse_bios_year("garbage\n") == ""


# ── collapsing primitives ────────────────────────────────────────────────

def test_first_non_empty_returns_first_truthy():
    assert first_non_empty("", "  ", "real", "ignored") == "real"
    assert first_non_empty(None, "", "x") == "x"
    assert first_non_empty("", None, "") == ""


# ── full collect() smoke test ────────────────────────────────────────────

def test_collect_returns_all_keys():
    """``collect()`` must always return the full schema, even on a
    machine with missing tools — every QML-side field reads a key by
    name, so a missing key would render as ``undefined``."""
    info = collect()
    expected_keys = {
        "vendor", "model", "year", "chip", "cores", "memory",
        "graphics", "disk", "network", "serial", "os",
    }
    assert set(info.keys()) == expected_keys


def test_collect_returns_string_values():
    """No nulls in the JSON payload — QML expects strings throughout."""
    info = collect()
    for key, value in info.items():
        assert isinstance(value, str), f"{key} is {type(value).__name__}, expected str"


def test_collect_chip_is_non_empty_on_linux():
    """The whole point of the multi-source design is that *something*
    answers on a real machine. On the test host, at least one of
    lscpu / cpuinfo / dmidecode must produce a CPU model."""
    info = collect()
    assert info["chip"] not in ("", "Unknown"), \
        "no CPU source resolved on test host — fallbacks are broken"


def test_collect_memory_is_non_empty_on_linux():
    info = collect()
    assert info["memory"] not in ("", "Unknown"), \
        "no memory source resolved on test host"


def test_collect_os_is_non_empty_on_linux():
    info = collect()
    assert info["os"] not in ("", "Unknown"), \
        "no OS source resolved on test host"


# ── helper-binary integration ────────────────────────────────────────────

def test_helper_emits_valid_json_to_stdout():
    """``mac-tahoe-about-info`` (the executable shim QML calls) must
    exit 0 and produce parseable JSON with the full schema."""
    helper = SCRIPTS / "about_info.py"
    result = subprocess.run(
        [sys.executable, str(helper)],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, f"helper exited {result.returncode}: {result.stderr}"
    info = json.loads(result.stdout)
    expected_keys = {
        "vendor", "model", "year", "chip", "cores", "memory",
        "graphics", "disk", "network", "serial", "os", "theme_version",
    }
    assert set(info.keys()) == expected_keys


def test_helper_pretty_flag_indents():
    helper = SCRIPTS / "about_info.py"
    result = subprocess.run(
        [sys.executable, str(helper), "--pretty"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0
    # Indented JSON has newlines + spaces; compact JSON is single-line.
    assert "\n  " in result.stdout


# ── adversarial: data-fetch failure modes ────────────────────────────────

# ── network / MAC ────────────────────────────────────────────────────────

def test_default_iface_from_ip_route():
    """``ip route get`` prints the path to a destination on one line —
    we pull the iface from the ``dev <name>`` token."""
    s = "1.1.1.1 via 192.168.1.1 dev wlp3s0 src 192.168.1.42 uid 1000 \n    cache\n"
    assert parse_default_iface(s) == "wlp3s0"


def test_default_iface_handles_ethernet_name():
    s = "1.1.1.1 dev eno1 src 10.0.0.5 uid 1000\n"
    assert parse_default_iface(s) == "eno1"


def test_default_iface_handles_vpn():
    """A tun/wg interface is the real egress when a VPN is up. We
    don't second-guess the routing decision — whatever the kernel
    picks is what we report."""
    s = "1.1.1.1 dev wg0 src 10.8.0.2 uid 1000\n"
    assert parse_default_iface(s) == "wg0"


def test_default_iface_empty_when_no_route():
    """Air-gapped box or boot before networking — empty input → empty."""
    assert parse_default_iface("") == ""
    assert parse_default_iface(
        "RTNETLINK answers: Network is unreachable\n") == ""


def test_proc_route_default_picks_destination_zero():
    """``/proc/net/route`` columns are tab-separated; the default route
    has ``Destination == 00000000``."""
    s = (
        "Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\n"
        "wlp3s0\t00000000\t0101A8C0\t0003\t0\t0\t600\t00000000\n"
        "wlp3s0\t0001A8C0\t00000000\t0001\t0\t0\t600\t00FFFFFF\n"
    )
    assert parse_proc_route_default(s) == "wlp3s0"


def test_proc_route_default_no_default():
    """A LAN-only box may have no default route — return empty so we
    fall through to other sources."""
    s = (
        "Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\n"
        "wlp3s0\t0001A8C0\t00000000\t0001\t0\t0\t600\t00FFFFFF\n"
    )
    assert parse_proc_route_default(s) == ""


def test_mac_valid_address():
    assert parse_mac("a8:7e:ea:12:34:56\n") == "a8:7e:ea:12:34:56"


def test_mac_uppercase_normalized():
    """sysfs sometimes returns uppercase hex. Normalize so display is
    stable across machines."""
    assert parse_mac("A8:7E:EA:12:34:56\n") == "a8:7e:ea:12:34:56"


def test_mac_zero_mac_dropped():
    """Some bridge / dummy interfaces expose 00:00:00:00:00:00 — that
    isn't a real address and shouldn't appear in the UI."""
    assert parse_mac("00:00:00:00:00:00\n") == ""


def test_mac_invalid_format_dropped():
    """Anything that doesn't match the canonical 17-char colon form is
    dropped — we don't try to repair garbage."""
    assert parse_mac("not-a-mac\n") == ""
    assert parse_mac("a8-7e-ea-12-34-56\n") == ""  # dashed (Windows) form
    assert parse_mac("a87e.ea12.3456\n") == ""    # Cisco form
    assert parse_mac("") == ""


def test_format_network_with_iface():
    assert format_network("wlp3s0", "a8:7e:ea:12:34:56") \
        == "a8:7e:ea:12:34:56 (wlp3s0)"


def test_format_network_without_iface():
    assert format_network("", "a8:7e:ea:12:34:56") == "a8:7e:ea:12:34:56"


def test_format_network_no_mac_returns_empty():
    """If we couldn't find a MAC, don't render parens with empty
    contents — return empty so the caller can fall to ``"Unknown"``."""
    assert format_network("eth0", "") == ""
    assert format_network("", "") == ""


def test_collect_includes_network_key():
    """The full schema now includes ``network`` — every QML row
    reads its key by name, so a missing key would render as
    ``undefined``."""
    info = collect()
    assert "network" in info
    assert isinstance(info["network"], str)


def test_collect_runs_fast_enough_for_a_modal():
    """AboutWindow blocks on this helper. Parallel collection should
    keep total wall time under ~3 s even with one or two timed-out
    subprocesses; sequential execution would push past 8 s."""
    import time
    t0 = time.monotonic()
    collect()
    elapsed = time.monotonic() - t0
    assert elapsed < 5.0, f"collect() took {elapsed:.1f}s; parallelism broken"


def test_collect_idempotent():
    """Two consecutive calls must return identical schemas. Catches
    accidental statefulness in the live-source table or parsers."""
    a, b = collect(), collect()
    assert set(a.keys()) == set(b.keys())
    # Values may differ if a flaky subprocess timed out on one run —
    # what matters is that the schema (key set) is stable.


def test_helper_returns_full_schema_even_with_no_tools(tmp_path, monkeypatch):
    """Simulate a stripped-down system: empty PATH so every subprocess
    (lscpu, lspci, lsblk, dmidecode, …) fails with FileNotFoundError.
    /proc and /sys are still readable, so something will come back, but
    every field must be a string — never None, never missing."""
    helper = SCRIPTS / "about_info.py"
    env = dict(os.environ)
    env["PATH"] = ""  # nothing to find
    result = subprocess.run(
        [sys.executable, str(helper)],
        capture_output=True, text=True, timeout=15, env=env,
    )
    assert result.returncode == 0, result.stderr
    info = json.loads(result.stdout)
    expected_keys = {
        "vendor", "model", "year", "chip", "cores", "memory",
        "graphics", "disk", "network", "serial", "os", "theme_version",
    }
    assert set(info.keys()) == expected_keys
    for key, value in info.items():
        assert isinstance(value, str)


def test_parsers_never_raise_on_garbage():
    """Every public parser receives random / malformed / binary-ish
    input and must return ``""`` rather than raise."""
    garbage_inputs = [
        "",
        "\n",
        "\x00\x01\x02binary garbage",
        "a" * 100000,
        "𝕌𝕟𝕚𝕔𝕠𝕕𝕖 madness 🌈🦄",
        "<html><body>not even close</body></html>",
    ]
    parsers_single = [
        parse_dmi_string, parse_vendor, parse_bios_year,
        parse_meminfo, parse_free_bytes, parse_dmidecode_memory,
        parse_dmidecode_cpu, parse_nproc,
        parse_lspci_gpu, parse_drm_fallback, parse_glxinfo,
        parse_findmnt_root, parse_proc_mounts_root, parse_df_root,
        parse_os_release, parse_lsb_release, parse_uname, parse_etc_issue,
    ]
    for fn in parsers_single:
        for raw in garbage_inputs:
            try:
                out = fn(raw)
            except Exception as e:
                raise AssertionError(f"{fn.__name__} raised on garbage: {e!r}")
            assert isinstance(out, str)


def test_parsers_dict_return_never_raise_on_garbage():
    """Same contract for the parsers that return ``{model, cores}``."""
    garbage_inputs = ["", "\n", "no fields here\n",
                      "𝕦𝕟𝕚𝕔𝕠𝕕𝕖", "\x00binary"]
    for fn in (parse_lscpu, parse_cpuinfo):
        for raw in garbage_inputs:
            out = fn(raw)
            assert isinstance(out, dict)
            assert "model" in out and "cores" in out


def test_lsblk_with_unicode_model_in_path():
    """Some no-name OEM SSDs put unicode (™, ™, ™) or extended ASCII in
    the MODEL field. We must not choke."""
    out = parse_lsblk(
        "nvme0n1     500107862016 disk 国产™ Brand SSD-Pro 500G\n",
        "/dev/nvme0n1p1",
    )
    assert "国产" in out or "Brand SSD-Pro" in out


def test_os_release_with_unicode_pretty_name():
    """A localized PRETTY_NAME (Korean / Japanese / Chinese) must round-
    trip through the regex without mangling."""
    s = 'PRETTY_NAME="우분투 24.04 LTS"\n'
    assert parse_os_release(s) == "우분투 24.04 LTS"


def test_lspci_no_id_class_falls_back_to_text():
    """Some lspci builds don't include the ``"0300"`` numeric class. We
    must still match on the english text class."""
    line = (
        '00:02.0 "VGA compatible controller" "Intel Corporation" '
        '"TigerLake-LP GT2 [Iris Xe Graphics]" -r0c -p00 "" ""\n'
    )
    assert "Intel" in parse_lspci_gpu(line)
    assert "Iris Xe" in parse_lspci_gpu(line)


def test_meminfo_zero_kb():
    """A container with cgroups v2 strict limits sometimes reports 0."""
    assert parse_meminfo("MemTotal:       0 kB\n") == ""


def test_lscpu_with_only_logical_cores():
    """Some VPS / cgroup setups only expose ``CPU(s)`` — no Socket /
    Core(s) per socket. Cores should still resolve to the logical
    count alone, not be empty."""
    s = "Architecture: x86_64\nCPU(s):                   4\n"
    parsed = parse_lscpu(s)
    assert parsed["cores"] == "4"


def test_lscpu_logical_equals_physical_no_brackets():
    """When SMT is off, logical == physical. Don't render the
    redundant ``"8 (8 physical)"``."""
    s = (
        "CPU(s):                   8\n"
        "Core(s) per socket:       8\n"
        "Socket(s):                1\n"
        "Model name:               Intel Core i7\n"
    )
    parsed = parse_lscpu(s)
    assert parsed["cores"] == "8"


def test_lsblk_busybox_minimal_output():
    """Busybox's lsblk omits MODEL by default. Size + name must still
    produce a label."""
    out = parse_lsblk("sda     34359738368 disk\n", "/dev/sda1")
    assert out  # non-empty
    assert "GB" in out or "TB" in out


# ── theme version plumbing (About window footer) ─────────────────────────

def test_theme_version_matches_repo_version():
    import about_info
    assert about_info.theme_version() == (REPO / "VERSION").read_text().strip()


def test_emitted_json_carries_theme_version():
    res = subprocess.run(
        [sys.executable, str(SCRIPTS / "about_info.py"), "--mock"],
        capture_output=True, text=True,
    )
    data = json.loads(res.stdout)
    assert data["theme_version"] == (REPO / "VERSION").read_text().strip()


def test_installed_copy_reports_baked_version(tmp_path):
    """Outside the repo (no VERSION two parents up) the helper falls
    back to the version _install_about_info() baked in."""
    source = (SCRIPTS / "about_info.py").read_text(encoding="utf-8")
    helper = tmp_path / "mac-tahoe-about-info"
    helper.write_text(source.replace("@THEME_VERSION@", "9.9.9"),
                      encoding="utf-8")
    res = subprocess.run(
        [sys.executable, str(helper), "--mock"],
        capture_output=True, text=True,
    )
    assert json.loads(res.stdout)["theme_version"] == "9.9.9"


def test_unbaked_copy_outside_repo_reports_empty(tmp_path):
    source = (SCRIPTS / "about_info.py").read_text(encoding="utf-8")
    helper = tmp_path / "mac-tahoe-about-info"
    helper.write_text(source, encoding="utf-8")
    res = subprocess.run(
        [sys.executable, str(helper), "--mock"],
        capture_output=True, text=True,
    )
    assert json.loads(res.stdout)["theme_version"] == ""
