#!/usr/bin/env python3
"""About This Computer — system information collector.

Reads every public source of hardware/OS data the running user can see
(DMI sysfs, ``/proc``, ``lscpu``, ``lspci``, ``lsblk``, ``glxinfo``,
``free``, ``dmidecode``, …), picks the first non-empty answer from each
source stack per field, and emits a JSON document on stdout that the
AboutWindow QML consumes.

Everything except serial-number is expected to resolve to a real value
on a standard desktop Linux install — the install ships the helper into
``~/.local/bin`` and the QML calls it via Plasma5Support's executable
data source.

Public functions (``parse_*``) are pure: they take a captured stdout
string and return a parsed value or ``""``. ``collect()`` wires them to
live commands. The test suite exercises ``parse_*`` directly with
captured fixtures from CachyOS, Arch, Ubuntu, Fedora, openSUSE,
locale-translated lscpu, and minimal VMs.

Usage:
    mac-tahoe-about-info               # JSON to stdout
    mac-tahoe-about-info --pretty      # indented
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ── helpers ──────────────────────────────────────────────────────────────

_DMI_PLACEHOLDERS = frozenset(
    s.lower() for s in (
        "", "none",
        "System Product Name", "System manufacturer", "System Version",
        "Default string", "To Be Filled By O.E.M.", "To Be Filled By O.E.M",
        "Not Specified", "Not Available", "Unknown", "OEM", "N/A", "NA",
        "Chassis Manufacture", "Chassis Version",
    )
)


def _is_placeholder(s: str) -> bool:
    return (s or "").strip().lower() in _DMI_PLACEHOLDERS


def first_non_empty(*values: str) -> str:
    """Return the first stripped, non-empty value. Used to collapse a
    stack of (source → parsed) candidates into the rendered string."""
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


# ── DMI strings ──────────────────────────────────────────────────────────

def parse_dmi_string(stdout: str) -> str:
    """A DMI sysfs read with the OEM-placeholder filter applied."""
    s = (stdout or "").strip()
    return "" if _is_placeholder(s) else s


# Vendor shortening table: DMI sys_vendor / board_vendor strings the way
# OEMs report them on the left, the friendly form on the right. Keep
# strings exactly as they appear in /sys/devices/virtual/dmi/id/* — DMI
# whitespace and casing aren't normalized.
_VENDOR_SHORTS = {
    # ── desktop / mobo majors (US/EU/Taiwan/Korea/Japan) ─────────────
    "ASUSTeK COMPUTER INC.": "ASUS",
    "ASUSTeK Computer Inc.": "ASUS",
    "ASUSTeK Computer INC.": "ASUS",
    "ASUS": "ASUS",
    "Micro-Star International Co., Ltd.": "MSI",
    "Micro-Star International Co., Ltd": "MSI",
    "MICRO-STAR INTERNATIONAL CO., LTD": "MSI",
    "MSI": "MSI",
    "LENOVO": "Lenovo",
    "Lenovo": "Lenovo",
    "Hewlett-Packard": "HP",
    "HP": "HP",
    "HPE": "HPE",
    "Dell Inc.": "Dell",
    "Dell Computer Corporation": "Dell",
    "Alienware": "Alienware",
    "Gigabyte Technology Co., Ltd.": "Gigabyte",
    "GIGABYTE": "Gigabyte",
    "Giga-byte Technology": "Gigabyte",
    "ASRock": "ASRock",
    "ASRockRack": "ASRock Rack",
    "Apple Inc.": "Apple",
    "Apple Computer, Inc.": "Apple",
    "Acer": "Acer",
    "Acer Inc.": "Acer",
    "Acer Aspire": "Acer",
    "Framework": "Framework",
    "Framework Computer Inc": "Framework",
    "TUXEDO": "TUXEDO",
    "TUXEDO Computers GmbH": "TUXEDO",
    "System76": "System76",
    "System76, Inc.": "System76",
    "Star Labs": "Star Labs",
    "Razer": "Razer",
    "Razer Inc.": "Razer",
    "Toshiba": "Toshiba",
    "TOSHIBA": "Toshiba",
    "Sony Corporation": "Sony",
    "Sony": "Sony",
    "Samsung Electronics Co., Ltd.": "Samsung",
    "SAMSUNG ELECTRONICS CO., LTD.": "Samsung",
    "LG Electronics": "LG",
    "LG ELECTRONICS": "LG",
    "Fujitsu": "Fujitsu",
    "FUJITSU": "Fujitsu",
    "FUJITSU CLIENT COMPUTING LIMITED": "Fujitsu",
    "Panasonic Corporation": "Panasonic",
    "NEC Corporation": "NEC",
    "NEC": "NEC",
    "Medion": "Medion",
    "MEDION": "Medion",
    "Clevo": "Clevo",
    "CLEVO": "Clevo",
    "Notebook": "Clevo",  # generic Clevo OEM string
    "Eluktronics": "Eluktronics",
    "Origin PC": "Origin PC",
    "ORIGIN PC": "Origin PC",
    "Sager": "Sager",

    # ── Chinese OEMs / SBCs / mini-PCs ───────────────────────────────
    "HUAWEI": "Huawei",
    "Huawei": "Huawei",
    "HONOR": "Honor",
    "XIAOMI": "Xiaomi",
    "Xiaomi": "Xiaomi",
    "Timi": "Xiaomi",  # Timi is Xiaomi's laptop OEM
    "TIMI": "Xiaomi",
    "RedmiBook": "Xiaomi",
    "TONGFANG": "Tongfang",
    "Tongfang": "Tongfang",
    "TongFang": "Tongfang",
    "GUANGZHOU YULONG": "Tongfang",
    "Mechrevo": "Mechrevo",
    "MECHREVO": "Mechrevo",
    "Hasee": "Hasee",
    "HASEE": "Hasee",
    "Hasee Computer": "Hasee",
    "Jumper": "Jumper",
    "JUMPER": "Jumper",
    "Teclast": "Teclast",
    "TECLAST": "Teclast",
    "ALLDOCUBE": "ALLDOCUBE",
    "Cube": "ALLDOCUBE",
    "Onda": "Onda",
    "ONDA": "Onda",
    "Chuwi": "Chuwi",
    "CHUWI": "Chuwi",
    "CHUWI Innovation And Technology(ShenZhen)co.,Ltd": "Chuwi",
    "BMAX": "BMAX",
    "Bmax": "BMAX",
    "Beelink": "Beelink",
    "BEELINK": "Beelink",
    "AZW": "Beelink",
    "Minisforum": "Minisforum",
    "MINISFORUM": "Minisforum",
    "MINIX": "MINIX",
    "Topton": "Topton",
    "TOPTON": "Topton",
    "GMK": "GMK",
    "GMKtec": "GMK",
    "Maibenben": "Maibenben",
    "MAIBENBEN": "Maibenben",
    "KUU": "KUU",
    "Vorke": "Vorke",
    "VORKE": "Vorke",
    "ZOTAC": "ZOTAC",
    "Zotac": "ZOTAC",
    "ZOTAC International (MCO) Ltd.": "ZOTAC",
    "INSPUR": "Inspur",
    "Inspur": "Inspur",
    "Loongson": "Loongson",
    "Phytium": "Phytium",
    "PHYTIUM": "Phytium",
    "TENCENT": "Tencent",
    "AAEON": "AAEON",
    "Yeston": "Yeston",
    "Colorful": "Colorful",
    "COLORFUL": "Colorful",
    "MAXSUN": "Maxsun",
    "Maxsun": "Maxsun",
    "Sapphire": "Sapphire",
    "BIOSTAR": "Biostar",
    "Biostar": "Biostar",
    "BIOSTAR Group": "Biostar",
    "ECS": "ECS",
    "Elitegroup Computer Systems": "ECS",
    "ECS LIVA": "ECS",
    "Foxconn": "Foxconn",
    "FOXCONN": "Foxconn",
    "Hon Hai Precision Ind. Co., Ltd.": "Foxconn",
    "Pegatron": "Pegatron",
    "PEGATRON CORPORATION": "Pegatron",
    "Compal": "Compal",
    "COMPAL": "Compal",
    "Quanta": "Quanta",
    "QUANTA": "Quanta",
    "Inventec": "Inventec",
    "INVENTEC": "Inventec",
    "Mitac": "Mitac",
    "MiTAC": "Mitac",
    "Wistron": "Wistron",

    # ── server / workstation OEMs ────────────────────────────────────
    "Supermicro": "Supermicro",
    "Super Micro Computer, Inc.": "Supermicro",
    "Tyan": "Tyan",
    "TYAN Computer Corporation": "Tyan",
    "IBM": "IBM",
    "IBM Corporation": "IBM",
    "Cisco Systems Inc": "Cisco",
    "Intel Corporation": "Intel",
    "Intel": "Intel",
    "AMD": "AMD",
    "Advanced Micro Devices, Inc.": "AMD",
    "Oracle Corporation": "Oracle",
    "ARM Limited": "ARM",
    "Qualcomm": "Qualcomm",
    "QUALCOMM": "Qualcomm",

    # ── SBCs ─────────────────────────────────────────────────────────
    "Raspberry Pi Foundation": "Raspberry Pi",
    "Raspberry Pi Ltd": "Raspberry Pi",
    "Pine64": "Pine64",
    "PINE64": "Pine64",
    "Hardkernel": "Hardkernel",
    "HARDKERNEL Co., Ltd.": "Hardkernel",
    "Rockchip": "Rockchip",
    "Allwinner": "Allwinner",
    "Amlogic": "Amlogic",
    "Radxa": "Radxa",
    "RADXA": "Radxa",
    "FriendlyARM": "FriendlyARM",
    "FriendlyElec": "FriendlyElec",
    "ODROID": "Hardkernel",
    "Khadas": "Khadas",
    "KHADAS": "Khadas",
    "Banana Pi": "Banana Pi",
    "Sipeed": "Sipeed",

    # ── VMs / hypervisors / cloud (sys_vendor surface) ───────────────
    "QEMU": "QEMU",
    "innotek GmbH": "VirtualBox",
    "VMware, Inc.": "VMware",
    "VMware": "VMware",
    "Microsoft Corporation": "Microsoft",
    "Parallels Software International Inc.": "Parallels",
    "Xen": "Xen",
    "Bochs": "Bochs",
    "Bochs/Plex86": "Bochs",
    "Red Hat": "Red Hat",
    "Red Hat KVM": "Red Hat KVM",
    "Amazon EC2": "Amazon EC2",
    "Amazon Web Services": "AWS",
    "Google": "Google",
    "Google Compute Engine": "Google Cloud",
    "DigitalOcean": "DigitalOcean",
    "Hetzner": "Hetzner",
    "OpenStack Foundation": "OpenStack",
    "Nutanix": "Nutanix",
    "Proxmox": "Proxmox",
}


def parse_vendor(stdout: str) -> str:
    """Friendly vendor name from DMI sys_vendor / board_vendor.

    If the OEM string is in the lookup table, swap it for the short form
    (so "ASUSTeK COMPUTER INC." → "ASUS"). Otherwise return the raw DMI
    string verbatim — every attempt to be "smart" about trimming
    suffixes has at some point mangled a real vendor name. The goal is
    to work on *every* system, not to look pretty on the known ones.

    The DMI-placeholder filter still applies — "Default string" / "To
    Be Filled By O.E.M." come back empty so the caller can fall through
    to the next source.
    """
    raw = parse_dmi_string(stdout)
    if not raw:
        return ""
    return _VENDOR_SHORTS.get(raw, raw)


def parse_bios_year(stdout: str) -> str:
    m = re.search(r"(\d{4})", (stdout or "").strip())
    return m.group(1) if m else ""


# ── CPU ──────────────────────────────────────────────────────────────────

def _clean_cpu_model(raw: str) -> str:
    if not raw:
        return ""
    s = raw.strip()
    s = re.sub(r"\(R\)|\(TM\)", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+CPU\s*", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+Processor\s*$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*@\s*[\d.]+\s*[GM]Hz", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+with\s+.*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+\d+-Core.*", "", s, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", s).strip()


def parse_lscpu(stdout: str) -> dict[str, str]:
    """Parse ``LC_ALL=C lscpu`` output. Returns ``{"model", "cores"}``.

    Caller is responsible for setting ``LC_ALL=C`` — without it, lscpu
    translates the field labels ("Modèle de processeur :", etc.) and
    the regex returns nothing. That mistake was the original bug behind
    the v0.13.11 issue report.
    """
    out = {"model": "", "cores": ""}
    if not stdout:
        return out

    # util-linux 2.40+ ships a hierarchical "lscpu" that indents nested
    # fields ("  Model name:"). Older releases output flush-left. Accept
    # both so the parser matches no matter which release is installed.
    m = re.search(r"^[ \t]*Model name:\s+(.+)$", stdout, re.MULTILINE)
    if m:
        out["model"] = _clean_cpu_model(m.group(1))

    m_logical = re.search(r"^[ \t]*CPU\(s\):\s+(\d+)", stdout, re.MULTILINE)
    m_per_socket = re.search(r"^[ \t]*Core\(s\) per socket:\s+(\d+)", stdout, re.MULTILINE)
    m_sockets = re.search(r"^[ \t]*Socket\(s\):\s+(\d+)", stdout, re.MULTILINE)
    if m_logical:
        logical = int(m_logical.group(1))
        physical = ""
        if m_per_socket and m_sockets:
            physical = str(int(m_per_socket.group(1)) * int(m_sockets.group(1)))
        out["cores"] = (f"{logical} ({physical} physical)"
                        if physical and physical != str(logical)
                        else str(logical))
    return out


def parse_cpuinfo(stdout: str) -> dict[str, str]:
    """Parse ``/proc/cpuinfo``. Portable fallback when lscpu is missing
    or its locale couldn't be forced."""
    out = {"model": "", "cores": ""}
    if not stdout:
        return out

    m = re.search(r"^model name\s*:\s*(.+)$", stdout, re.MULTILINE)
    if not m:
        # ARM big.LITTLE / RISC-V: no model name field. Try ``Model``
        # before ``Hardware`` — the former is usually the friendly
        # board name ("Raspberry Pi 5 Model B Rev 1.0") while the
        # latter is the SoC family ("BCM2835") which is less useful.
        m = (re.search(r"^Model\s*:\s*(.+)$", stdout, re.MULTILINE)
             or re.search(r"^Hardware\s*:\s*(.+)$", stdout, re.MULTILINE))
    if m:
        out["model"] = _clean_cpu_model(m.group(1))

    logical = len(re.findall(r"^processor\s*:", stdout, re.MULTILINE))
    physical_ids: set[str] = set()
    cores_per_socket = 0
    for line in stdout.splitlines():
        p = re.match(r"^physical id\s*:\s*(\d+)", line)
        if p:
            physical_ids.add(p.group(1))
        c = re.match(r"^cpu cores\s*:\s*(\d+)", line)
        if c and not cores_per_socket:
            cores_per_socket = int(c.group(1))

    if logical:
        physical = ""
        if physical_ids and cores_per_socket:
            physical = str(len(physical_ids) * cores_per_socket)
        out["cores"] = (f"{logical} ({physical} physical)"
                        if physical and physical != str(logical)
                        else str(logical))
    return out


