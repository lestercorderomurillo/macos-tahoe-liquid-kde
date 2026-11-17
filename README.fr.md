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
  <a href="README.de.md" lang="de" hreflang="de">🇩🇪 Deutsch</a> ·
  <a href="README.fr.md" lang="fr" hreflang="fr" aria-current="page">🇫🇷 Français</a>
</p>

<p align="center">
  <a href="https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/releases"><img src="https://img.shields.io/github/v/release/lestercorderomurillo/macos-tahoe-liquid-kde?label=release&amp;color=blue" alt="release"></a>
  <a href="https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/workflows/test.yml"><img src="https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/workflows/test.yml/badge.svg?branch=dev" alt="tests"></a>
  <a href="https://kde.org/plasma-desktop/"><img src="https://img.shields.io/badge/Plasma-6.6%2B-1d99f3?logo=kde" alt="plasma"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-blue" alt="license"></a>
  <a href="https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new"><img src="https://img.shields.io/badge/report-a%20bug-red?logo=github" alt="report a bug"></a>
</p>

<p align="center">Le style macOS Tahoe pour KDE Plasma 6.6, 6.7 et 6.8+.</p>

> [!CAUTION]
> Projet expérimental avec des mises à jour fréquentes pouvant rompre la compatibilité. Évitez les systèmes de production. Ce projet est gratuit : aucun achat ni abonnement n’est nécessaire.

<p align="center"><sub>Sélectionnez une distribution pour consulter ses tests.</sub></p>

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

## Installation et mises à jour

Téléchargez le dépôt et ouvrez l’installateur :

```bash
git clone --filter=blob:none https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde.git
cd macos-tahoe-liquid-kde
./installer
```

Choisissez **Express** pour installer. Rouvrez `./installer` pour mettre à jour ou désinstaller.

Cette édition utilise Tahoe, son fond d’écran et le préréglage 1 du lanceur. Vous pouvez modifier les options dans l’assistant.

L’installateur est disponible en anglais, espagnol, chinois simplifié, portugais du Brésil, allemand et français. Les langues prévues figurent dans l’[état complet](README.md).

## Prérequis et compatibilité

KDE Plasma 6.6 ou ultérieur, Python 3.10+, PyQt6, `sudo` et les outils de développement Qt 6/KDE sont nécessaires. Les composants compilés nécessitent `cmake`, `g++` et `pkg-config`. Les téléchargements, les dépendances manquantes et KDE Rounded Corners nécessitent internet.

Plasma 6.6–6.8 est pris en charge ; les versions 6.5 et antérieures ne le sont pas. Les effets natifs sont compilés contre Qt et KWin du système. Onze distributions ont été testées en machine virtuelle : CachyOS, Arch, EndeavourOS, Fedora, Manjaro, Artix/OpenRC, Garuda, Nobara, openSUSE Tumbleweed, KDE neon et Debian testing/sid. Cela ne couvre pas toutes les configurations.

Le changement automatique clair/sombre et la protection OLED utilisent des minuteries utilisateur systemd ou cron par utilisateur avec OpenRC/dinit. OpenRC et dinit nécessitent un démon cron actif. La validation du bureau dinit et de Kubuntu reste en attente ; les photographies Artix correspondent à OpenRC.

## Fonctionnalités et photographies

### Tahoe Finder (Alpha)

Navigation de fichiers de style Finder avec le verre Tahoe.

<p align="center">
  <a href="src/screenshots/previews/readme-tahoe-light-finder-4203d60bcd59.webp"><img src="src/screenshots/previews/readme-tahoe-light-finder-4203d60bcd59.webp" alt="Tahoe Finder · Clair" width="415"></a>
  <a href="src/screenshots/previews/readme-tahoe-dark-finder-3fba4166a2d8.webp"><img src="src/screenshots/previews/readme-tahoe-dark-finder-3fba4166a2d8.webp" alt="Tahoe Finder · Sombre" width="415"></a>
</p>

<details>
<summary>Accents rouges et bleus en modes clair et sombre</summary>

<table>
<tr><th>Accent</th><th>Clair</th><th>Sombre</th></tr>
<tr><td>Rouge</td><td><a href="src/screenshots/previews/readme-tahoe-light-finder-red-cf60519353bc.webp"><img src="src/screenshots/previews/readme-tahoe-light-finder-red-cf60519353bc.webp" alt="Tahoe Finder · Clair" width="415"></a></td><td><a href="src/screenshots/previews/readme-tahoe-dark-finder-red-a5d3144faf0f.webp"><img src="src/screenshots/previews/readme-tahoe-dark-finder-red-a5d3144faf0f.webp" alt="Tahoe Finder · Sombre" width="415"></a></td></tr>
<tr><td>Bleu</td><td><a href="src/screenshots/previews/readme-tahoe-light-finder-blue-ad74eeb6e7a1.webp"><img src="src/screenshots/previews/readme-tahoe-light-finder-blue-ad74eeb6e7a1.webp" alt="Tahoe Finder · Clair" width="415"></a></td><td><a href="src/screenshots/previews/readme-tahoe-dark-finder-blue-2a9bacc3b9a9.webp"><img src="src/screenshots/previews/readme-tahoe-dark-finder-blue-2a9bacc3b9a9.webp" alt="Tahoe Finder · Sombre" width="415"></a></td></tr>
</table>

