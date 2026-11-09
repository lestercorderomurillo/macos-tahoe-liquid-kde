# Live desktop proof

Each green entry represents an installed graphical QEMU guest, native package
installation and compilation, light/dark rendering, Firefox interaction,
Nautilus appearance, a real reboot, and successful uninstall. The same installer
engine serves Tahoe and Golden Gate; their edition previews are captured separately
for each release. These results describe the recorded VM configuration.

[Run the checks yourself](README.md). Screenshots below are original 3840×2160
captures at 2× scale. Open an image to inspect it at full resolution.

<a id="debian"></a>
<details>
<summary><b>Debian testing (Forky) — ✅ VM verified · v0.57.3</b></summary>

**Light**

![Debian light](../../src/screenshots/vm/debian/light-db2c5c38c8dc.webp)

**Dark**

![Debian dark](../../src/screenshots/vm/debian/dark-c0980428ece6.webp)

**After reboot**

![Debian after reboot](../../src/screenshots/vm/debian/reboot-ccdfdd941aa2.webp)

**Tested VM**

Plasma 6.7.4 · Qt 6.11.2 · Wayland · systemd · VirtIO/virgl.
Official Debian testing cloud image, with a normal KDE desktop. Debian 13's
stock Plasma 6.3 is below this project's minimum; this run does not qualify it.

**Checks**

| Check | Result |
| --- | --- |
| Full installation and host SDK builds | ✅ Passed |
| Light and dark desktop, loaded Acrylic Glass, Dock autohide | ✅ Passed |
| Firefox rendering, text input, button action and appearance | ✅ Passed |
| Nautilus light/dark pixels and live switching | ✅ Passed |
| Live switch preserves app, Plasma and KWin processes | ✅ Passed |
| Reboot and desktop/app checks | ✅ Passed |
| Full uninstall and removal checks | ✅ Passed |

[Machine-readable results and image hashes](../../src/screenshots/vm/debian/report.json).

</details>

<a id="cachyos"></a>
<details>
<summary><b>CachyOS — ✅ VM verified · v0.57.4</b></summary>

**Light**

![CachyOS light](../../src/screenshots/vm/cachyos/light-ad7e6ab0eca5.webp)

**Dark**

![CachyOS dark](../../src/screenshots/vm/cachyos/dark-5d6eab9d22a2.webp)

**After reboot**

![CachyOS after reboot](../../src/screenshots/vm/cachyos/reboot-7f8d8db91e17.webp)

**Tested VM**

Plasma 6.8.0 · Qt 6.12.0 · Wayland · systemd · VirtIO/virgl.
Installed from the official CachyOS ISO and upgraded with its native repositories.

**Checks**

| Check | Result |
| --- | --- |
| Full installation and host SDK builds | ✅ Passed |
| Light and dark desktop, loaded Acrylic Glass, Dock autohide | ✅ Passed |
| Firefox rendering, text input, button action and appearance | ✅ Passed |
| Nautilus light/dark pixels and live switching | ✅ Passed |
| Live switch preserves app, Plasma and KWin processes | ✅ Passed |
| Reboot and desktop/app checks | ✅ Passed |
| Full uninstall and removal checks | ✅ Passed |

[Machine-readable results and image hashes](../../src/screenshots/vm/cachyos/report.json).

</details>

<a id="arch"></a>
<details>
<summary><b>Arch Linux — ✅ VM verified · v0.57.5</b></summary>

**Light**

![Arch Linux light](../../src/screenshots/vm/arch/light-04fa1012dc03.webp)

**Dark**

![Arch Linux dark](../../src/screenshots/vm/arch/dark-e20d8cf7c4bd.webp)

**After reboot**

![Arch Linux after reboot](../../src/screenshots/vm/arch/reboot-03a3d61e916a.webp)

**Tested VM**

Plasma 6.8.0 · Qt 6.12.0 · Wayland · systemd · VirtIO/virgl.
Official Arch cloud image with KDE Plasma installed from its native repositories.