def parse_dmidecode_cpu(stdout: str) -> str:
    """``dmidecode -s processor-version`` → bare model string."""
    if not stdout:
        return ""
    lines = stdout.strip().splitlines()
    if not lines:
        return ""
    return _clean_cpu_model(lines[0])


def parse_nproc(stdout: str) -> str:
    """``nproc --all`` → bare integer."""
    m = re.match(r"^(\d+)", (stdout or "").strip())
    return m.group(1) if m else ""


def merge_cpu(*candidates: dict[str, str]) -> dict[str, str]:
    """First non-empty model wins; same for cores. Each candidate is
    a ``{"model", "cores"}`` dict from one of the parse_* sources."""
    model = first_non_empty(*(c.get("model", "") for c in candidates))
    cores = first_non_empty(*(c.get("cores", "") for c in candidates))
    return {"model": model, "cores": cores}


# ── Memory ───────────────────────────────────────────────────────────────

_MEM_SNAP_SIZES = (1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192,
                   256, 384, 512, 768, 1024)


def _snap_gb(gb: float) -> str:
    """OEM-reserved holes drop usable RAM by 100–500 MiB on most boards;
    snap to the nearest commonly-installed size so "15.7 GiB" reads as
    "16 GB". Outside the table we just round."""
    if gb <= 0:
        return ""
    best = min(_MEM_SNAP_SIZES, key=lambda s: abs(s - gb))
    if abs(best - gb) <= max(2, gb * 0.06):
        return f"{best} GB"
    return f"{round(gb)} GB"