</details>

### Tahoe Launchpad (Alpha)

Recherchez des applications, parcourez les catégories et gardez vos favoris. Deux préréglages sont disponibles.

<p align="center">
  <img src="src/screenshots/previews/readme-tahoe-light-launcher-95744cf7a341.webp" alt="Tahoe Launchpad · Clair" width="415">
  <img src="src/screenshots/previews/readme-tahoe-dark-launcher-2399734a1625.webp" alt="Tahoe Launchpad · Sombre" width="415">
</p>

### Tahoe Dock (Alpha)

Réfraction du verre, agrandissement au survol, compteurs de notifications et masquage automatique.

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-regular-6d506b3465fd.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-regular-6d506b3465fd.webp" alt="Tahoe Dock · Clair" width="415"></a><br>Standard · Clair</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-regular-9254e2db86a7.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-regular-9254e2db86a7.webp" alt="Tahoe Dock · Sombre" width="415"></a><br>Standard · Sombre</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-clear-843c40a052a7.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-clear-843c40a052a7.webp" alt="Tahoe Dock · Clair" width="415"></a><br>Transparent · Clair</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-clear-58edd6d52e38.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-clear-58edd6d52e38.webp" alt="Tahoe Dock · Sombre" width="415"></a><br>Transparent · Sombre</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-blue-d39bb78e2f1d.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-blue-d39bb78e2f1d.webp" alt="Tahoe Dock · Clair" width="415"></a><br>Bleu · Clair</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-blue-a292ebe93f08.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-blue-a292ebe93f08.webp" alt="Tahoe Dock · Sombre" width="415"></a><br>Bleu · Sombre</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-purple-b8d6d4a59d58.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-purple-b8d6d4a59d58.webp" alt="Tahoe Dock · Clair" width="415"></a><br>Violet · Clair</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-purple-090970372f80.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-purple-090970372f80.webp" alt="Tahoe Dock · Sombre" width="415"></a><br>Violet · Sombre</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-pink-c0b0ba00ddeb.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-pink-c0b0ba00ddeb.webp" alt="Tahoe Dock · Clair" width="415"></a><br>Rose · Clair</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-pink-ba6941817529.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-pink-ba6941817529.webp" alt="Tahoe Dock · Sombre" width="415"></a><br>Rose · Sombre</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-red-19adb9d798fd.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-red-19adb9d798fd.webp" alt="Tahoe Dock · Clair" width="415"></a><br>Rouge · Clair</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-red-379c09615f96.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-red-379c09615f96.webp" alt="Tahoe Dock · Sombre" width="415"></a><br>Rouge · Sombre</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-orange-18c4663ce547.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-orange-18c4663ce547.webp" alt="Tahoe Dock · Clair" width="415"></a><br>Orange · Clair</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-orange-5079b478c649.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-orange-5079b478c649.webp" alt="Tahoe Dock · Sombre" width="415"></a><br>Orange · Sombre</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-yellow-c7656eaf2b61.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-yellow-c7656eaf2b61.webp" alt="Tahoe Dock · Clair" width="415"></a><br>Jaune · Clair</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-yellow-c1945efddc21.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-yellow-c1945efddc21.webp" alt="Tahoe Dock · Sombre" width="415"></a><br>Jaune · Sombre</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-green-ac9611249165.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-green-ac9611249165.webp" alt="Tahoe Dock · Clair" width="415"></a><br>Vert · Clair</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-green-84eab2e65cf2.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-green-84eab2e65cf2.webp" alt="Tahoe Dock · Sombre" width="415"></a><br>Vert · Sombre</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-gray-18617e5c0df8.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-gray-18617e5c0df8.webp" alt="Tahoe Dock · Clair" width="415"></a><br>Gris · Clair</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-gray-e7baf051c7cb.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-gray-e7baf051c7cb.webp" alt="Tahoe Dock · Sombre" width="415"></a><br>Gris · Sombre</p>

### Tahoe Shell (Alpha)

Accès aux réglages système, aux applications et aux commandes de session.

<p align="center">
  <img src="src/screenshots/previews/readme-tahoe-light-menu-a8579c6bdc3c.webp" alt="Tahoe Shell · Clair" width="415">
  <img src="src/screenshots/previews/readme-tahoe-dark-menu-01a3a4305740.webp" alt="Tahoe Shell · Sombre" width="415">