**Checks**

| Check | Result |
| --- | --- |
| Full installation and host SDK builds | ✅ Passed |
| Light and dark desktop, loaded Acrylic Glass, Dock autohide | ✅ Passed |
| Firefox rendering, text input, button action and appearance | ✅ Passed |
| Nautilus light/dark pixels and live switching | ✅ Passed |
| Live switch preserves app, Plasma and KWin processes | ✅ Passed |
| Reboot and desktop/app checks | ✅ Passed |
| Full uninstall and removal checks | ✅ Passed |

[Machine-readable results and image hashes](../../src/screenshots/vm/arch/report.json).

</details>

<a id="endeavouros"></a>
<details>
<summary><b>EndeavourOS — ✅ VM verified · v0.57.9</b></summary>

**Light**

![EndeavourOS light](../../src/screenshots/vm/endeavouros/light-a40ed8e4d780.webp)

**Dark**

![EndeavourOS dark](../../src/screenshots/vm/endeavouros/dark-df6a395f14ae.webp)

**After reboot**

![EndeavourOS after reboot](../../src/screenshots/vm/endeavouros/reboot-b57409cd3b05.webp)

**Tested VM**

Plasma 6.8.0 · Qt 6.12.0 · Wayland · systemd · VirtIO/virgl.
Official EndeavourOS ISO with native KDE desktop and a full distribution upgrade.

**Checks**

| Check | Result |
| --- | --- |
| Full installation and host SDK builds | ✅ Passed |
| Light and dark desktop, loaded Acrylic Glass, Dock autohide | ✅ Passed |
| Firefox rendering, text input, button action and appearance | ✅ Passed |
| Nautilus light/dark pixels and live switching | ✅ Passed |
| Live switch preserves app, Plasma and KWin processes | ✅ Passed |
| Reboot and desktop/app checks | ✅ Passed |
| Full uninstall and removal checks | ✅ Passed |

[Machine-readable results and image hashes](../../src/screenshots/vm/endeavouros/report.json).

</details>

<a id="fedora"></a>
<details>
<summary><b>Fedora — ✅ VM verified · v0.57.8</b></summary>

**Light**

![Fedora light](../../src/screenshots/vm/fedora/light-52d8b52aa131.webp)

**Dark**

![Fedora dark](../../src/screenshots/vm/fedora/dark-ab71ca191d88.webp)

**After reboot**

![Fedora after reboot](../../src/screenshots/vm/fedora/reboot-f9b7b986829a.webp)

**Tested VM**

Plasma 6.7.5 · Qt 6.11.2 · Wayland · systemd · VirtIO/virgl.
Official Fedora 44 cloud image with native KDE desktop and packages.

**Checks**

| Check | Result |
| --- | --- |
| Full installation and host SDK builds | ✅ Passed |
| Light and dark desktop, loaded Acrylic Glass, Dock autohide | ✅ Passed |
| Firefox rendering, text input, button action and appearance | ✅ Passed |
| Nautilus light/dark pixels and live switching | ✅ Passed |
| Live switch preserves app, Plasma and KWin processes | ✅ Passed |
| Reboot and desktop/app checks | ✅ Passed |
| Full uninstall and removal checks | ✅ Passed |

[Machine-readable results and image hashes](../../src/screenshots/vm/fedora/report.json).

</details>

<a id="manjaro"></a>
<details>
<summary><b>Manjaro — ✅ VM verified · v0.57.10</b></summary>

**Light**

![Manjaro light](../../src/screenshots/vm/manjaro/light-fc4d40151547.webp)

**Dark**

![Manjaro dark](../../src/screenshots/vm/manjaro/dark-bcae493cb335.webp)

**After reboot**

![Manjaro after reboot](../../src/screenshots/vm/manjaro/reboot-936f07329942.webp)

**Tested VM**

