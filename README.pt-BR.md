<p align="center">
  <!-- Artwork: https://developer.apple.com/assets/elements/icons/macos-26/macos-26-128x128_2x.png -->
  <img src="src/screenshots/macos-26.png" alt="macOS 26 circular emblem" width="180" height="180">
</p>

<h1 align="center">macOS Tahoe for KDE Plasma</h1>

<p align="center">
  <a href="README.md" lang="en" hreflang="en">🇺🇸 English</a> ·
  <a href="README.es.md" lang="es" hreflang="es">🇪🇸 Español</a> ·
  <a href="README.zh-CN.md" lang="zh-CN" hreflang="zh-CN">🇨🇳 简体中文</a> ·
  <a href="README.pt-BR.md" lang="pt-BR" hreflang="pt-BR" aria-current="page">🇧🇷 Português (Brasil)</a> ·
  <a href="README.de.md" lang="de" hreflang="de">🇩🇪 Deutsch</a> ·
  <a href="README.fr.md" lang="fr" hreflang="fr">🇫🇷 Français</a>
</p>

<p align="center">
  <a href="https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/releases"><img src="https://img.shields.io/github/v/release/lestercorderomurillo/macos-tahoe-liquid-kde?label=release&amp;color=blue" alt="release"></a>
  <a href="https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/workflows/test.yml"><img src="https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/actions/workflows/test.yml/badge.svg?branch=dev" alt="tests"></a>
  <a href="https://kde.org/plasma-desktop/"><img src="https://img.shields.io/badge/Plasma-6.6%2B-1d99f3?logo=kde" alt="plasma"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-blue" alt="license"></a>
  <a href="https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new"><img src="https://img.shields.io/badge/report-a%20bug-red?logo=github" alt="report a bug"></a>
</p>

<p align="center">Estilo macOS Tahoe para KDE Plasma 6.6, 6.7 e 6.8+.</p>

> [!CAUTION]
> Projeto experimental com atualizações frequentes que podem quebrar a compatibilidade. Evite sistemas de produção. Este projeto é gratuito: não exige compra nem assinatura.

<p align="center"><sub>Selecione uma distribuição para consultar seus testes.</sub></p>

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

## Instalação e atualizações

Baixe o repositório e abra o instalador:

```bash
git clone --filter=blob:none https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde.git
cd macos-tahoe-liquid-kde
./installer
```

Escolha **Express** para instalar. Abra `./installer` novamente para atualizar ou desinstalar.

Esta edição usa Tahoe, seu papel de parede e o preajuste 1 do lançador. Você pode alterar as opções no assistente.

O instalador está disponível em inglês, espanhol, chinês simplificado, português do Brasil, alemão e francês. Os idiomas planejados aparecem no [estado completo](README.md).

## Requisitos e compatibilidade

São necessários KDE Plasma 6.6 ou superior, Python 3.10+, PyQt6, `sudo` e ferramentas de desenvolvimento Qt 6/KDE. Os componentes compilados precisam de `cmake`, `g++` e `pkg-config`. Downloads, dependências ausentes e KDE Rounded Corners exigem internet.

Plasma 6.6–6.8 é compatível; versões 6.5 e anteriores não são. Os efeitos nativos são compilados com o Qt e KWin do sistema. Onze distribuições passaram por testes em máquinas virtuais: CachyOS, Arch, EndeavourOS, Fedora, Manjaro, Artix/OpenRC, Garuda, Nobara, openSUSE Tumbleweed, KDE neon e Debian testing/sid. Isso não cobre todas as configurações.

A troca automática claro/escuro e a proteção OLED usam temporizadores de usuário systemd ou cron por usuário com OpenRC/dinit. OpenRC e dinit precisam de um daemon cron ativo. A validação do ambiente dinit e do Kubuntu continua pendente; as fotografias do Artix correspondem ao OpenRC.

## Recursos e fotografias

### Tahoe Finder (Alpha)

Navegação de arquivos no estilo Finder com o vidro Tahoe.

<p align="center">
  <a href="src/screenshots/previews/readme-tahoe-light-finder-4203d60bcd59.webp"><img src="src/screenshots/previews/readme-tahoe-light-finder-4203d60bcd59.webp" alt="Tahoe Finder · Claro" width="415"></a>
  <a href="src/screenshots/previews/readme-tahoe-dark-finder-3fba4166a2d8.webp"><img src="src/screenshots/previews/readme-tahoe-dark-finder-3fba4166a2d8.webp" alt="Tahoe Finder · Escuro" width="415"></a>
</p>

<details>
<summary>Destaques vermelhos e azuis nos modos claro e escuro</summary>

