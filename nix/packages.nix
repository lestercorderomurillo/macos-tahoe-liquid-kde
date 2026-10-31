{ pkgs, language ? "en" }:
let
  inherit (pkgs) lib;
  kde = pkgs.kdePackages;
  version = lib.strings.trim (builtins.readFile ../VERSION);
  offline = ../src/offline;
  locale = if lib.hasPrefix "pt_BR" language then "pt_BR"
    else if lib.hasPrefix "de" language then "de" else "en";
  passwordPrompt = if locale == "en" then "Password:"
    else (builtins.fromJSON (builtins.readFile (../src/scripts/locales + "/${locale}.json")))."Password:";
  meta = {
    description = "Independent macOS Tahoe-inspired theme for KDE Plasma";
    homepage = "https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde";
    license = lib.licenses.gpl3Only;
    platforms = lib.platforms.linux;
  };
  buildPlugin = name: src: extra: pkgs.stdenv.mkDerivation ({
    pname = "mac-tahoe-${name}";
    inherit version src meta;
    nativeBuildInputs = [ pkgs.cmake kde.extra-cmake-modules pkgs.pkg-config pkgs.wayland-scanner kde.wrapQtAppsHook ];
    buildInputs = with kde; [ qtbase qtdeclarative qtwayland qttools kconfig kconfigwidgets
      kcoreaddons kcrash kglobalaccel kguiaddons ki18n kio kcmutils knotifications
      kservice kwidgetsaddons kwindowsystem kcolorscheme libplasma plasma-activities
      plasma-activities-stats libksysguard plasma-workspace kwin kdecoration ]
      ++ [ pkgs.libepoxy pkgs.libdrm pkgs.wayland pkgs.libxkbcommon
           pkgs.libGL pkgs.vulkan-headers pkgs.vulkan-loader pkgs.libx11 pkgs.libxcb ];
    dontWrapQtApps = true;
    cmakeFlags = [ "-DCMAKE_BUILD_TYPE=Release" ];
  } // extra);
  # Read the same audited tag and digest as the imperative installer.
  pin = builtins.readFile ../src/scripts/steps/rounded_corners.py;
  capture = key: builtins.head (builtins.match (".*" + key + " = \"([^\"]+)\".*") pin);
in rec {
  theme-assets = pkgs.stdenvNoCC.mkDerivation {
    pname = "mac-tahoe-theme-assets";
    inherit version meta;
    src = lib.fileset.toSource {
      root = offline;
      fileset = lib.fileset.unions (map (name: offline + "/${name}") [
        "aurorae" "color-schemes" "cursors" "gtk" "icons" "kvantum"
        "look-and-feel" "plasma-theme" "plasmoids"
      ]);
    };
    nativeBuildInputs = [ pkgs.python3 pkgs.zstd ];
    installPhase = ''
      runHook preInstall
      PYTHONPATH=${../src/scripts} python ${./install-assets.py} . "$out"
      mkdir -p "$out/share/icons"
      tar --zstd -xf "$src/icons/MacTahoeLiquidKde-Icons.tar.zst" -C "$out/share/icons"
      PYTHONPATH=${../src/scripts} python ${../src/scripts/interface_icons.py} "$out/share/icons"
      tar --zstd -xf "$src/cursors/MacTahoeLiquidKde-Cursors.tar.zst" -C "$out/share/icons"
      runHook postInstall
    '';
  };
  global-menu = buildPlugin "global-menu" (offline + "/plasmoids/org.kde.mac.tahoe.liquid.globalmenu") {};
  task-manager = buildPlugin "task-manager" (offline + "/plasmoids/org.kde.mac.tahoe.liquid.taskmanager") {};
  acrylic-glass = buildPlugin "acrylic-glass" (offline + "/kwin-effects/acrylic-glass") {};
  rounded-corners = buildPlugin "rounded-corners" (pkgs.fetchurl {
    url = "https://github.com/matinlotfali/KDE-Rounded-Corners/archive/refs/tags/v${capture "UPSTREAM_VERSION"}.tar.gz";
    sha256 = capture "UPSTREAM_SHA256";
  }) {
    version = capture "UPSTREAM_VERSION";
    # Upstream has an informational /usr header probe, not a build dependency.
    postPatch = ''
      ${pkgs.python3}/bin/python ${../src/scripts/rounded_corners_compat.py} .
      substituteInPlace cmake/info.cmake --replace-fail /usr/include/ ${kde.kwin.dev}/include/
    '';
  };
  tools = pkgs.stdenvNoCC.mkDerivation {
    pname = "mac-tahoe-tools";
    inherit version meta;
    dontUnpack = true;
    nativeBuildInputs = [ pkgs.makeWrapper ];
    installPhase = ''
      mkdir -p "$out/bin" "$out/libexec"
      cp ${../src/scripts/theme_switch.py} "$out/libexec/theme_switch.py"
      cp ${../src/scripts/localization.py} "$out/libexec/localization.py"
      cp -r ${../src/scripts/locales} "$out/libexec/locales"
      cp ${../src/scripts/defaults.json} "$out/libexec/defaults.json"
      cp ${../src/scripts/oled_care.py} "$out/libexec/oled_care.py"
      for tool in theme-switch oled-care; do
        script="$(echo "$tool" | tr - _)"
        makeWrapper ${pkgs.python3}/bin/python "$out/bin/mac-tahoe-$tool" \
          --add-flags "$out/libexec/$script.py" \
          --prefix PATH : ${lib.makeBinPath [ kde.kconfig kde.qttools kde.plasma-workspace kde.kde-gtk-config kde.qtstyleplugin-kvantum pkgs.glib pkgs.dbus pkgs.xdg-utils ]}
      done
    '';
  };
  apple-assets = pkgs.stdenvNoCC.mkDerivation {
    pname = "mac-tahoe-apple-assets";
    inherit version;
    src = lib.fileset.toSource {
      root = offline;
      fileset = lib.fileset.unions [ (offline + "/fonts") (offline + "/wallpapers") (offline + "/sounds") ];
    };
    meta = meta // { license = lib.licenses.unfree; };
    installPhase = ''
      mkdir -p "$out/share/fonts" "$out/share/wallpapers" "$out/share/sounds"
      cp -r fonts/. "$out/share/fonts/"
      cp -r wallpapers/. "$out/share/wallpapers/"
      cp -r sounds/. "$out/share/sounds/"
    '';
  };
  plymouth = pkgs.stdenvNoCC.mkDerivation {
    pname = "mac-tahoe-plymouth";
    inherit version meta;
    src = offline + "/plymouth/MacTahoeLiquidKde";
    installPhase = ''
      dir="$out/share/plymouth/themes/MacTahoeLiquidKde"
      mkdir -p "$dir"
      cp -r . "$dir/"
      substituteInPlace "$dir/MacTahoeLiquidKde.script" \
        --replace-fail 'prompt = "Password:";' ${lib.escapeShellArg ("prompt = " + builtins.toJSON passwordPrompt + ";")}
      substituteInPlace "$dir/MacTahoeLiquidKde.plymouth" \
        --replace-fail /usr/share/plymouth/themes/MacTahoeLiquidKde "$dir"
    '';
  };
  default = pkgs.symlinkJoin {
    name = "mac-tahoe-liquid-kde-${version}";
    paths = [ theme-assets global-menu task-manager acrylic-glass rounded-corners tools kde.plasma5support kde.kitemmodels ];
    inherit meta;
  };
}
