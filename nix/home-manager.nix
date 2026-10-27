{ config, lib, pkgs, ... }:
let
  cfg = config.programs.mac-tahoe;
  packages = import ./packages.nix { inherit pkgs; };
  assets = packages.theme-assets;
  plugins = [ packages.global-menu packages.task-manager packages.acrylic-glass packages.rounded-corners ];
  qtPluginPath = lib.concatMapStringsSep ":" (p: "${p}/${pkgs.kdePackages.qtbase.qtPluginPrefix}") plugins;
  qmlImportPath = lib.concatMapStringsSep ":" (p: "${p}/${pkgs.kdePackages.qtbase.qtQmlPrefix}") plugins;
  names = [ "MacTahoeLiquidKde-Light" "MacTahoeLiquidKde-Dark" ];
  kvNames = [ "mac-tahoe-liquid-kde" "mac-tahoe-liquid-kdeDark" ];
  mutable = [ "kdeglobals" "kwinrc" "plasmarc" "plasmashellrc" "kcminputrc"
              "plasma-org.kde.plasma.desktop-appletsrc" "Kvantum/kvantum.kvconfig"
              "gtk-3.0/settings.ini" "gtk-4.0/gtk.css" "gtk-4.0/gtk-Light.css"
              "gtk-4.0/gtk-Dark.css" "gtk-4.0/assets" "gtk-4.0/windows-assets"
              "Kvantum" "gtk-3.0" "gtk-4.0" ];
  initEffects = pkgs.writeShellScript "mac-tahoe-initialize-effects" ''
    set -eu
    for effect in liquidglass shapecorners; do
      value="$(${pkgs.kdePackages.kconfig}/bin/kreadconfig6 --file kwinrc --group Plugins --key "''${effect}Enabled" --default __absent__)"
      if [ "$value" = __absent__ ]; then
        ${pkgs.kdePackages.kconfig}/bin/kwriteconfig6 --file kwinrc --group Plugins --key "''${effect}Enabled" true
      fi
    done
  '';
in {
  options.programs.mac-tahoe = {
    enable = lib.mkEnableOption "MacTahoe Plasma styling and live theme switching";
    mode = lib.mkOption { type = lib.types.enum [ "auto" "light" "dark" ]; default = "auto"; description = "Login appearance; auto also switches at 06:00 and 18:00."; };
    gtkAppmenuModule = lib.mkOption { type = lib.types.nullOr lib.types.path; default = null; description = "Optional native GTK3 appmenu module library; loaded for the process lifetime."; };
    appleAssets = lib.mkEnableOption "non-free Apple fonts, wallpapers and sounds (requires allowUnfreePredicate)";
    oledCare.enable = lib.mkEnableOption "periodic OLED panel pixel shifting";
    oledCare.interval = lib.mkOption { type = lib.types.ints.between 1 59; default = 5; description = "Minutes between panel shifts."; };
    oledCare.maxShift = lib.mkOption { type = lib.types.ints.between 1 16; default = 8; description = "Maximum shift in logical pixels."; };
  };
  config = lib.mkIf cfg.enable {
    assertions = map (file: {
      assertion = !(config.xdg.configFile ? ${file}) && !(config.home.file ? ${".config/" + file})
        && !(config.home.file ? ".config");
      message = "MacTahoe needs ${file} writable; do not manage the whole file with Home Manager. Use mutable plasma-manager settings instead.";
    }) mutable;
    fonts.fontconfig.enable = lib.mkDefault cfg.appleAssets;
    home.packages = [ packages.default pkgs.kdePackages.qtstyleplugin-kvantum ]
      ++ lib.optional cfg.appleAssets packages.apple-assets;
    home.file = lib.listToAttrs (map (name: {
      name = ".themes/${name}";
      value.source = "${assets}/share/themes/${name}";
    }) names);
    xdg.dataFile = {
      "plasma/desktoptheme" = { source = "${assets}/share/plasma/desktoptheme"; recursive = true; };
      "plasma/look-and-feel" = { source = "${assets}/share/plasma/look-and-feel"; recursive = true; };
      "plasma/plasmoids" = { source = "${assets}/share/plasma/plasmoids"; recursive = true; };
      "aurorae/themes" = { source = "${assets}/share/aurorae/themes"; recursive = true; };
      "color-schemes" = { source = "${assets}/share/color-schemes"; recursive = true; };
      "icons" = { source = "${assets}/share/icons"; recursive = true; };
    } // lib.optionalAttrs cfg.appleAssets {
      "wallpapers" = { source = "${packages.apple-assets}/share/wallpapers"; recursive = true; };
    };
    xdg.configFile = lib.listToAttrs (map (name: {
      name = "Kvantum/${name}";
      value.source = "${assets}/share/Kvantum/${name}";
    }) kvNames) // {
      "plasma-workspace/env/mac-tahoe-plugin-paths.sh".text = ''
        # Plasma sources this before launching KWin and plasmashell.
        # Extend the inherited paths here; home.sessionVariables would replace them.
        export QT_PLUGIN_PATH="${qtPluginPath}''${QT_PLUGIN_PATH:+:$QT_PLUGIN_PATH}"
        export QML2_IMPORT_PATH="${qmlImportPath}''${QML2_IMPORT_PATH:+:$QML2_IMPORT_PATH}"
        export XDG_DATA_DIRS="${packages.default}/share:''${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
      '';
    } // lib.optionalAttrs (cfg.gtkAppmenuModule != null) {
      "plasma-workspace/env/mac-tahoe-gtk-appmenu.sh".text = ''
        # mac-tahoe-liquid-kde: GTK3 appmenu lifetime guard
        module=${lib.escapeShellArg (toString cfg.gtkAppmenuModule)}
        case ":''${GTK3_MODULES-}:" in
          *":$module:"*) ;;
          *) export GTK3_MODULES="''${GTK3_MODULES:+$GTK3_MODULES:}$module" ;;
        esac
      '';
    };
    systemd.user.services.mac-tahoe-theme = {
      Unit = {
        Description = "Apply MacTahoe appearance";
        After = [ "plasma-plasmashell.service" ];
        PartOf = [ "graphical-session.target" ];
      };
      Service = {
        Type = "oneshot";
        ExecStartPre = "${initEffects}";
        ExecStart = "${packages.tools}/bin/mac-tahoe-theme-switch ${cfg.mode}";
      };
      Install.WantedBy = [ "plasma-plasmashell.service" ];
    };
    systemd.user.timers.mac-tahoe-theme = lib.mkIf (cfg.mode == "auto") {
      Unit.Description = "Switch MacTahoe at 06:00 and 18:00";
      Timer = { OnCalendar = [ "*-*-* 06:00:00" "*-*-* 18:00:00" ]; Persistent = true; };
      Install.WantedBy = [ "timers.target" ];
    };
    systemd.user.services.mac-tahoe-oled = lib.mkIf cfg.oledCare.enable {
      Unit = { Description = "MacTahoe OLED care"; After = [ "plasma-plasmashell.service" ]; PartOf = [ "graphical-session.target" ]; };
      Service = { Type = "oneshot"; ExecStart = "${packages.tools}/bin/mac-tahoe-oled-care shift --max-px ${toString cfg.oledCare.maxShift}"; };
    };
    systemd.user.timers.mac-tahoe-oled = lib.mkIf cfg.oledCare.enable {
      Unit.Description = "Shift MacTahoe panels periodically";
      Timer.OnCalendar = "*-*-* *:0/${toString cfg.oledCare.interval}:00";
      Install.WantedBy = [ "timers.target" ];
    };
  };
}