<table>
<tr><th>Destaque</th><th>Claro</th><th>Escuro</th></tr>
<tr><td>Vermelho</td><td><a href="src/screenshots/previews/readme-tahoe-light-finder-red-cf60519353bc.webp"><img src="src/screenshots/previews/readme-tahoe-light-finder-red-cf60519353bc.webp" alt="Tahoe Finder · Claro" width="415"></a></td><td><a href="src/screenshots/previews/readme-tahoe-dark-finder-red-a5d3144faf0f.webp"><img src="src/screenshots/previews/readme-tahoe-dark-finder-red-a5d3144faf0f.webp" alt="Tahoe Finder · Escuro" width="415"></a></td></tr>
<tr><td>Azul</td><td><a href="src/screenshots/previews/readme-tahoe-light-finder-blue-ad74eeb6e7a1.webp"><img src="src/screenshots/previews/readme-tahoe-light-finder-blue-ad74eeb6e7a1.webp" alt="Tahoe Finder · Claro" width="415"></a></td><td><a href="src/screenshots/previews/readme-tahoe-dark-finder-blue-2a9bacc3b9a9.webp"><img src="src/screenshots/previews/readme-tahoe-dark-finder-blue-2a9bacc3b9a9.webp" alt="Tahoe Finder · Escuro" width="415"></a></td></tr>
</table>

</details>

### Tahoe Launchpad (Alpha)

Encontre aplicativos, navegue pelas categorias e mantenha seus favoritos. Há dois preajustes disponíveis.

<p align="center">
  <img src="src/screenshots/previews/readme-tahoe-light-launcher-95744cf7a341.webp" alt="Tahoe Launchpad · Claro" width="415">
  <img src="src/screenshots/previews/readme-tahoe-dark-launcher-2399734a1625.webp" alt="Tahoe Launchpad · Escuro" width="415">
</p>

### Tahoe Dock (Alpha)

Refração do vidro, ampliação ao passar o cursor, contadores de notificações e ocultação automática.

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-regular-6d506b3465fd.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-regular-6d506b3465fd.webp" alt="Tahoe Dock · Claro" width="415"></a><br>Padrão · Claro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-regular-9254e2db86a7.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-regular-9254e2db86a7.webp" alt="Tahoe Dock · Escuro" width="415"></a><br>Padrão · Escuro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-clear-843c40a052a7.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-clear-843c40a052a7.webp" alt="Tahoe Dock · Claro" width="415"></a><br>Transparente · Claro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-clear-58edd6d52e38.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-clear-58edd6d52e38.webp" alt="Tahoe Dock · Escuro" width="415"></a><br>Transparente · Escuro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-blue-d39bb78e2f1d.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-blue-d39bb78e2f1d.webp" alt="Tahoe Dock · Claro" width="415"></a><br>Azul · Claro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-blue-a292ebe93f08.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-blue-a292ebe93f08.webp" alt="Tahoe Dock · Escuro" width="415"></a><br>Azul · Escuro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-purple-b8d6d4a59d58.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-purple-b8d6d4a59d58.webp" alt="Tahoe Dock · Claro" width="415"></a><br>Roxo · Claro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-purple-090970372f80.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-purple-090970372f80.webp" alt="Tahoe Dock · Escuro" width="415"></a><br>Roxo · Escuro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-pink-c0b0ba00ddeb.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-pink-c0b0ba00ddeb.webp" alt="Tahoe Dock · Claro" width="415"></a><br>Rosa · Claro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-pink-ba6941817529.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-pink-ba6941817529.webp" alt="Tahoe Dock · Escuro" width="415"></a><br>Rosa · Escuro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-red-19adb9d798fd.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-red-19adb9d798fd.webp" alt="Tahoe Dock · Claro" width="415"></a><br>Vermelho · Claro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-red-379c09615f96.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-red-379c09615f96.webp" alt="Tahoe Dock · Escuro" width="415"></a><br>Vermelho · Escuro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-orange-18c4663ce547.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-orange-18c4663ce547.webp" alt="Tahoe Dock · Claro" width="415"></a><br>Laranja · Claro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-orange-5079b478c649.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-orange-5079b478c649.webp" alt="Tahoe Dock · Escuro" width="415"></a><br>Laranja · Escuro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-yellow-c7656eaf2b61.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-yellow-c7656eaf2b61.webp" alt="Tahoe Dock · Claro" width="415"></a><br>Amarelo · Claro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-yellow-c1945efddc21.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-yellow-c1945efddc21.webp" alt="Tahoe Dock · Escuro" width="415"></a><br>Amarelo · Escuro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-green-ac9611249165.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-green-ac9611249165.webp" alt="Tahoe Dock · Claro" width="415"></a><br>Verde · Claro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-green-84eab2e65cf2.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-green-84eab2e65cf2.webp" alt="Tahoe Dock · Escuro" width="415"></a><br>Verde · Escuro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-light-dock-gray-18617e5c0df8.webp"><img src="src/screenshots/previews/readme-tahoe-light-dock-gray-18617e5c0df8.webp" alt="Tahoe Dock · Claro" width="415"></a><br>Cinza · Claro</p>

<p align="center"><a href="src/screenshots/previews/readme-tahoe-dark-dock-gray-e7baf051c7cb.webp"><img src="src/screenshots/previews/readme-tahoe-dark-dock-gray-e7baf051c7cb.webp" alt="Tahoe Dock · Escuro" width="415"></a><br>Cinza · Escuro</p>