Plasma 6.7.4 · Qt 6.11.2 · Wayland · systemd · VirtIO/virgl.
Official Manjaro KDE ISO with native packages.

**Checks**

| Check | Result |
| --- | --- |
| Full installation and host SDK builds | ✅ Passed |
| Light and dark desktop, loaded Acrylic Glass, Dock autohide | ✅ Passed |
| Firefox rendering, text input, button action and appearance | ✅ Passed |
| Nautilus light/dark pixels and live switching | ✅ Passed |
| Live switch preserves app, Plasma and KWin processes | ✅ Passed |
| Reboot and desktop/app checks | ✅ Passed |
| Full uninstall and removal checks | ✅ Passed |

[Machine-readable results and image hashes](../../src/screenshots/vm/manjaro/report.json).

</details>

<a id="artix"></a>
<details>
<summary><b>Artix Linux (OpenRC) — ✅ VM verified · v0.57.11</b></summary>

**Light**

![Artix Linux (OpenRC) light](../../src/screenshots/vm/artix/light-818b2b786445.webp)

**Dark**

![Artix Linux (OpenRC) dark](../../src/screenshots/vm/artix/dark-efe24bbe0c0b.webp)

**After reboot**

![Artix Linux (OpenRC) after reboot](../../src/screenshots/vm/artix/reboot-c99f281e2a54.webp)

**Tested VM**

Plasma 6.8.0 · Qt 6.12.0 · Wayland · openrc · VirtIO/virgl.
Official Artix Plasma OpenRC ISO with native packages and per-user cron scheduling.

**Checks**

| Check | Result |
| --- | --- |
| Full installation and host SDK builds | ✅ Passed |
| Light and dark desktop, loaded Acrylic Glass, Dock autohide | ✅ Passed |
| Firefox rendering, text input, button action and appearance | ✅ Passed |
| Nautilus light/dark pixels and live switching | ✅ Passed |
| Live switch preserves app, Plasma and KWin processes | ✅ Passed |
| Reboot and desktop/app checks | ✅ Passed |
| Full uninstall and removal checks | ✅ Passed |

[Machine-readable results and image hashes](../../src/screenshots/vm/artix/report.json).

</details>

<a id="garuda"></a>
<details>
<summary><b>Garuda Linux — ✅ VM verified · v0.57.12</b></summary>

**Light**

![Garuda Linux light](../../src/screenshots/vm/garuda/light-f87227465173.webp)

**Dark**

![Garuda Linux dark](../../src/screenshots/vm/garuda/dark-96da0552a722.webp)

**After reboot**

![Garuda Linux after reboot](../../src/screenshots/vm/garuda/reboot-743c7d23e7e0.webp)

**Tested VM**

Plasma 6.8.0 · Qt 6.12.0 · Wayland · systemd · VirtIO/virgl.
Official Garuda KDE ISO with native packages.

**Checks**

| Check | Result |
| --- | --- |
| Full installation and host SDK builds | ✅ Passed |
| Light and dark desktop, loaded Acrylic Glass, Dock autohide | ✅ Passed |
| Firefox rendering, text input, button action and appearance | ✅ Passed |
| Nautilus light/dark pixels and live switching | ✅ Passed |
| Live switch preserves app, Plasma and KWin processes | ✅ Passed |
| Reboot and desktop/app checks | ✅ Passed |
| Full uninstall and removal checks | ✅ Passed |

[Machine-readable results and image hashes](../../src/screenshots/vm/garuda/report.json).

</details>

<a id="nobara"></a>
<details>
<summary><b>Nobara — ✅ VM verified · v0.57.13</b></summary>

**Light**

![Nobara light](../../src/screenshots/vm/nobara/light-04a9ecb375da.webp)

**Dark**

![Nobara dark](../../src/screenshots/vm/nobara/dark-b71945558810.webp)

**After reboot**

![Nobara after reboot](../../src/screenshots/vm/nobara/reboot-5b0113d37cb8.webp)

