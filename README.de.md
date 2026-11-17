<p align="center">
  <!-- Artwork: https://developer.apple.com/assets/elements/icons/macos-26/macos-26-128x128_2x.png -->
  <img src="src/screenshots/macos-26.png" alt="macOS 26 circular emblem" width="180" height="180">
</p>

<h1 align="center">macOS Tahoe for KDE Plasma</h1>

<p align="center">
  <a href="README.md" lang="en" hreflang="en">🇺🇸 English</a> ·
  <a href="README.es.md" lang="es" hreflang="es">🇪🇸 Español</a> ·
  <a href="README.zh-CN.md" lang="zh-CN" hreflang="zh-CN">🇨🇳 简体中文</a> ·
  <a href="README.pt-BR.md" lang="pt-BR" hreflang="pt-BR">🇧🇷 Português (Brasil)</a> ·
  <a href="README.de.md" lang="de" hreflang="de" aria-current="page">🇩🇪 Deutsch</a> ·
  <a href="README.fr.md" lang="fr" hreflang="fr">🇫🇷 Français</a>
</p>

<p align="center">
  <a href="https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/releases"><img src="https://img.shields.io/github/v/release/lestercorderomurillo/macos-tahoe-liquid-kde?label=release&amp;color=blue" alt="release"></a>
  <a href="https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/workflows/test.yml"><img src="https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/workflows/test.yml/badge.svg?branch=dev" alt="tests"></a>
  <a href="https://kde.org/plasma-desktop/"><img src="https://img.shields.io/badge/Plasma-6.6%2B-1d99f3?logo=kde" alt="plasma"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-blue" alt="license"></a>
  <a href="https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new"><img src="https://img.shields.io/badge/report-a%20bug-red?logo=github" alt="report a bug"></a>
</p>

<p align="center">macOS-Tahoe-Stil für KDE Plasma 6.6, 6.7 und 6.8+.</p>

> [!CAUTION]
> Experimentelles Projekt mit häufigen Aktualisierungen, die die Kompatibilität beeinträchtigen können. Nicht auf Produktivsystemen einsetzen. Dieses Projekt ist kostenlos: Es sind weder Kauf noch Abonnement erforderlich.

<p align="center"><sub>Eine Distribution auswählen, um ihre Testergebnisse zu sehen.</sub></p>

<p align="center">
  <a href="tests/vm/PROOF.md#cachyos" title="CachyOS"><img src="src/screenshots/distros/cachyos.svg" alt="CachyOS" width="32" height="32"></a>
  <a href="tests/vm/PROOF.md#arch" title="Arch Linux"><img src="src/screenshots/distros/archlinux.svg" alt="Arch Linux" width="32" height="32"></a>
  <a href="tests/vm/PROOF.md#endeavouros" title="EndeavourOS"><img src="src/screenshots/distros/endeavouros.svg" alt="EndeavourOS" width="32" height="32"></a>
  <a href="tests/vm/PROOF.md#fedora" title="Fedora"><img src="src/screenshots/distros/fedora.svg" alt="Fedora" width="32" height="32"></a>
  <a href="tests/vm/PROOF.md#manjaro" title="Manjaro"><img src="src/screenshots/distros/manjaro.svg" alt="Manjaro" width="32" height="32"></a>
  <a href="tests/vm/PROOF.md#artix" title="Artix Linux (OpenRC)"><img src="src/screenshots/distros/artixlinux.svg" alt="Artix Linux" width="32" height="32"></a>
  <a href="tests/vm/PROOF.md#garuda" title="Garuda Linux"><img src="src/screenshots/distros/garudalinux.svg" alt="Garuda Linux" width="32" height="32"></a>
  <a href="tests/vm/PROOF.md#nobara" title="Nobara Linux"><img src="src/screenshots/distros/nobaralinux.svg" alt="Nobara Linux" width="32" height="32"></a>
  <a href="tests/vm/PROOF.md#opensuse" title="openSUSE Tumbleweed"><img src="src/screenshots/distros/opensuse.svg" alt="openSUSE" width="32" height="32"></a>
  <a href="tests/vm/PROOF.md#neon" title="KDE neon"><img src="src/screenshots/distros/kdeneon.svg" alt="KDE neon" width="32" height="32"></a>
  <a href="tests/vm/PROOF.md#debian" title="Debian testing / sid (Plasma 6.6+)"><img src="src/screenshots/distros/debian.svg" alt="Debian" width="32" height="32"></a>
  <a href="tests/vm/PROOF.md#nixos" title="NixOS (experimental)"><img src="src/screenshots/distros/nixos.svg" alt="NixOS" width="32" height="32"></a>