### Tahoe Shell (Alpha)

Acesso às configurações do sistema, aplicativos e controles de sessão.

<p align="center">
  <img src="src/screenshots/previews/readme-tahoe-light-menu-a8579c6bdc3c.webp" alt="Tahoe Shell · Claro" width="415">
  <img src="src/screenshots/previews/readme-tahoe-dark-menu-01a3a4305740.webp" alt="Tahoe Shell · Escuro" width="415">
</p>

### Tahoe Central de Controle (Alpha)

Wi-Fi, som, brilho e notificações em um menu de vidro.

<p align="center">
  <img src="src/screenshots/previews/readme-tahoe-light-control-f093af128a34.webp" alt="Tahoe Central de Controle · Claro" width="415">
  <img src="src/screenshots/previews/readme-tahoe-dark-control-3a039c914a10.webp" alt="Tahoe Central de Controle · Escuro" width="415">
</p>

### Tahoe Histórico da área de transferência (Alpha)

Encontre e reutilize textos e imagens copiados diretamente pelo Launchpad.

<p align="center">
  <img src="src/screenshots/previews/readme-tahoe-light-clipboard-e0cf55fa87a4.webp" alt="Tahoe Histórico da área de transferência · Claro" width="415">
  <img src="src/screenshots/previews/readme-tahoe-dark-clipboard-024174b100b7.webp" alt="Tahoe Histórico da área de transferência · Escuro" width="415">
</p>

### Tahoe Informações do sistema

Informações sobre hardware, software e tema.

<p align="center">
  <img src="src/screenshots/previews/readme-tahoe-light-about-2a83d687da3f.webp" alt="Tahoe Informações do sistema · Claro" width="415">
  <img src="src/screenshots/previews/readme-tahoe-dark-about-c6bf5138a206.webp" alt="Tahoe Informações do sistema · Escuro" width="415">
</p>

### Tahoe Tema Plasma (Alpha)

Menus e janelas pop-up translúcidos com cores claras e escuras coordenadas.

<p align="center">
  <img src="src/screenshots/previews/readme-tahoe-light-context-a94e322fac42.webp" alt="Tahoe Tema Plasma · Claro" width="415">
  <img src="src/screenshots/previews/readme-tahoe-dark-context-359afa6d3a32.webp" alt="Tahoe Tema Plasma · Escuro" width="415">
</p>

### Tahoe Tela de inicialização (Alpha)

Tela de inicialização com desbloqueio integrado de unidades criptografadas com LUKS2.

<p align="center">
  <img src="src/screenshots/previews/readme-tahoe-light-boot-959163f469f4.webp" alt="Tahoe Tela de inicialização" width="415">
</p>

## Opções e ferramentas

O assistente permite escolher componentes, ícones, papéis de parede, botões e sombras das janelas. A reinstalação mantém a personalização do Dock, salvo quando você escolhe redefini-la. O tema sincroniza a aparência clara/escura, integra menus globais e estilos GTK/Qt e faz backup dos perfis do Firefox antes de alterá-los.

A proteção OLED é opcional e vem desativada. Ative-a no assistente e escolha o intervalo e deslocamento máximo. Controles manuais:

```bash
mac-tahoe-oled-care shift
mac-tahoe-oled-care restore
mac-tahoe-oled-care status
```

Para testar em um ambiente isolado, use `./vm <os>`. Consulte o [guia de máquinas virtuais](tests/vm/README.md). A validação completa do Kubuntu continua pendente. NixOS e Home Manager são experimentais: use os módulos flake, não o instalador gráfico; consulte a [configuração detalhada em inglês](README.md).

O [guia de contribuição](CONTRIBUTING.md) documenta configurações avançadas e o gerador compartilhado de ícones. Execute `./icon-toolset` no Tahoe para gerar, visualizar e verificar ícones das duas edições sem aplicar o tema ao ambiente. Para liberar espaço do Git preservando o trabalho local: `./installer --free-space`.

Consulte os [resultados e limites dos testes](tests/vm/PROOF.md) e as [fotografias do instalador](TESTING.md). As fotografias mantêm sua procedência original; não representam uma nova validação de cada versão.

[Referência técnica completa e estado dos componentes (inglês)](README.md)

## Contribuições e problemas

[Relate problemas](https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new) incluindo a versão do Plasma (`plasmashell --version`), a distribuição, a versão do tema e uma captura ou gravação para problemas visuais. Consulte o [guia de contribuição](CONTRIBUTING.md).

Colaboradores de código e pessoas que relataram problemas no Tahoe e Golden Gate:

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

## Licença e créditos

Projeto independente inspirado no macOS, sem afiliação ou endosso da Apple ou do KDE. O conjunto é distribuído sob [GPL-3.0](LICENSE); as licenças de cada componente e os direitos de terceiros continuam válidos. O emblema, papéis de parede, sons e fontes SF da Apple não são cobertos pela licença do projeto. Consulte [NOTICE](NOTICE), [LICENSING.md](LICENSING.md) e [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

<details>
<summary>Créditos e avisos originais (inglês)</summary>

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