def parse_meminfo(stdout: str) -> str:
    """``/proc/meminfo`` MemTotal in kB → snapped human size."""
    if not stdout:
        return ""
    m = re.search(r"MemTotal:\s+(\d+)", stdout)
    if not m:
        return ""
    kb = int(m.group(1))
    return _snap_gb(kb / 1048576)


def parse_free_bytes(stdout: str) -> str:
    """``free -b`` "Mem: <total> ..." → snapped human size."""
    if not stdout:
        return ""
    m = re.search(r"^Mem:\s+(\d+)", stdout, re.MULTILINE)
    if not m:
        return ""
    return _snap_gb(int(m.group(1)) / 1073741824)


def parse_dmidecode_memory(stdout: str) -> str:
    """``dmidecode -t memory`` — sum populated DIMM "Size: N GB" lines.
    Skip "No Module Installed"."""
    if not stdout:
        return ""
    total_gb = 0.0
    for line in stdout.splitlines():
        if re.search(r"No Module Installed", line, re.IGNORECASE):
            continue
        m = re.match(r"\s*Size:\s+(\d+(?:\.\d+)?)\s*(MB|GB|TB)\b",
                     line, re.IGNORECASE)
        if not m:
            continue
        v = float(m.group(1))
        unit = m.group(2).upper()
        if unit == "MB":
            v /= 1024
        elif unit == "TB":
            v *= 1024
        total_gb += v
    return _snap_gb(total_gb) if total_gb > 0 else ""