</p>

## Installation und Aktualisierungen

Repository herunterladen und das Installationsprogramm öffnen:

```bash
git clone --filter=blob:none https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde.git
cd macos-tahoe-liquid-kde
./installer
```

Zum Installieren **Express** wählen. Zum Aktualisieren oder Deinstallieren `./installer` erneut öffnen.

Diese Edition verwendet Tahoe, das dazugehörige Hintergrundbild und Starter-Voreinstellung 1. Die Optionen lassen sich im Assistenten ändern.

Das Installationsprogramm ist auf Englisch, Spanisch, vereinfachtem Chinesisch, brasilianischem Portugiesisch, Deutsch und Französisch verfügbar. Geplante Sprachen stehen in der [vollständigen Übersicht](README.md).

## Voraussetzungen und Kompatibilität

Erforderlich sind KDE Plasma 6.6 oder neuer, Python 3.10+, PyQt6, `sudo` und Qt-6/KDE-Entwicklungswerkzeuge. Kompilierte Komponenten benötigen `cmake`, `g++` und `pkg-config`. Downloads, fehlende Abhängigkeiten und KDE Rounded Corners benötigen einen Internetzugang.

Plasma 6.6–6.8 wird unterstützt; 6.5 und ältere Versionen nicht. Native Effekte werden gegen Qt und KWin des Systems kompiliert. Elf Distributionen wurden in virtuellen Maschinen geprüft: CachyOS, Arch, EndeavourOS, Fedora, Manjaro, Artix/OpenRC, Garuda, Nobara, openSUSE Tumbleweed, KDE neon und Debian testing/sid. Damit sind nicht alle Konfigurationen abgedeckt.

Automatischer Hell-/Dunkelwechsel und OLED-Schutz verwenden systemd-Benutzertimer oder benutzerspezifisches cron unter OpenRC/dinit. OpenRC und dinit benötigen einen laufenden cron-Dienst. Die Desktop-Prüfung für dinit und Kubuntu steht noch aus; die Artix-Fotos zeigen OpenRC.

## Funktionen und Bildschirmfotos

### Tahoe Finder (Alpha)

Dateiverwaltung im Finder-Stil mit Tahoe-Glas.

<p align="center">
  <a href="src/screenshots/showcase_light_2k-5dedfb291557.webp"><img src="src/screenshots/showcase_light_2k-5dedfb291557.webp" alt="Tahoe Finder · Hell" width="415"></a>
  <a href="src/screenshots/showcase_dark_2k-b6fcdffe7c22.webp"><img src="src/screenshots/showcase_dark_2k-b6fcdffe7c22.webp" alt="Tahoe Finder · Dunkel" width="415"></a>
</p>

<details>
<summary>Rote und blaue Akzente im hellen und dunklen Modus</summary>

<table>
<tr><th>Akzent</th><th>Hell</th><th>Dunkel</th></tr>
<tr><td>Rot</td><td><a href="src/screenshots/previews/tahoe-light-finder-red-a330af534340.webp"><img src="src/screenshots/previews/tahoe-light-finder-red-a330af534340.webp" alt="Tahoe Finder · Hell" width="415"></a></td><td><a href="src/screenshots/previews/tahoe-dark-finder-red-10e9028543a1.webp"><img src="src/screenshots/previews/tahoe-dark-finder-red-10e9028543a1.webp" alt="Tahoe Finder · Dunkel" width="415"></a></td></tr>
<tr><td>Blau</td><td><a href="src/screenshots/previews/tahoe-light-finder-blue-bbf03b509a68.webp"><img src="src/screenshots/previews/tahoe-light-finder-blue-bbf03b509a68.webp" alt="Tahoe Finder · Hell" width="415"></a></td><td><a href="src/screenshots/previews/tahoe-dark-finder-blue-8ac67b97300d.webp"><img src="src/screenshots/previews/tahoe-dark-finder-blue-8ac67b97300d.webp" alt="Tahoe Finder · Dunkel" width="415"></a></td></tr>
</table>

