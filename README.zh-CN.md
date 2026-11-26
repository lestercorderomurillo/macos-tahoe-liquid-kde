<p align="center">
  <!-- Adapted with ImageGen from artwork by Apple: https://developer.apple.com/assets/elements/icons/macos-26/macos-26-128x128_2x.png. Tux design by Larry Ewing. -->
  <img src="src/installer/assets/glass-tux-tahoe-d9301a4b323e.png" alt="Tahoe · Glass Tux" width="180" height="180">
</p>

<h1 align="center">适用于 Linux KDE 桌面的 macOS Tahoe Shell</h1>

<p align="center">
  <a href="README.md" lang="en" hreflang="en">🇺🇸 English</a> ·
  <a href="README.es.md" lang="es" hreflang="es">🇪🇸 Español</a> ·
  <a href="README.zh-CN.md" lang="zh-CN" hreflang="zh-CN" aria-current="page">🇨🇳 简体中文</a> ·
  <a href="README.pt-BR.md" lang="pt-BR" hreflang="pt-BR">🇧🇷 Português (Brasil)</a> ·
  <a href="README.de.md" lang="de" hreflang="de">🇩🇪 Deutsch</a> ·
  <a href="README.fr.md" lang="fr" hreflang="fr">🇫🇷 Français</a> ·
  <a href="README.it.md" lang="it" hreflang="it">🇮🇹 Italiano</a> ·
  <a href="README.ja.md" lang="ja" hreflang="ja">🇯🇵 日本語</a> ·
  <a href="README.ko.md" lang="ko" hreflang="ko">🇰🇷 한국어</a> ·
  <a href="README.ru.md" lang="ru" hreflang="ru">🇷🇺 Русский</a> ·
  <a href="README.ar.md" lang="ar" hreflang="ar">🇸🇦 العربية</a> ·
  <a href="README.hi.md" lang="hi" hreflang="hi">🇮🇳 हिन्दी</a> ·
  <a href="README.nl.md" lang="nl" hreflang="nl">🇳🇱 Nederlands</a> ·
  <a href="README.pl.md" lang="pl" hreflang="pl">🇵🇱 Polski</a> ·
  <a href="README.tr.md" lang="tr" hreflang="tr">🇹🇷 Türkçe</a>
</p>

<p align="center">
  <a href="https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/releases"><img src="https://img.shields.io/github/v/release/lestercorderomurillo/macos-tahoe-liquid-kde?label=release&amp;color=blue" alt="release"></a>
  <a href="https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/workflows/test.yml"><img src="https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/workflows/test.yml/badge.svg?branch=dev" alt="tests"></a>
  <a href="https://kde.org/plasma-desktop/"><img src="https://img.shields.io/badge/Plasma-6.6%2B-1d99f3?logo=kde" alt="plasma"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-blue" alt="license"></a>
  <a href="https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new"><img src="https://img.shields.io/badge/report-a%20bug-red?logo=github" alt="report a bug"></a>
</p>


<p align="center">
  <sub>选择发行版以查看其测试状态。</sub>
</p>

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