**Tested VM**

Plasma 6.7.5 · Qt 6.11.2 · Wayland · systemd · VirtIO/virgl.
Official Nobara 44 KDE ISO with native packages.

**Checks**

| Check | Result |
| --- | --- |
| Full installation and host SDK builds | ✅ Passed |
| Light and dark desktop, loaded Acrylic Glass, Dock autohide | ✅ Passed |
| Firefox rendering, text input, button action and appearance | ✅ Passed |
| Nautilus light/dark pixels and live switching | ✅ Passed |
| Live switch preserves app, Plasma and KWin processes | ✅ Passed |
| Reboot and desktop/app checks | ✅ Passed |
| Full uninstall and removal checks | ✅ Passed |

[Machine-readable results and image hashes](../../src/screenshots/vm/nobara/report.json).

</details>

<a id="opensuse"></a>
<details>
<summary><b>openSUSE Tumbleweed — ✅ VM verified · v0.57.7</b></summary>

**Light**

![openSUSE Tumbleweed light](../../src/screenshots/vm/opensuse/light-95fc6f10cc1c.webp)

**Dark**

![openSUSE Tumbleweed dark](../../src/screenshots/vm/opensuse/dark-18f8a3d9c86c.webp)

**After reboot**

![openSUSE Tumbleweed after reboot](../../src/screenshots/vm/opensuse/reboot-ca1f78b5974c.webp)

**Tested VM**

Plasma 6.8.0 · Qt 6.12.0 · Wayland · systemd · VirtIO/virgl.
Official openSUSE Tumbleweed cloud image with native KDE desktop and packages.

**Checks**

| Check | Result |
| --- | --- |
| Full installation and host SDK builds | ✅ Passed |
| Light and dark desktop, loaded Acrylic Glass, Dock autohide | ✅ Passed |
| Firefox rendering, text input, button action and appearance | ✅ Passed |
| Nautilus light/dark pixels and live switching | ✅ Passed |
| Live switch preserves app, Plasma and KWin processes | ✅ Passed |
| Reboot and desktop/app checks | ✅ Passed |
| Full uninstall and removal checks | ✅ Passed |

[Machine-readable results and image hashes](../../src/screenshots/vm/opensuse/report.json).

</details>

<a id="neon"></a>
<details>
<summary><b>KDE neon — ✅ VM verified · v0.57.6</b></summary>

**Light**

![KDE neon light](../../src/screenshots/vm/neon/light-69884b16d0c0.webp)

**Dark**

![KDE neon dark](../../src/screenshots/vm/neon/dark-ade3e158ad34.webp)

**After reboot**

![KDE neon after reboot](../../src/screenshots/vm/neon/reboot-3ae480081973.webp)

**Tested VM**

Plasma 6.8.1 · Qt 6.11.1 · Wayland · systemd · VirtIO/virgl.
Official KDE neon image with its native KDE desktop and packages.

**Checks**

| Check | Result |
| --- | --- |
| Full installation and host SDK builds | ✅ Passed |
| Light and dark desktop, loaded Acrylic Glass, Dock autohide | ✅ Passed |
| Firefox rendering, text input, button action and appearance | ✅ Passed |
| Nautilus light/dark pixels and live switching | ✅ Passed |
| Live switch preserves app, Plasma and KWin processes | ✅ Passed |
| Reboot and desktop/app checks | ✅ Passed |
| Full uninstall and removal checks | ✅ Passed |

[Machine-readable results and image hashes](../../src/screenshots/vm/neon/report.json).

</details>

<a id="nixos"></a>
<details>
<summary><b>NixOS — evidence pending</b></summary>

The NixOS and Home Manager installation route remains experimental. Live desktop
validation and reviewed screenshots have not been published yet.

</details>

All 11 distributions in the supported VM matrix have completed the live desktop checks above. The separate experimental NixOS route remains unqualified.