</details>

### Tahoe Launchpad (Alpha)

Anwendungen suchen, Kategorien durchsuchen und Favoriten griffbereit halten. Zwei Voreinstellungen stehen zur Auswahl.

<p align="center">
  <img src="src/screenshots/launcher_preset_1_light-2234900b9d82.webp" alt="Tahoe Launchpad · Hell" width="415">
  <img src="src/screenshots/launcher_preset_1_dark-0cabfbb9e4f6.webp" alt="Tahoe Launchpad · Dunkel" width="415">
</p>

### Tahoe Dock (Alpha)

Glasbrechung, Vergrößerung beim Überfahren, Benachrichtigungszähler und automatisches Ausblenden.

<p align="center"><a href="src/screenshots/previews/tahoe-dock-regular-light-reference-74619aaa7764.webp"><img src="src/screenshots/previews/tahoe-dock-regular-light-reference-74619aaa7764.webp" alt="Tahoe Dock · Hell" width="415"></a><br>Standard · Hell</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-regular-dark-reference-5a56afc6c7ac.webp"><img src="src/screenshots/previews/tahoe-dock-regular-dark-reference-5a56afc6c7ac.webp" alt="Tahoe Dock · Dunkel" width="415"></a><br>Standard · Dunkel</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-clear-light-reference-97f0fdd5e0a1.webp"><img src="src/screenshots/previews/tahoe-dock-clear-light-reference-97f0fdd5e0a1.webp" alt="Tahoe Dock · Hell" width="415"></a><br>Transparent · Hell</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-clear-dark-reference-9cdf564ebb32.webp"><img src="src/screenshots/previews/tahoe-dock-clear-dark-reference-9cdf564ebb32.webp" alt="Tahoe Dock · Dunkel" width="415"></a><br>Transparent · Dunkel</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-blue-light-reference-451ebd6e17bc.webp"><img src="src/screenshots/previews/tahoe-dock-blue-light-reference-451ebd6e17bc.webp" alt="Tahoe Dock · Hell" width="415"></a><br>Blau · Hell</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-blue-dark-reference-a2757a9e1690.webp"><img src="src/screenshots/previews/tahoe-dock-blue-dark-reference-a2757a9e1690.webp" alt="Tahoe Dock · Dunkel" width="415"></a><br>Blau · Dunkel</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-purple-light-reference-ce34696e8a65.webp"><img src="src/screenshots/previews/tahoe-dock-purple-light-reference-ce34696e8a65.webp" alt="Tahoe Dock · Hell" width="415"></a><br>Violett · Hell</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-purple-dark-reference-a9513c3b6673.webp"><img src="src/screenshots/previews/tahoe-dock-purple-dark-reference-a9513c3b6673.webp" alt="Tahoe Dock · Dunkel" width="415"></a><br>Violett · Dunkel</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-pink-light-reference-080e7323ffb1.webp"><img src="src/screenshots/previews/tahoe-dock-pink-light-reference-080e7323ffb1.webp" alt="Tahoe Dock · Hell" width="415"></a><br>Rosa · Hell</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-pink-dark-reference-37badc9241a8.webp"><img src="src/screenshots/previews/tahoe-dock-pink-dark-reference-37badc9241a8.webp" alt="Tahoe Dock · Dunkel" width="415"></a><br>Rosa · Dunkel</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-red-light-reference-a654bc25c74f.webp"><img src="src/screenshots/previews/tahoe-dock-red-light-reference-a654bc25c74f.webp" alt="Tahoe Dock · Hell" width="415"></a><br>Rot · Hell</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-red-dark-reference-2799aac75e5c.webp"><img src="src/screenshots/previews/tahoe-dock-red-dark-reference-2799aac75e5c.webp" alt="Tahoe Dock · Dunkel" width="415"></a><br>Rot · Dunkel</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-orange-light-reference-25bcc0e95908.webp"><img src="src/screenshots/previews/tahoe-dock-orange-light-reference-25bcc0e95908.webp" alt="Tahoe Dock · Hell" width="415"></a><br>Orange · Hell</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-orange-dark-reference-70fab1e16209.webp"><img src="src/screenshots/previews/tahoe-dock-orange-dark-reference-70fab1e16209.webp" alt="Tahoe Dock · Dunkel" width="415"></a><br>Orange · Dunkel</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-yellow-light-reference-ccb4a109822b.webp"><img src="src/screenshots/previews/tahoe-dock-yellow-light-reference-ccb4a109822b.webp" alt="Tahoe Dock · Hell" width="415"></a><br>Gelb · Hell</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-yellow-dark-reference-9bde557131d1.webp"><img src="src/screenshots/previews/tahoe-dock-yellow-dark-reference-9bde557131d1.webp" alt="Tahoe Dock · Dunkel" width="415"></a><br>Gelb · Dunkel</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-green-light-reference-36f3c1ba2de1.webp"><img src="src/screenshots/previews/tahoe-dock-green-light-reference-36f3c1ba2de1.webp" alt="Tahoe Dock · Hell" width="415"></a><br>Grün · Hell</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-green-dark-reference-6f4857af9d43.webp"><img src="src/screenshots/previews/tahoe-dock-green-dark-reference-6f4857af9d43.webp" alt="Tahoe Dock · Dunkel" width="415"></a><br>Grün · Dunkel</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-gray-light-reference-de7e0b3ebeae.webp"><img src="src/screenshots/previews/tahoe-dock-gray-light-reference-de7e0b3ebeae.webp" alt="Tahoe Dock · Hell" width="415"></a><br>Grau · Hell</p>