本项目用于自定义 Linux 上 KDE 桌面的外观，不包含任何 Apple 服务，也不会连接到这些服务。如需 Apple 服务，请[直接前往 Apple 官方商店选购](https://www.apple.com/store)。

> [!CAUTION]
> **滚动发布理念**
> 实验性项目。每天接收更新。更新可能破坏兼容性。请避免用于生产系统；[在此报告问题](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new)。

> [!WARNING]
> **谨防收费的重新打包版本：本主题免费。**
>
> 如果你通过第三方渠道发现本主题，无需付费获取：直接从本仓库下载即可。我们保持项目免费，让所有人都能使用，无需付费。无需购买或订阅。

<br>

![贡献](https://img.shields.io/badge/contributing-A04B4B?style=for-the-badge&logo=github&logoColor=white)

错误报告、修复、测试和文档：参阅[贡献指南](CONTRIBUTING.md)。

Tahoe 和 Golden Gate 的代码贡献者及问题报告者：

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
  <a href="https://github.com/blaykelarue"><img src="src/screenshots/contributors/blaykelarue-2bab875307a8.svg" width="40" height="40" alt="@blaykelarue" title="@blaykelarue"></a>
  <a href="https://github.com/JacobJS34"><img src="src/screenshots/contributors/JacobJS34-cfa23b3982f4.svg" width="40" height="40" alt="@JacobJS34" title="@JacobJS34"></a>
  <a href="https://github.com/Leon-Swains"><img src="src/screenshots/contributors/Leon-Swains-4e422e08f4af.svg" width="40" height="40" alt="@Leon-Swains" title="@Leon-Swains"></a>
  <a href="https://github.com/LucipurrsDad"><img src="src/screenshots/contributors/LucipurrsDad-673ba01c9c16.svg" width="40" height="40" alt="@LucipurrsDad" title="@LucipurrsDad"></a>
  <a href="https://github.com/SinglerGold2"><img src="src/screenshots/contributors/SinglerGold2-5a612bf1fdcf.svg" width="40" height="40" alt="@SinglerGold2" title="@SinglerGold2"></a>
  <a href="https://github.com/CiderGuru"><img src="src/screenshots/contributors/CiderGuru-5d553f4b5a4d.svg" width="40" height="40" alt="@CiderGuru" title="@CiderGuru"></a>
  <a href="https://github.com/soumyadeep70"><img src="src/screenshots/contributors/soumyadeep70-627c30fbef2c.svg" width="40" height="40" alt="@soumyadeep70" title="@soumyadeep70"></a>
</p>

<br>

![功能与截图](https://img.shields.io/badge/features-%26%20screenshots-4B6B8A?style=for-the-badge&logo=kde&logoColor=white)

### 多彩 Dock

为程序坞图标选择与桌面相配的颜色。

<p align="center">
  <img src="src/screenshots/previews/tahoe-dock-7a6a63313869.gif" alt="塔霍码头显示多彩色图标在光和黑暗模式下,然后通过虹色 ⁇ 色进行自行车" width="830">
</p>

<br>

### Quickbar

从顶栏打开当前应用的菜单。

<p align="center">
  <img src="src/screenshots/previews/tahoe-quickbar-light-dark-93a568560a33.gif" alt="Quickbar · 浅色与深色模式" width="830">
</p>

<br>

### Launchpad

搜索应用，或按类别浏览。

<p align="center">
  <img src="src/screenshots/previews/tahoe-launchpad-light-dark-52685d6c5ca9.gif" alt="Launchpad · 浅色与深色模式" width="830">
</p>

<br>

### 控制中心

在同一菜单中调节无线网络、音量和亮度。

<p align="center">
  <img src="src/screenshots/previews/tahoe-control-center-light-dark-0b1436efd34c.gif" alt="控制中心 · 浅色与深色模式" width="360">
</p>

<br>

### 通知

按应用查看最近的通知。

<p align="center">
  <img src="src/screenshots/previews/tahoe-notifications-light-dark-934cf72b696e.gif" alt="通知 · 浅色与深色模式" width="620">
</p>

<br>

### Finder

在 Finder 风格的窗口中浏览文件。

<p align="center">
  <a href="src/screenshots/previews/tahoe-finder-light-dark-21d755ca3c50.gif"><img src="src/screenshots/previews/tahoe-finder-light-dark-21d755ca3c50.gif" alt="Finder · 浅色与深色模式" width="830"></a>
</p>

<br>

### 历日

点击时钟即可查看月历。

<p align="center">
  <img src="src/screenshots/previews/tahoe-calendar-light-dark-969f0fa02557.gif" alt="历日 · 浅色与深色模式" width="620">
</p>

<br>

### Bluetooth

连接已配对的设备并查看其剩余电量。

<p align="center">
  <img src="src/screenshots/previews/tahoe-bluetooth-light-dark-939d5481fd28.gif" alt="Bluetooth · 浅色与深色模式" width="620">
</p>

### Wi-Fi

查看可用网络和连接状态。

<p align="center">
  <img src="src/screenshots/previews/tahoe-wi-fi-light-dark-d3c1485cc8a2.gif" alt="Wi-Fi · 浅色与深色模式" width="328">
</p>

<br>

### 电池

查看电池电量和充电状态。

<p align="center">
  <img src="src/screenshots/previews/tahoe-battery-light-dark-9f9dc31907a4.gif" alt="电池 · 浅色与深色模式" width="620">
</p>

<br>

### 剪贴板历史记录

再次使用之前复制的文字和图片。

<p align="center">
  <img src="src/screenshots/previews/tahoe-clipboard-history-light-dark-84a04bc54fb0.gif" alt="剪贴板历史记录 · 浅色与深色模式" width="830">
</p>

<br>

### 系统信息

查看硬件、软件和主题信息。

<p align="center">
  <img src="src/screenshots/previews/tahoe-system-information-light-dark-8ab37f94d9cc.gif" alt="系统信息 · 浅色与深色模式" width="830">
</p>

<br>

### Plasma 主题

菜单和弹窗跟随浅色或深色主题。

<p align="center">
  <img src="src/screenshots/previews/tahoe-plasma-theme-light-dark-6f2816142832.gif" alt="Plasma 主题 · 浅色与深色模式" width="453">
</p>

<br>

### 启动画面

启动时显示与主题相配的画面。

<p align="center">
  <img src="src/screenshots/previews/readme-tahoe-light-boot-6d6f3b7d649e.webp" alt="普利 ⁇ 斯创业点击与进步行" width="415">
</p>

<br>

### 自适应对比度

文字颜色会随背景调整，让标签保持清晰。

<p align="center">
  <img src="src/screenshots/previews/tahoe-adaptive-contrast-off-on-442477246a8a.png" alt="自适应对比度 · Tahoe · OFF / ON" width="900">
</p>

<br>

![功能](https://img.shields.io/badge/features-6B4B8A?style=for-the-badge&logo=github&logoColor=white)

- **外观：**桌面、应用、图标和窗口装饰采用统一的浅色与深色主题，支持自动切换和为每台显示器单独设置壁纸。
- **玻璃特效：**可调节模糊、折射和色调，支持的菜单会根据背景调整文字颜色。
- **Dock：**支持固定应用、悬停放大、通知角标和隐藏设置，可随操作在不同显示器之间移动。
- **菜单栏与控制中心：**提供全局应用菜单和系统快捷控制，菜单栏设置可在不同显示器之间同步。
- **Launchpad：**提供两种布局，可搜索应用、浏览分类和收藏常用应用。
- **桌面小部件：**可将 Liquid Glass 小部件直接添加到桌面。
- **通知：**玻璃风格的通知横幅和分组历史记录，在应用支持时可使用快捷操作和回复。
- **剪贴板历史：**查找并重复使用复制过的文字和图片，也可以固定想保留的条目。
- **应用集成：**Nautilus 提供 Finder 风格的文件浏览体验，并支持 GTK 菜单集成和带配置备份的 Firefox 主题。
- **系统信息与启动：**主题化的系统信息窗口和可选的配套启动画面。
- **安装与恢复：**图形化安装程序随附主题资源，支持更新和设置备份，可在卸载时恢复设置。
- **语言：** 可在设置中选择安装程序的语言。Plasma 小部件使用桌面的语言。
- **兼容性：**支持基于 Arch 或 Fedora 的系统以及 openSUSE、Debian 和 KDE neon 上的 Plasma 6.6–6.8。
- **可选功能：**OLED 屏幕保护，以及对 NixOS 和 Home Manager 的实验性支持。

<br>

![入门](https://img.shields.io/badge/getting-started-3B7B5B?style=for-the-badge&logo=gnubash&logoColor=white)

下载并打开安装程序：

```bash
git clone --filter=blob:none https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde.git
cd macos-tahoe-liquid-kde
./installer
```

选择 **Express** 进行安装。再次打开 `./installer` 即可更新或卸载。

释放磁盘空间并保留 Git 工作副本和本地工作：

```bash
./installer --free-space
```

| 安装程序语言 | 状态 |
| --- | --- |
| 🇺🇸 英语 | ![可用](https://img.shields.io/badge/Available-1A7F37) |
| 🇪🇸 西班牙语 | ![可用](https://img.shields.io/badge/Available-1A7F37) |
| 🇨🇳 简体中文 | ![可用](https://img.shields.io/badge/Available-1A7F37) |
| 🇧🇷 巴西葡萄牙语 | ![可用](https://img.shields.io/badge/Available-1A7F37) |
| 🇩🇪 德语 | ![可用](https://img.shields.io/badge/Available-1A7F37) |
| 🇫🇷 法语 | ![可用](https://img.shields.io/badge/Available-1A7F37) |
| 🇮🇹 意大利语 | ![可用](https://img.shields.io/badge/Available-1A7F37) |
| 🇷🇺 俄语 | ![可用](https://img.shields.io/badge/Available-1A7F37) |
| 🇯🇵 日语 | ![可用](https://img.shields.io/badge/Available-1A7F37) |
| 🇰🇷 韩语 | ![可用](https://img.shields.io/badge/Available-1A7F37) |
| 🇸🇦 阿拉伯语 | ![可用](https://img.shields.io/badge/Available-1A7F37) |
| 🇮🇳 印地语 | ![可用](https://img.shields.io/badge/Available-1A7F37) |
| 🇳🇱 荷兰语 | ![可用](https://img.shields.io/badge/Available-1A7F37) |
| 🇵🇱 波兰语 | ![可用](https://img.shields.io/badge/Available-1A7F37) |
| 🇹🇷 土耳其语 | ![可用](https://img.shields.io/badge/Available-1A7F37) |

<details>
<summary><b>系统要求</b></summary>

所需的桌面环境、构建工具和系统软件包。

- KDE Plasma 6.6+
- Python 3.10+ 和 PyQt6
- `sudo`
- Qt 6 开发工具
- 用于编译型 Plasma 组件和 KWin 特效的 KDE 与 Qt 6 开发包
- `cmake`, `g++`，以及 `pkg-config`（选择编译功能时）
- `dbus-send`
- `systemctl` 或 `crontab`（用于计划功能）

**dinit：**安装程序检测 dinit，并使用用户 cron 条目进行自动浅色/深色切换和 OLED 保护。需要运行中的 cron 守护进程；仅安装 `crontab` 不会启动它。在 Artix/dinit 上，使用以下命令准备：

```bash
sudo pacman -S --needed cronie cronie-dinit
sudo dinitctl --system enable cronie
```

自动切换在登录期间的 06:00 和 18:00 执行；cron 后端不会在登录时补执行。手动浅色/深色切换不依赖 cron。dinit 桌面验证尚未完成；现有 Artix 截图覆盖 OpenRC。

资源已随附。缺失的依赖和可选的 KDE Rounded Corners 需要网络连接。经过验证的 Rounded Corners 更新会删除旧的下载源码和压缩包。重新安装会原位替换受管理的资源目录树；成功复制后会清除临时数据，后续复制会清理中断的一次性暂存数据。恢复备份、浏览器配置备份和用户偏好将保留。开发用虚拟机镜像和截图包不是安装程序缓存，绝不会自动删除。

| 发行版 | Qt 6 工具 | KDE Plasma 6 开发包 |
|--------|------------|-----------------------------------|
| Arch 系列 | `pacman -S qt6-tools` | `pacman -S extra-cmake-modules plasma-workspace kdecoration libplasma libnotificationmanager libksysguard plasma-activities-stats` |
| Fedora 系列 | `dnf install qt6-qttools-devel` | `dnf install extra-cmake-modules plasma-workspace-devel kdecoration-devel libplasma-devel knotifications-devel libksysguard-devel kf6-plasma-activities-devel` |
| openSUSE Tumbleweed | `zypper install qt6-tools-devel` | `zypper install extra-cmake-modules plasma6-workspace-devel kdecoration-devel libKF6Plasma-devel libnotificationmanager6-devel libksysguard6-devel libKF6PlasmaActivitiesStats6-devel` |

</details>

<details>
<summary><b>OLED 保护</b></summary>

可选的面板位移；默认关闭。

在 **OLED 保护** 页面启用。在此选择位移间隔和最大像素位移；默认关闭。

**手动控制**

```bash
mac-tahoe-oled-care shift
mac-tahoe-oled-care restore
mac-tahoe-oled-care status
```

</details>

<br>

![兼容性](https://img.shields.io/badge/compatibility-system%20support-4B6B8A?style=for-the-badge&logo=linux&logoColor=white)

检查你的发行版、初始化系统和 Plasma 版本的支持情况。

<details>
<summary><b>发行版测试</b></summary>

在隔离的 Plasma 桌面中试用主题。

```bash
./vm <os>
```

**OS:** `cachyos` · `arch` · `manjaro` · `endeavouros` · `garuda` · `fedora` · `nobara` · `opensuse` · `neon` · `debian` · `artix` · `kubuntu`

`all` 启动所有发行版。云镜像目标会自动配置；其他目标使用以校验和固定的官方 ISO 安装程序。参阅[虚拟机设置与验证指南](tests/vm/README.md)。

`./vm kubuntu` 启动官方 Kubuntu 26.04.1 LTS ISO 并验证 SHA-256（配置来宾后，SSH 端口为 `2234`）。此新增启动器回归测试目标尚待完整的实际运行验证。

`./vm debian` 使用官方 Debian testing（Forky）云镜像，验证 SHA-512 校验和并配置 Plasma 桌面。以 `tester` 登录，密码为 `tester`；SSH 位于 `127.0.0.1:2232`。安装程序从来宾内可写副本 `/home/tester/macos-tahoe-liquid-kde` 打开；宿主仓库以只读方式挂载。使用 `./vm debian --clean` 从头重建一次性来宾。

此表中的全部 11 个发行版均通过实际虚拟机验证。选择状态徽章以查看已审阅截图和测试结果。

| | 名称 | 状态 |
|:--:|------|---------|
| <img src="https://cdn.simpleicons.org/cachyos" alt="CachyOS" width="22"> | CachyOS | [![虚拟机已验证](https://img.shields.io/badge/VM%20verified-1A7F37)](tests/vm/PROOF.md#cachyos) |
| <img src="https://cdn.simpleicons.org/archlinux" alt="Arch Linux" width="22"> | Arch Linux | [![虚拟机已验证](https://img.shields.io/badge/VM%20verified-1A7F37)](tests/vm/PROOF.md#arch) |
| <img src="https://cdn.simpleicons.org/endeavouros" alt="EndeavourOS" width="22"> | EndeavourOS | [![虚拟机已验证](https://img.shields.io/badge/VM%20verified-1A7F37)](tests/vm/PROOF.md#endeavouros) |
| <img src="https://cdn.simpleicons.org/fedora" alt="Fedora" width="22"> | Fedora | [![虚拟机已验证](https://img.shields.io/badge/VM%20verified-1A7F37)](tests/vm/PROOF.md#fedora) |
| <img src="https://cdn.simpleicons.org/manjaro" alt="Manjaro" width="22"> | Manjaro | [![虚拟机已验证](https://img.shields.io/badge/VM%20verified-1A7F37)](tests/vm/PROOF.md#manjaro) |
| <img src="https://cdn.simpleicons.org/linux" alt="Linux" width="22"> | Artix Linux (OpenRC) | [![虚拟机已验证](https://img.shields.io/badge/VM%20verified-1A7F37)](tests/vm/PROOF.md#artix) |
| <img src="https://cdn.simpleicons.org/linux" alt="Linux" width="22"> | Garuda Linux | [![虚拟机已验证](https://img.shields.io/badge/VM%20verified-1A7F37)](tests/vm/PROOF.md#garuda) |
| <img src="https://cdn.simpleicons.org/nobaralinux" alt="Nobara" width="22"> | Nobara | [![虚拟机已验证](https://img.shields.io/badge/VM%20verified-1A7F37)](tests/vm/PROOF.md#nobara) |
| <img src="https://cdn.simpleicons.org/opensuse" alt="openSUSE" width="22"> | openSUSE Tumbleweed | [![虚拟机已验证](https://img.shields.io/badge/VM%20verified-1A7F37)](tests/vm/PROOF.md#opensuse) |
| <img src="https://cdn.simpleicons.org/kde" alt="KDE" width="22"> | KDE neon | [![虚拟机已验证](https://img.shields.io/badge/VM%20verified-1A7F37)](tests/vm/PROOF.md#neon) |
| <img src="https://cdn.simpleicons.org/debian" alt="Debian" width="22"> | Debian testing / sid (Plasma 6.6+) | [![虚拟机已验证](https://img.shields.io/badge/VM%20verified-1A7F37)](tests/vm/PROOF.md#debian) |

**NixOS 和 Home Manager（测试中）**

使用 flake 模块，**不要使用图形安装程序**。实际桌面验证尚未完成。

**Flake 输入**（需要 Nixpkgs 和 Home Manager）：

```nix
inputs.mac-tahoe = {
  url = "github:lestercorderomurillo/macos-tahoe-liquid-kde/v0.55.2";
  inputs.nixpkgs.follows = "nixpkgs";
  inputs.home-manager.follows = "home-manager";
};
```

**NixOS：**导入 `inputs.mac-tahoe.nixosModules.default`。

```nix
services.desktopManager.plasma6.enable = true;
services.mac-tahoe.enable = true;
# services.mac-tahoe.plymouth.enable = true; # optional boot splash
```

**Home Manager：**导入 `inputs.mac-tahoe.homeManagerModules.default`。

```nix
programs.mac-tahoe = {
  enable = true;
  mode = "auto"; # or "light" / "dark"
  # appleAssets = true;
  # oledCare.enable = true;
};
```

**Apple 资源：**可选的非自由字体、壁纸和声音。启用 `appleAssets` 还需要：

```nix
nixpkgs.config.allowUnfreePredicate = pkg:
  builtins.elem (lib.getName pkg) [ "mac-tahoe-apple-assets" ];
```

**面板：**还需导入你自己的 plasma-manager 模块及 `inputs.mac-tahoe.homeManagerModules.plasma-manager`。启用 `programs.mac-tahoe.panels.enable` 并设置 `programs.mac-tahoe.panels.launchers`，例如 `[ "applications:org.kde.dolphin.desktop" ]`。这会替换布局，不会导入现有固定项目。

**可写设置：**保持 `kdeglobals`、`kwinrc`、`plasmarc`、`plasmashellrc`、`kcminputrc`、`plasma-org.kde.plasma.desktop-appletsrc`、`Kvantum/kvantum.kvconfig` 和当前 GTK 配置可写。避免将主题切换器管理的 plasma-manager 键设为不可变。

激活后请注销并重新登录。不会配置 Firefox 配置文件、GTK 书签和 SDDM。GTK 全局菜单需要 `programs.mac-tahoe.gtkAppmenuModule`。关闭 OLED 保护前，运行 `mac-tahoe-oled-care restore`；移除模块前，选择 Breeze。移除操作会保留用户设置。

</details>

<details>
<summary><b>初始化系统</b></summary>

自动主题切换和 OLED 保护使用以下调度后端：

| 初始化系统 | 调度 | 已记录测试 |
| --- | --- | --- |
| systemd | 用户定时器 | ![桌面虚拟机已验证](https://img.shields.io/badge/Desktop%20VM%20verified-1A7F37) |
| OpenRC | 用户 cron | ![Artix 桌面虚拟机已验证](https://img.shields.io/badge/Artix%20desktop%20VM%20verified-1A7F37) |
| dinit | 用户 cron | ![调度已验证](https://img.shields.io/badge/Scheduling%20verified-1A7F37) ![桌面虚拟机测试待完成](https://img.shields.io/badge/Desktop%20VM%20testing%20pending-D4A017) |

OpenRC 和 dinit 需要运行中的 cron 守护进程。
[桌面测试结果](tests/vm/PROOF.md) · [dinit 调度检查](CONTRIBUTING.md#setup)。

</details>

<details>
<summary><b>Plasma 版本</b></summary>

支持 Plasma 6.6–6.8；编译特效使用宿主 SDK。

| Plasma | 支持 | 起始版本 |
|--------|---------|-------|
| 6.5 及更早版本 | ![不支持](https://img.shields.io/badge/Not%20supported-D1242F) | 不适用 |
| 6.6 | ![支持](https://img.shields.io/badge/Supported-1A7F37) | v0.1.0 |
| 6.7 | ![支持](https://img.shields.io/badge/Supported-1A7F37) | v0.19.0 |
| 6.8 | ![支持](https://img.shields.io/badge/Supported-1A7F37) | v0.54.1 |

</details>

<br>

![免责声明](https://img.shields.io/badge/disclaimer-not%20affiliated%20with%20apple-6B6B6B?style=for-the-badge&logo=apple&logoColor=white)

这是受 macOS 美学启发的独立重新实现。与 Apple 或 KDE 无关联，也未获其背书。“macOS”和“Apple”是 Apple Inc. 的商标。

macOS 徽标、随附壁纸、系统声音及 SF Pro / SF Mono 字体仍属于 Apple，不受本项目许可证覆盖。其他组件保留各自许可证和版权声明；有关范围及已知来源缺口，请参阅下方第三方声明索引。

整体以 [GPL-3.0](LICENSE) 授权；各组件许可证和第三方权利仍适用。请参阅[版权声明](NOTICE)、[许可与项目身份](LICENSING.md)及[第三方声明](THIRD_PARTY_NOTICES.md)。

<br>

![致谢与灵感](https://img.shields.io/badge/credits-%26%20inspiration-8A6B4B?style=for-the-badge&logo=apple&logoColor=white)

<details>
<summary><b>项目、资源与致谢</b></summary>

项目参考与第三方组件：

- **[EliverLara](https://github.com/EliverLara/TahoeLauncher)**: `TahoeLauncher`: Launchpad 设计参考。
- **[vinceliuice](https://github.com/vinceliuice)**: `MacTahoe-icon-theme`: 基础图标和光标；GTK 设计参考。 [`MacTahoe-gtk-theme` Firefox CSS/SVG](https://github.com/vinceliuice/MacTahoe-gtk-theme/tree/main/other/firefox) 在此作为 MIT 许可的分支维护，支持配置备份和恢复。
- **[taj-ny](https://github.com/taj-ny/kwin-effects-forceblur)** 和 **[4v3ngR](https://github.com/4v3ngR/kwin-effects-glass)**: Better Blur 及其玻璃分支：Acrylic Glass 使用的上游代码（KWin 模糊效果作者的署名保留在源码头部）。
- **[luisbocanegra](https://github.com/luisbocanegra/plasma-panel-colorizer)**: `plasma-panel-colorizer` v7.3.0，离线随附并由布局步骤安装，用于为面板着色（GPL-3.0，附带许可证）。
- **[jaxparrow07](https://github.com/jaxparrow07/liquidglass-kde-widgets)**：`liquidglass-kde-widgets` 提供主题随附的 Liquid Glass 桌面小部件套件（GPL-3.0，附带许可证）。
- **[RoxasYTB](https://github.com/RoxasYTB)**：[照片小部件](https://github.com/jaxparrow07/liquidglass-kde-widgets/pull/41)可在桌面上显示照片。[Solid/Glass 样式自动切换](https://github.com/jaxparrow07/liquidglass-kde-widgets/pull/40)会在屏幕上有窗口打开时启用 Glass 样式。
- **[Matin Lotfaliei / KDE-Rounded-Corners](https://github.com/matinlotfali/KDE-Rounded-Corners)**: GPL-3.0 许可的 KWin 窗口圆角特效，从固定的 v0.9.0 版本获取并在线基于宿主 KWin SDK 构建（同时安装许可证）。
- **[ful1e5](https://github.com/ful1e5)**: `apple_cursor`: 替代光标设计参考。
- **[sahibjotsaggu](https://github.com/sahibjotsaggu)**: `San-Francisco-Pro-Fonts`: SF Pro / SF Mono 包的来源。
- **[Lucide](https://github.com/lucide-icons/lucide)**: 全局菜单随附的复制图标（ISC，© Lucide Contributors）。
- **[512pixels.net](https://512pixels.net/projects/default-mac-wallpapers-in-5k/)**: 高分辨率 macOS 壁纸档案。

如果遗漏了致谢，请[提交问题](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new)。

</details>


[安装程序截图与测试](TESTING.md)。