# ── GPU ──────────────────────────────────────────────────────────────────

def _short_gpu_vendor(v: str) -> str:
    if not v:
        return ""
    s = v.strip()
    # ``lspci -nn`` appends PCI vendor IDs in ``[...]`` brackets; the
    # ``-mm`` form additionally keeps the ATI alias ("[AMD/ATI]"). Strip
    # every trailing bracket pair before the friendly-name swap so the
    # AMD/NVIDIA shorts don't leave residue like "AMD [AMD/ATI] [1002]".
    s = re.sub(r"\s*\[[^\]]*\]\s*", " ", s).strip()
    s = re.sub(r"\s*Corporation\s*$", "", s, flags=re.IGNORECASE)
    s = s.replace("Advanced Micro Devices, Inc.", "AMD")
    s = s.replace("Advanced Micro Devices, Inc", "AMD")
    s = re.sub(r"NVIDIA Corporation", "NVIDIA", s, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", s).strip()


def _short_gpu_device(d: str) -> str:
    if not d:
        return ""
    s = d.strip()
    # lspci device strings are typically "<codename> [<marketing>] [<id>]".
    # Strip the trailing PCI id bracket first so we don't pick it instead
    # of the marketing name, then take the first remaining bracket.
    s = re.sub(r"\s*\[[0-9a-fA-F]{4}\]\s*$", "", s)
    br = re.search(r"\[([^\]]+)\]", s)
    if br:
        s = br.group(1)
    s = re.sub(r"\s*\[.*?\]\s*", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_lspci_gpu(stdout: str) -> str:
    """``LC_ALL=C lspci -mm -nn`` — pick VGA / 3D / Display controllers
    and produce "Vendor Device". Multiple GPUs join with " + ", with
    adjacent duplicates removed."""
    if not stdout:
        return ""
    gpus: list[str] = []
    for line in stdout.splitlines():
        is_gpu = (
            re.search(r'"0(?:300|302|380)"', line)
            or re.search(
                r"VGA compatible controller|3D controller|Display controller",
                line, re.IGNORECASE,
            )
        )
        if not is_gpu:
            continue
        fields = re.findall(r'"([^"]*)"', line)
        if len(fields) < 3:
            continue
        vendor = _short_gpu_vendor(fields[1])
        device = _short_gpu_device(fields[2])
        if not vendor and not device:
            continue
        name = re.sub(r"\s+", " ", f"{vendor} {device}").strip()
        if name:
            gpus.append(name)
    seen: set[str] = set()
    unique: list[str] = []
    for g in gpus:
        if g not in seen:
            seen.add(g)
            unique.append(g)
    return " + ".join(unique)


_DRM_VENDORS = {
    "0x8086": "Intel",
    "0x10de": "NVIDIA",
    "0x1002": "AMD",
    "0x1af4": "VirtIO GPU",
    "0x15ad": "VMware",
    "0x1414": "Microsoft Hyper-V",
    "0x80ee": "VirtualBox",
}


def parse_drm_fallback(vendors_stdout: str) -> str:
    """Concatenated ``/sys/class/drm/card*/device/vendor`` reads → list
    of friendly vendor names. Cheap enough to use when lspci is gone."""
    if not vendors_stdout:
        return ""
    found: list[str] = []
    seen: set[str] = set()
    for line in vendors_stdout.splitlines():
        v = line.strip().lower()
        if not v:
            continue
        name = _DRM_VENDORS.get(v)
        if name and name not in seen:
            seen.add(name)
            found.append(name)
    return " + ".join(found)


def parse_glxinfo(stdout: str) -> str:
    """``LC_ALL=C glxinfo -B`` → OpenGL renderer string. Last-ditch GPU
    source when neither lspci nor /sys/class/drm gave anything."""
    if not stdout:
        return ""
    m = re.search(r"^OpenGL renderer string:\s+(.+)$", stdout, re.MULTILINE)
    if not m:
        return ""
    return _short_gpu_device(_short_gpu_vendor(m.group(1)))


# ── Disk ─────────────────────────────────────────────────────────────────

def parse_findmnt_root(stdout: str) -> str:
    """``findmnt -n -o SOURCE /`` → device path for "/"."""
    if not stdout:
        return ""
    return stdout.strip().split()[0] if stdout.strip() else ""


def parse_proc_mounts_root(stdout: str) -> str:
    """``/proc/mounts`` → first device mounted at "/"."""
    if not stdout:
        return ""
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "/":
            return parts[0]
    return ""


def _base_disk(dev_path: str) -> str:
    """Trim a partition device path to its parent disk.

        /dev/nvme0n1p2 → nvme0n1
        /dev/mmcblk0p1 → mmcblk0
        /dev/sda3      → sda
        /dev/vda1      → vda
        /dev/mapper/x  → mapper/x  (LUKS/LVM — can't trace without -s)

    NVMe and eMMC follow the ``<base>p<N>`` partition convention, where
    ``<base>`` itself ends in a digit (``nvme0n1``, ``mmcblk0``). SCSI /
    SATA / VirtIO follow the older ``<letters><N>`` convention. Strip
    one or the other — never both, or NVMe would lose its namespace
    digit (``nvme0n1`` → ``nvme0n``, missing the parent disk).
    """
    if not dev_path:
        return ""
    name = re.sub(r"^/dev/", "", dev_path)
    if name.startswith("mapper/") or name.startswith("dm-"):
        return name
    # NVMe / eMMC / mmcblk: the partition suffix is "pN".
    m = re.sub(r"p\d+$", "", name)
    if m != name:
        return m
    # SCSI / SATA / VirtIO: the partition suffix is bare digits.
    return re.sub(r"\d+$", "", name)


_DISK_SNAP_GB = (16, 32, 64, 128, 240, 256, 480, 500, 512, 960, 1000, 1024,
                 2000, 2048, 4000, 4096, 8000, 8192)


def _human_disk(bytes_: int) -> str:
    if bytes_ <= 0:
        return ""
    gib = bytes_ / 1073741824
    best = min(_DISK_SNAP_GB, key=lambda s: abs(s - gib))
    if abs(best - gib) > max(20, gib * 0.08):
        # Far enough off the snap table that snapping would mislead.
        return f"{round(gib)} GB"
    if best >= 1000:
        tb = best / 1000
        return f"{int(tb)} TB" if tb.is_integer() else f"{tb:.1f} TB"
    return f"{best} GB"


def parse_lsblk(stdout: str, root_device: str = "") -> str:
    """``lsblk -bdno NAME,SIZE,TYPE,MODEL`` — match the disk that holds
    the root partition; fall back to the first ``disk``-type row."""
    if not stdout:
        return ""
    base = _base_disk(root_device)
    fallback = ""
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 3)
        if len(parts) < 3:
            continue
        name = parts[0]
        try:
            size_bytes = int(parts[1])
        except ValueError:
            continue
        type_ = parts[2]
        if type_ != "disk":
            continue
        model = parts[3].strip() if len(parts) > 3 else ""
        human = _human_disk(size_bytes)
        label = f"{human} {model}".strip() if human else model
        if not fallback:
            fallback = label
        if base and name == base:
            return label
    return fallback


def parse_df_root(stdout: str) -> str:
    """``df -B1 --output=size /`` → root filesystem size in bytes.
    Final fallback when lsblk isn't installed (some musl-based distros).
    """
    if not stdout:
        return ""
    for line in stdout.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        try:
            return _human_disk(int(line))
        except ValueError:
            continue
    return ""


# ── OS ───────────────────────────────────────────────────────────────────

def parse_os_release(stdout: str) -> str:
    if not stdout:
        return ""
    m = re.search(r'^PRETTY_NAME="?([^"\n]+)"?', stdout, re.MULTILINE)
    return m.group(1).strip() if m else ""


def parse_lsb_release(stdout: str) -> str:
    """Both ``/etc/lsb-release`` (DISTRIB_DESCRIPTION="...") and
    ``lsb_release -ds`` (plain line) feed through here."""
    if not stdout:
        return ""
    m = re.search(r'^DISTRIB_DESCRIPTION="?([^"\n]+)"?', stdout, re.MULTILINE)
    if m:
        return m.group(1).strip()
    line = stdout.strip().splitlines()[0] if stdout.strip() else ""
    return line.strip('"').strip()


def parse_uname(stdout: str) -> str:
    """``uname -srm`` → "Linux 6.18.25-1-cachyos-lts x86_64"."""
    return (stdout or "").strip()


def parse_etc_issue(stdout: str) -> str:
    """First non-empty line of ``/etc/issue``, with ``\\n``/``\\l``
    escapes stripped."""
    if not stdout:
        return ""
    for raw in stdout.splitlines():
        cleaned = re.sub(r"\\[a-zA-Z]", "", raw).strip()
        if cleaned:
            return cleaned
    return ""


# ── network / MAC ────────────────────────────────────────────────────────

def parse_default_iface(ip_route_stdout: str) -> str:
    """``ip route get 1.1.1.1`` → name of the egress interface, e.g.
    ``wlp3s0`` or ``eno1``. That single line of output looks like:

        1.1.1.1 via 192.168.1.1 dev wlp3s0 src 192.168.1.42 uid 1000

    We pull the token after ``dev``. The token must start with a
    letter and contain only the characters Linux permits in interface
    names — that rules out matching natural-language "dev token" pairs
    in arbitrary text and keeps the parser strict."""
    if not ip_route_stdout:
        return ""
    m = re.search(r"\bdev\s+([A-Za-z][A-Za-z0-9._-]*)", ip_route_stdout)
    return m.group(1) if m else ""


def parse_proc_route_default(stdout: str) -> str:
    """``/proc/net/route`` → name of the iface for destination 0.0.0.0
    (the default route). Format is tab-separated columns; row with
    ``Destination`` == ``00000000`` is the default."""
    if not stdout:
        return ""
    for line in stdout.splitlines()[1:]:
        cols = line.split()
        if len(cols) >= 2 and cols[1] == "00000000":
            return cols[0]
    return ""


def parse_mac(stdout: str) -> str:
    """``/sys/class/net/<iface>/address`` → 17-char MAC like
    ``a8:7e:ea:12:34:56``. The ``00:00:00:00:00:00`` value some virtual
    interfaces expose is filtered out."""
    if not stdout:
        return ""
    s = stdout.strip().lower()
    if not re.match(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$", s):
        return ""
    if s == "00:00:00:00:00:00":
        return ""
    return s


def format_network(iface: str, mac: str) -> str:
    """Display string: ``<mac> (<iface>)`` when both present, just MAC
    otherwise, ``""`` if no MAC."""
    if not mac:
        return ""
    return f"{mac} ({iface})" if iface else mac


# ── live collection ──────────────────────────────────────────────────────

def _read(path: str) -> str:
    """Read a file as UTF-8 with replace-on-error so a corrupted byte
    can't crash the collector. Any OSError (ENOENT, EACCES, EIO, …)
    silently returns ``""`` so the caller can fall through."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _sh(cmd: list[str], timeout: float = 4.0) -> str:
    """Run a command with LC_ALL=C and UTF-8 decoding, swallow stderr,
    return stdout. Any failure path returns ``""`` so the next source
    in the cascade can answer:

    - ``FileNotFoundError`` — binary not on PATH (busybox without lscpu, …)
    - ``PermissionError`` / other ``OSError`` — sandboxed or SELinux-denied
    - ``TimeoutExpired`` — glxinfo on broken Wayland, dmidecode on bad SMBIOS

    ``LC_ALL=C`` is non-negotiable: lscpu and lspci translate their
    labels under non-English locales, which silently broke every regex
    in v0.13.11.
    """
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    try:
        result = subprocess.run(
            cmd, env=env, capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False,
        )
        return result.stdout or ""
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ""


def _collect_drm_vendors() -> str:
    """Concatenate /sys/class/drm/card*/device/vendor reads. Walk
    glob() inside a try because /sys may be sandboxed away in some
    containers."""
    try:
        drm_root = Path("/sys/class/drm")
        if not drm_root.is_dir():
            return ""
        return "".join(_read(str(p))
                       for p in sorted(drm_root.glob("card*/device/vendor")))
    except OSError:
        return ""


# Every live source — file or subprocess — declared as a (key, callable)
# pair so they can be fanned out across a thread pool. Total wall time is
# now ``max(per-source latency)`` rather than the sum, which matters when
# dmidecode or glxinfo time out (4 s each, would otherwise add 8 s to a
# user-facing modal).
_LIVE_SOURCES: tuple[tuple[str, "callable"], ...] = (
    # DMI sysfs (all cheap, all sudoless except *_serial)
    ("sys_vendor",     lambda: _read("/sys/devices/virtual/dmi/id/sys_vendor")),
    ("board_vendor",   lambda: _read("/sys/devices/virtual/dmi/id/board_vendor")),
    ("product_name",   lambda: _read("/sys/devices/virtual/dmi/id/product_name")),
    ("product_version", lambda: _read("/sys/devices/virtual/dmi/id/product_version")),
    ("board_name",     lambda: _read("/sys/devices/virtual/dmi/id/board_name")),
    ("bios_date",      lambda: _read("/sys/devices/virtual/dmi/id/bios_date")),
    ("product_serial", lambda: _read("/sys/devices/virtual/dmi/id/product_serial")),
    ("board_serial",   lambda: _read("/sys/devices/virtual/dmi/id/board_serial")),
    ("chassis_serial", lambda: _read("/sys/devices/virtual/dmi/id/chassis_serial")),
    # /proc reads (always present on Linux)
    ("cpuinfo",        lambda: _read("/proc/cpuinfo")),
    ("meminfo",        lambda: _read("/proc/meminfo")),
    ("mounts",         lambda: _read("/proc/mounts")),
    ("os_release",     lambda: _read("/etc/os-release")),
    ("lsb_release_file", lambda: _read("/etc/lsb-release")),
    ("etc_issue",      lambda: _read("/etc/issue")),
    ("drm_vendors",    _collect_drm_vendors),
    # subprocess invocations
    ("lscpu",          lambda: _sh(["lscpu"])),
    ("nproc",          lambda: _sh(["nproc", "--all"])),
    ("dmi_cpu",        lambda: _sh(["dmidecode", "-s", "processor-version"])),
    ("free",           lambda: _sh(["free", "-b"])),
    ("dmi_mem",        lambda: _sh(["dmidecode", "-t", "memory"])),
    ("lspci",          lambda: _sh(["lspci", "-mm", "-nn"])),
    ("glxinfo",        lambda: _sh(["glxinfo", "-B"])),
    ("findmnt",        lambda: _sh(["findmnt", "-n", "-o", "SOURCE", "/"])),
    ("lsblk",          lambda: _sh(["lsblk", "-bdno", "NAME,SIZE,TYPE,MODEL"])),
    ("df_root",        lambda: _sh(["df", "-B1", "--output=size", "/"])),
    ("lsb_release_cmd", lambda: _sh(["lsb_release", "-ds"])),
    ("uname",          lambda: _sh(["uname", "-srm"])),
    ("dmi_serial",     lambda: _sh(["dmidecode", "-s", "system-serial-number"])),
    # Network: pick the iface for the default route, then read its MAC.
    # ``ip`` is the modern path; ``/proc/net/route`` is the kernel-side
    # fallback that doesn't need iproute2 installed.
    ("ip_route",       lambda: _sh(["ip", "route", "get", "1.1.1.1"])),
    ("proc_route",     lambda: _read("/proc/net/route")),
)


def _gather_raw() -> dict[str, str]:
    """Run every live source in parallel. Each callable already swallows
    its own errors and returns ``""`` on failure, so the futures here
    never raise."""
    out: dict[str, str] = {key: "" for key, _ in _LIVE_SOURCES}
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(_LIVE_SOURCES)) as pool:
        futures = {pool.submit(fn): key for key, fn in _LIVE_SOURCES}
        for fut in concurrent.futures.as_completed(futures, timeout=20):
            try:
                out[futures[fut]] = fut.result() or ""
            except Exception:
                # _read / _sh already trap their own errors, but if a
                # future raises for any reason (timeout from the pool
                # itself, an unexpected callable) keep the empty default.
                pass
    return out


def collect() -> dict[str, str]:
    """Run every source, parse, and return the rendered display strings.

    All live I/O happens in ``_gather_raw`` (parallel); this function is
    pure parsing. ``parse_*`` functions never raise on malformed input
    — they return ``""`` — so the cascade always lands on a string,
    never a None or an exception."""
    raw = _gather_raw()

    cpu = merge_cpu(parse_lscpu(raw["lscpu"]), parse_cpuinfo(raw["cpuinfo"]))
    chip = first_non_empty(
        cpu["model"],
        parse_dmidecode_cpu(raw["dmi_cpu"]),
    ) or "Unknown"
    cores = first_non_empty(
        cpu["cores"],
        parse_nproc(raw["nproc"]),
    ) or "Unknown"

    memory = first_non_empty(
        parse_meminfo(raw["meminfo"]),
        parse_free_bytes(raw["free"]),
        parse_dmidecode_memory(raw["dmi_mem"]),
    ) or "Unknown"

    graphics = first_non_empty(
        parse_lspci_gpu(raw["lspci"]),
        parse_drm_fallback(raw["drm_vendors"]),
        parse_glxinfo(raw["glxinfo"]),
    ) or "Unknown"

    root_dev = first_non_empty(
        parse_findmnt_root(raw["findmnt"]),
        parse_proc_mounts_root(raw["mounts"]),
    )
    disk = first_non_empty(
        parse_lsblk(raw["lsblk"], root_dev),
        parse_df_root(raw["df_root"]),
    ) or "Unknown"

    os_name = first_non_empty(
        parse_os_release(raw["os_release"]),
        parse_lsb_release(raw["lsb_release_file"] or raw["lsb_release_cmd"]),
        parse_etc_issue(raw["etc_issue"]),
        parse_uname(raw["uname"]),
    ) or "Unknown"

    vendor = first_non_empty(
        parse_vendor(raw["sys_vendor"]),
        parse_vendor(raw["board_vendor"]),
    ) or "Personal Computer"
    model = first_non_empty(
        parse_dmi_string(raw["product_version"]),
        parse_dmi_string(raw["product_name"]),
        parse_dmi_string(raw["board_name"]),
    )
    year = parse_bios_year(raw["bios_date"])

    # Serial — only field that may legitimately be unreadable. The
    # kernel locks DMI serial files to root since 4.10; on a plain user
    # account every cat returns "". dmidecode requires root too.
    serial = first_non_empty(
        parse_dmi_string(raw["product_serial"]),
        parse_dmi_string(raw["board_serial"]),
        parse_dmi_string(raw["chassis_serial"]),
        parse_dmi_string(raw["dmi_serial"]),
    ) or "Not Available"

    # Network: read the MAC of whichever interface holds the default
    # route. This is the macOS-style "Network address" — the one the
    # user would actually identify their machine with on the LAN.
    iface = first_non_empty(
        parse_default_iface(raw["ip_route"]),
        parse_proc_route_default(raw["proc_route"]),
    )
    mac = parse_mac(_read(f"/sys/class/net/{iface}/address")) if iface else ""
    network = format_network(iface, mac) or "Unknown"

    return {
        "vendor": vendor,
        "model": model,
        "year": year,
        "chip": chip,
        "cores": cores,
        "memory": memory,
        "graphics": graphics,
        "disk": disk,
        "network": network,
        "serial": serial,
        "os": os_name,
    }


_UNKNOWN_SCHEMA = {
    "vendor": "Personal Computer", "model": "", "year": "",
    "chip": "Unknown", "cores": "Unknown", "memory": "Unknown",
    "graphics": "Unknown", "disk": "Unknown", "network": "Unknown",
    "serial": "Not Available", "os": "Unknown",
}


# Canned values for the README screenshots. ``MAC_TAHOE_ABOUT_MOCK=1`` or
# ``--mock`` short-circuits live collection and emits this instead, so
# the captured PNGs don't leak the maintainer's MAC address / serial /
# disk model. Chosen to look plausible on a Linux Plasma desktop while
# matching the visual density of a real result (multi-line graphics row
# wrapping, present-but-private serial, etc.).
_MOCK_DATA = {
    "vendor": "ASUS",
    "model": "ROG Crosshair X870E HERO",
    "year": "2025",
    "chip": "AMD Ryzen 9 9950X3D",
    "cores": "32 (16 physical)",
    "memory": "192 GB",
    "graphics": "NVIDIA GeForce RTX 5090",
    "disk": "4 TB Samsung 990 PRO",
    "network": "a8:7e:ea:01:23:45 (eno1)",
    "serial": "Not Available",
    "os": "CachyOS",
}


def main(argv: list[str]) -> int:
    pretty = "--pretty" in argv
    mock = "--mock" in argv or os.environ.get("MAC_TAHOE_ABOUT_MOCK") == "1"

    if mock:
        data = dict(_MOCK_DATA)
    else:
        try:
            data = collect()
        except Exception as exc:
            # collect() should never raise — parsers all return "" on
            # bad input and _gather_raw traps subprocess errors — but
            # if the impossible happens, the UI still gets a full
            # schema so no field renders as ``undefined``.
            print(f"about_info: unexpected error: {exc}", file=sys.stderr)
            data = dict(_UNKNOWN_SCHEMA)
    sys.stdout.write(json.dumps(data, indent=2 if pretty else None,
                                ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