<p align="center"><a href="src/screenshots/previews/tahoe-dock-gray-dark-reference-85d9f5de1cae.webp"><img src="src/screenshots/previews/tahoe-dock-gray-dark-reference-85d9f5de1cae.webp" alt="Tahoe Dock · Dunkel" width="415"></a><br>Grau · Dunkel</p>

### Tahoe Shell (Alpha)

Zugriff auf Systemeinstellungen, Anwendungen und Sitzungsaktionen.

<p align="center">
  <img src="src/screenshots/menu_v4-b41832636db3.webp" alt="Tahoe Shell · Hell" width="415">
  <img src="src/screenshots/menu_dark_v4-0f9fbb1971bd.webp" alt="Tahoe Shell · Dunkel" width="415">
</p>

### Tahoe Kontrollzentrum (Alpha)

WLAN, Klang, Helligkeit und Benachrichtigungen in einem Glasmenü.

<p align="center">
  <img src="src/screenshots/control-center-light-912d3227499f.webp" alt="Tahoe Kontrollzentrum · Hell" width="415">
  <img src="src/screenshots/control-center-dark-0413d0b90a04.webp" alt="Tahoe Kontrollzentrum · Dunkel" width="415">
</p>

### Tahoe Zwischenablageverlauf (Alpha)

Kopierte Texte und Bilder direkt im Launchpad finden und wiederverwenden.

<p align="center">
  <img src="src/screenshots/previews/clipboard-launcher-light-41232b9ea980.webp" alt="Tahoe Zwischenablageverlauf · Hell" width="415">
  <img src="src/screenshots/previews/clipboard-launcher-dark-383fc47bdf9a.webp" alt="Tahoe Zwischenablageverlauf · Dunkel" width="415">
</p>

### Tahoe Systeminformationen

Informationen zu Hardware, Software und Design.

<p align="center">
  <img src="src/screenshots/about_v4-03352b9758c3.webp" alt="Tahoe Systeminformationen · Hell" width="415">
  <img src="src/screenshots/about_dark_v4-f2d6c47fe0e6.webp" alt="Tahoe Systeminformationen · Dunkel" width="415">
</p>

### Tahoe Plasma-Design (Alpha)

Durchscheinende Menüs und Popups mit abgestimmten hellen und dunklen Farben.

<p align="center">
  <img src="src/screenshots/context_menu_v4-1e63c5d70acd.webp" alt="Tahoe Plasma-Design · Hell" width="415">
  <img src="src/screenshots/context_menu_dark_v4-7148ec8f973c.webp" alt="Tahoe Plasma-Design · Dunkel" width="415">
</p>

### Tahoe Startbildschirm (Alpha)

Startbildschirm mit integrierter Entsperrung von LUKS2-verschlüsselten Laufwerken.

<p align="center">
  <img src="src/screenshots/boot_v4-1f628792b5bc.webp" alt="Tahoe Startbildschirm" width="415">
</p>