</p>

### Tahoe Centre de contrôle (Alpha)

Wi-Fi, son, luminosité et notifications dans un menu en verre.

<p align="center">
  <img src="src/screenshots/previews/readme-tahoe-light-control-f093af128a34.webp" alt="Tahoe Centre de contrôle · Clair" width="415">
  <img src="src/screenshots/previews/readme-tahoe-dark-control-3a039c914a10.webp" alt="Tahoe Centre de contrôle · Sombre" width="415">
</p>

### Tahoe Historique du presse-papiers (Alpha)

Retrouvez et réutilisez le texte et les images copiés depuis Launchpad.

<p align="center">
  <img src="src/screenshots/previews/readme-tahoe-light-clipboard-e0cf55fa87a4.webp" alt="Tahoe Historique du presse-papiers · Clair" width="415">
  <img src="src/screenshots/previews/readme-tahoe-dark-clipboard-024174b100b7.webp" alt="Tahoe Historique du presse-papiers · Sombre" width="415">
</p>

### Tahoe Informations système

Informations sur votre matériel, vos logiciels et votre thème.

<p align="center">
  <img src="src/screenshots/previews/readme-tahoe-light-about-2a83d687da3f.webp" alt="Tahoe Informations système · Clair" width="415">
  <img src="src/screenshots/previews/readme-tahoe-dark-about-c6bf5138a206.webp" alt="Tahoe Informations système · Sombre" width="415">
</p>

### Tahoe Thème Plasma (Alpha)

Menus et fenêtres contextuelles translucides avec des couleurs claires et sombres coordonnées.

<p align="center">
  <img src="src/screenshots/previews/readme-tahoe-light-context-a94e322fac42.webp" alt="Tahoe Thème Plasma · Clair" width="415">
  <img src="src/screenshots/previews/readme-tahoe-dark-context-359afa6d3a32.webp" alt="Tahoe Thème Plasma · Sombre" width="415">
</p>

### Tahoe Écran de démarrage (Alpha)

Écran de démarrage avec déverrouillage intégré des disques chiffrés LUKS2.

<p align="center">
  <img src="src/screenshots/previews/readme-tahoe-light-boot-959163f469f4.webp" alt="Tahoe Écran de démarrage" width="415">
</p>

## Options et outils

L’assistant permet de choisir les composants, icônes, fonds d’écran, boutons et ombres des fenêtres. La réinstallation conserve la personnalisation du Dock sauf si vous demandez sa réinitialisation. Le thème synchronise l’apparence claire/sombre, intègre les menus globaux et les styles GTK/Qt et sauvegarde les profils Firefox avant de les modifier.

La protection OLED est facultative et désactivée par défaut. Activez-la dans l’assistant et choisissez l’intervalle et le décalage maximal. Commandes manuelles :

```bash
mac-tahoe-oled-care shift
mac-tahoe-oled-care restore
mac-tahoe-oled-care status
```

Pour tester dans un bureau isolé, utilisez `./vm <os>`. Consultez le [guide des machines virtuelles](tests/vm/README.md). La validation complète de Kubuntu reste en attente. NixOS et Home Manager sont expérimentaux : utilisez les modules flake, pas l’installateur graphique ; consultez la [configuration détaillée en anglais](README.md).

Le [guide de contribution](CONTRIBUTING.md) décrit la configuration avancée et le générateur d’icônes partagé. Lancez `./icon-toolset` depuis Tahoe pour générer, prévisualiser et vérifier les icônes des deux éditions sans appliquer le thème au bureau. Pour libérer de l’espace Git en conservant le travail local : `./installer --free-space`.

Consultez les [résultats et limites des tests](tests/vm/PROOF.md) et les [photographies de l’installateur](TESTING.md). Les photographies conservent leur provenance originale ; elles ne constituent pas une nouvelle validation de chaque version.

[Référence technique complète et état des composants (anglais)](README.md)

## Contributions et bogues

[Signalez les bogues](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new) en indiquant la version de Plasma (`plasmashell --version`), la distribution, la version du thème et une capture ou vidéo pour les problèmes visuels. Consultez le [guide de contribution](CONTRIBUTING.md).

Contributeurs au code et personnes ayant signalé des bogues dans Tahoe et Golden Gate :

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

## Licence et crédits

Projet indépendant inspiré de macOS, sans affiliation ni approbation d’Apple ou de KDE. L’ensemble est distribué sous [GPL-3.0](LICENSE) ; les licences de chaque composant et les droits des tiers restent applicables. L’emblème, les fonds d’écran, les sons et les polices SF d’Apple ne sont pas couverts par la licence du projet. Consultez [NOTICE](NOTICE), [LICENSING.md](LICENSING.md) et [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

<details>
<summary>Crédits et avis originaux (anglais)</summary>

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