## Optionen und Werkzeuge

Im Assistenten lassen sich Komponenten, Symbole, Hintergrundbilder, Fensterknöpfe und Fensterschatten auswählen. Eine Neuinstallation erhält die Dock-Anpassungen, sofern kein Zurücksetzen gewählt wird. Das Design synchronisiert die helle/dunkle Darstellung, integriert globale Menüs und GTK/Qt-Stile und sichert Firefox-Profile vor Änderungen.

Der OLED-Schutz ist optional und standardmäßig deaktiviert. Im Assistenten aktivieren und Intervall sowie maximale Verschiebung wählen. Manuelle Steuerung:

```bash
mac-tahoe-oled-care shift
mac-tahoe-oled-care restore
mac-tahoe-oled-care status
```

Zum Testen in einem isolierten Desktop `./vm <os>` verwenden. Siehe [VM-Anleitung](tests/vm/README.md). Die vollständige Kubuntu-Prüfung steht noch aus. NixOS und Home Manager sind experimentell: Flake-Module statt des grafischen Installationsprogramms verwenden; siehe [ausführliche Konfiguration auf Englisch](README.md).

Die [Beitragsrichtlinien](CONTRIBUTING.md) beschreiben erweiterte Einstellungen und den gemeinsamen Symbolgenerator. Mit `./icon-toolset` im Tahoe-Repository lassen sich Symbole für beide Editionen erzeugen, vorab ansehen und prüfen, ohne das Desktop-Design anzuwenden. Git-Speicher freigeben und lokale Arbeit erhalten: `./installer --free-space`.

Siehe [Testergebnisse und Abdeckungsgrenzen](tests/vm/PROOF.md) sowie [Bildschirmfotos des Installationsprogramms](TESTING.md). Die Fotos behalten ihre ursprünglichen Herkunftsnachweise; sie belegen keine erneute Prüfung jeder Version.

[Vollständige technische Referenz und Komponentenstatus (Englisch)](README.md)

## Beiträge und Fehlerberichte

Bei [Fehlerberichten](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new) Plasma-Version (`plasmashell --version`), Distribution, Designversion und bei Darstellungsproblemen ein Bildschirmfoto oder Video angeben. Siehe [Beitragsrichtlinien](CONTRIBUTING.md).

Code-Mitwirkende und Personen, die Fehler für Tahoe und Golden Gate gemeldet haben:

<p>
  <a href="https://github.com/lestercorderomurillo"><img src="src/screenshots/contributors/lestercorderomurillo.svg" width="40" height="40" alt="@lestercorderomurillo" title="@lestercorderomurillo"></a>
  <a href="https://github.com/yanhenrique-dev"><img src="src/screenshots/contributors/yanhenrique-dev.svg" width="40" height="40" alt="@yanhenrique-dev" title="@yanhenrique-dev"></a>
  <a href="https://github.com/naevui"><img src="src/screenshots/contributors/naevui.svg" width="40" height="40" alt="@naevui" title="@naevui"></a>
  <a href="https://github.com/caioniehues"><img src="src/screenshots/contributors/caioniehues.svg" width="40" height="40" alt="@caioniehues" title="@caioniehues"></a>
  <a href="https://github.com/404-not-found129"><img src="src/screenshots/contributors/404-not-found129.svg" width="40" height="40" alt="@404-not-found129" title="@404-not-found129"></a>
  <a href="https://github.com/myakupozluk"><img src="src/screenshots/contributors/myakupozluk.svg" width="40" height="40" alt="@myakupozluk" title="@myakupozluk"></a>
  <a href="https://github.com/EMS1998"><img src="src/screenshots/contributors/EMS1998.svg" width="40" height="40" alt="@EMS1998" title="@EMS1998"></a>
  <a href="https://github.com/allfritz"><img src="src/screenshots/contributors/allfritz.svg" width="40" height="40" alt="@allfritz" title="@allfritz"></a>
  <a href="https://github.com/elegos"><img src="src/screenshots/contributors/elegos.svg" width="40" height="40" alt="@elegos" title="@elegos"></a>
  <a href="https://github.com/kozeki-uii"><img src="src/screenshots/contributors/kozeki-uii.svg" width="40" height="40" alt="@kozeki-uii" title="@kozeki-uii"></a>
  <a href="https://github.com/imightbelosthere"><img src="src/screenshots/contributors/imightbelosthere.svg" width="40" height="40" alt="@imightbelosthere" title="@imightbelosthere"></a>
  <a href="https://github.com/evaildev"><img src="src/screenshots/contributors/evaildev.svg" width="40" height="40" alt="@evaildev" title="@evaildev"></a>
  <a href="https://github.com/xarblu"><img src="src/screenshots/contributors/xarblu.svg" width="40" height="40" alt="@xarblu" title="@xarblu"></a>
  <a href="https://github.com/PKMNPlatin"><img src="src/screenshots/contributors/PKMNPlatin.svg" width="40" height="40" alt="@PKMNPlatin" title="@PKMNPlatin"></a>
  <a href="https://github.com/matinlotfali"><img src="src/screenshots/contributors/matinlotfali.svg" width="40" height="40" alt="@matinlotfali" title="@matinlotfali"></a>
  <a href="https://github.com/luisbocanegra"><img src="src/screenshots/contributors/luisbocanegra.svg" width="40" height="40" alt="@luisbocanegra" title="@luisbocanegra"></a>
  <a href="https://github.com/OliverChase2003"><img src="src/screenshots/contributors/OliverChase2003.svg" width="40" height="40" alt="@OliverChase2003" title="@OliverChase2003"></a>
  <a href="https://github.com/RoxasYTB"><img src="src/screenshots/contributors/RoxasYTB.svg" width="40" height="40" alt="@RoxasYTB" title="@RoxasYTB"></a>
  <a href="https://github.com/Flagwill"><img src="src/screenshots/contributors/Flagwill.svg" width="40" height="40" alt="@Flagwill" title="@Flagwill"></a>
  <a href="https://github.com/4l3j0Ok"><img src="src/screenshots/contributors/4l3j0Ok.svg" width="40" height="40" alt="@4l3j0Ok" title="@4l3j0Ok"></a>
  <a href="https://github.com/0xrushi"><img src="src/screenshots/contributors/0xrushi-88d08627bc35.svg" width="40" height="40" alt="@0xrushi" title="@0xrushi"></a>
  <a href="https://github.com/aenriii"><img src="src/screenshots/contributors/aenriii-b3ff7f30e5bb.svg" width="40" height="40" alt="@aenriii" title="@aenriii"></a>
  <a href="https://github.com/andreas399"><img src="src/screenshots/contributors/andreas399-00993524b291.svg" width="40" height="40" alt="@andreas399" title="@andreas399"></a>
  <a href="https://github.com/Andrew-Sor"><img src="src/screenshots/contributors/Andrew-Sor-94949c08022e.svg" width="40" height="40" alt="@Andrew-Sor" title="@Andrew-Sor"></a>
  <a href="https://github.com/ardashir77"><img src="src/screenshots/contributors/ardashir77-40723979caf5.svg" width="40" height="40" alt="@ardashir77" title="@ardashir77"></a>
  <a href="https://github.com/azizaktas"><img src="src/screenshots/contributors/azizaktas-3e26627b326b.svg" width="40" height="40" alt="@azizaktas" title="@azizaktas"></a>
  <a href="https://github.com/binary-pleb"><img src="src/screenshots/contributors/binary-pleb-f740b0b97491.svg" width="40" height="40" alt="@binary-pleb" title="@binary-pleb"></a>
  <a href="https://github.com/bneils"><img src="src/screenshots/contributors/bneils-fb7ae850b1d9.svg" width="40" height="40" alt="@bneils" title="@bneils"></a>
  <a href="https://github.com/FAYZER77"><img src="src/screenshots/contributors/FAYZER77-d2d7b1894be9.svg" width="40" height="40" alt="@FAYZER77" title="@FAYZER77"></a>
  <a href="https://github.com/fxrncyyisingithub"><img src="src/screenshots/contributors/fxrncyyisingithub-318dada63e53.svg" width="40" height="40" alt="@fxrncyyisingithub" title="@fxrncyyisingithub"></a>
  <a href="https://github.com/germanbagutteorsomething"><img src="src/screenshots/contributors/germanbagutteorsomething-ab237be9d3ca.svg" width="40" height="40" alt="@germanbagutteorsomething" title="@germanbagutteorsomething"></a>
  <a href="https://github.com/iNarrow12"><img src="src/screenshots/contributors/iNarrow12-89d67a613995.svg" width="40" height="40" alt="@iNarrow12" title="@iNarrow12"></a>
  <a href="https://github.com/IsaiahSHanson"><img src="src/screenshots/contributors/IsaiahSHanson-c91886c82a21.svg" width="40" height="40" alt="@IsaiahSHanson" title="@IsaiahSHanson"></a>
  <a href="https://github.com/kuau"><img src="src/screenshots/contributors/kuau-f7a628210421.svg" width="40" height="40" alt="@kuau" title="@kuau"></a>
  <a href="https://github.com/Lando0007"><img src="src/screenshots/contributors/Lando0007-055a69c9d9ec.svg" width="40" height="40" alt="@Lando0007" title="@Lando0007"></a>
  <a href="https://github.com/LilT59"><img src="src/screenshots/contributors/LilT59-71e54221db69.svg" width="40" height="40" alt="@LilT59" title="@LilT59"></a>
  <a href="https://github.com/marcosfantonio"><img src="src/screenshots/contributors/marcosfantonio-7cf4769037d2.svg" width="40" height="40" alt="@marcosfantonio" title="@marcosfantonio"></a>
  <a href="https://github.com/moulikanand12345-lang"><img src="src/screenshots/contributors/moulikanand12345-lang-10436c88ec5b.svg" width="40" height="40" alt="@moulikanand12345-lang" title="@moulikanand12345-lang"></a>
  <a href="https://github.com/nanechi"><img src="src/screenshots/contributors/nanechi-6ee8bdc66808.svg" width="40" height="40" alt="@nanechi" title="@nanechi"></a>
  <a href="https://github.com/nousernameget"><img src="src/screenshots/contributors/nousernameget-867f5abf1c6b.svg" width="40" height="40" alt="@nousernameget" title="@nousernameget"></a>
  <a href="https://github.com/OpalSand"><img src="src/screenshots/contributors/OpalSand-e851921f53a7.svg" width="40" height="40" alt="@OpalSand" title="@OpalSand"></a>
  <a href="https://github.com/P0sixSplo1t-2"><img src="src/screenshots/contributors/P0sixSplo1t-2-d399b40eaff7.svg" width="40" height="40" alt="@P0sixSplo1t-2" title="@P0sixSplo1t-2"></a>
  <a href="https://github.com/rokan00"><img src="src/screenshots/contributors/rokan00-7f822820142e.svg" width="40" height="40" alt="@rokan00" title="@rokan00"></a>
  <a href="https://github.com/RussH"><img src="src/screenshots/contributors/RussH-c209ade9c4c8.svg" width="40" height="40" alt="@RussH" title="@RussH"></a>
  <a href="https://github.com/Salkio"><img src="src/screenshots/contributors/Salkio-d253feaa8c23.svg" width="40" height="40" alt="@Salkio" title="@Salkio"></a>
  <a href="https://github.com/Shivamingale3"><img src="src/screenshots/contributors/Shivamingale3-7fd280070657.svg" width="40" height="40" alt="@Shivamingale3" title="@Shivamingale3"></a>
  <a href="https://github.com/shoko3756"><img src="src/screenshots/contributors/shoko3756-71094b9b49ef.svg" width="40" height="40" alt="@shoko3756" title="@shoko3756"></a>
  <a href="https://github.com/Sonicx9876"><img src="src/screenshots/contributors/Sonicx9876-68707df90a4e.svg" width="40" height="40" alt="@Sonicx9876" title="@Sonicx9876"></a>
  <a href="https://github.com/Tias-dev"><img src="src/screenshots/contributors/Tias-dev-73b7671b1fa4.svg" width="40" height="40" alt="@Tias-dev" title="@Tias-dev"></a>
  <a href="https://github.com/txhammer68"><img src="src/screenshots/contributors/txhammer68-5ba01c461020.svg" width="40" height="40" alt="@txhammer68" title="@txhammer68"></a>
  <a href="https://github.com/vanshdev0101"><img src="src/screenshots/contributors/vanshdev0101-c4d78aedabcb.svg" width="40" height="40" alt="@vanshdev0101" title="@vanshdev0101"></a>
  <a href="https://github.com/vialolis"><img src="src/screenshots/contributors/vialolis-53aa505d17ae.svg" width="40" height="40" alt="@vialolis" title="@vialolis"></a>
  <a href="https://github.com/Whiddu"><img src="src/screenshots/contributors/Whiddu-e0cacbd52acd.svg" width="40" height="40" alt="@Whiddu" title="@Whiddu"></a>
  <a href="https://github.com/yingmanwumen"><img src="src/screenshots/contributors/yingmanwumen-17ac0de05287.svg" width="40" height="40" alt="@yingmanwumen" title="@yingmanwumen"></a>
  <a href="https://github.com/yofriendfromschool1"><img src="src/screenshots/contributors/yofriendfromschool1-0438de7dda5b.svg" width="40" height="40" alt="@yofriendfromschool1" title="@yofriendfromschool1"></a>
  <a href="https://github.com/zhaokelei"><img src="src/screenshots/contributors/zhaokelei-c371e37c16fb.svg" width="40" height="40" alt="@zhaokelei" title="@zhaokelei"></a>
</p>

## Lizenz und Danksagungen

Unabhängiges, von macOS inspiriertes Projekt ohne Verbindung zu oder Unterstützung durch Apple oder KDE. Das Gesamtwerk steht unter [GPL-3.0](LICENSE); die Lizenzen einzelner Komponenten und Rechte Dritter gelten weiterhin. Apples Emblem, Hintergrundbilder, Klänge und SF-Schriften sind nicht durch die Projektlizenz abgedeckt. Siehe [NOTICE](NOTICE), [LICENSING.md](LICENSING.md) und [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

<details>
<summary>Ursprüngliche Danksagungen und Hinweise (Englisch)</summary>

This is an independent reimplementation inspired by the macOS aesthetic. It is not affiliated with or endorsed by Apple or KDE. "macOS" and "Apple" are trademarks of Apple Inc.

The macOS emblem, bundled wallpapers, system sounds, and SF Pro / SF Mono fonts remain Apple's property and are not covered by this project's license. Other components retain their own licenses and copyright notices; see the third-party notice index below for scope and known provenance gaps.

Licensed [GPL-3.0](LICENSE) as a whole; individual component licenses and third-party rights remain applicable. See [copyright notices](NOTICE), [licensing and project identity](LICENSING.md), and [third-party notices](THIRD_PARTY_NOTICES.md).



Project references and third-party components:

- **[EliverLara](https://github.com/EliverLara/TahoeLauncher)**: `TahoeLauncher`: Launchpad design reference.
- **[vinceliuice](https://github.com/vinceliuice)**: `MacTahoe-icon-theme`: base icons and cursors; GTK design reference. [`MacTahoe-gtk-theme` Firefox CSS/SVG](https://github.com/vinceliuice/MacTahoe-gtk-theme/tree/main/other/firefox) is maintained here as an MIT-licensed fork with profile backup and restore support.
- **[taj-ny](https://github.com/taj-ny/kwin-effects-forceblur)** and **[4v3ngR](https://github.com/4v3ngR/kwin-effects-glass)**: Better Blur and its glass fork: upstream code used by Acrylic Glass (the KWin blur authors stay credited in the source headers).
- **[luisbocanegra](https://github.com/luisbocanegra/plasma-panel-colorizer)**: `plasma-panel-colorizer` v7.3.0, bundled offline and installed by the layout step to tint the panels (GPL-3.0, license shipped alongside).
- **[Matin Lotfaliei / KDE-Rounded-Corners](https://github.com/matinlotfali/KDE-Rounded-Corners)**: the GPL-3.0 KWin rounded-window effect, fetched from the pinned v0.9.0 release and built online against the host KWin SDK (license installed alongside).
- **[ful1e5](https://github.com/ful1e5)**: `apple_cursor`: alternate cursor design reference.
- **[sahibjotsaggu](https://github.com/sahibjotsaggu)**: `San-Francisco-Pro-Fonts`: source of the SF Pro / SF Mono bundle.
- **[Lucide](https://github.com/lucide-icons/lucide)**: copy icons bundled in the global menu (ISC, © Lucide Contributors).
- **[512pixels.net](https://512pixels.net/projects/default-mac-wallpapers-in-5k/)**: high-resolution macOS wallpaper archive.

If a credit is missing, please [open an issue](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new).

</details>
