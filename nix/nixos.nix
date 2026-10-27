{ config, lib, pkgs, ... }:
let
  cfg = config.services.mac-tahoe;
  packages = import ./packages.nix { inherit pkgs; language = config.i18n.defaultLocale; };
  plugins = [ packages.global-menu packages.task-manager packages.acrylic-glass packages.rounded-corners ];
in {
  options.services.mac-tahoe = {
    enable = lib.mkEnableOption "system-wide MacTahoe assets and compiled Plasma plugins";
    appleAssets = lib.mkEnableOption "optional non-free Apple fonts, wallpapers and sounds";
    plymouth.enable = lib.mkEnableOption "the MacTahoe Plymouth boot theme";
  };
  config = lib.mkMerge [
    (lib.mkIf cfg.enable {
      assertions = [{
        assertion = config.services.desktopManager.plasma6.enable;
        message = "services.mac-tahoe requires the Plasma 6 desktop.";
      }];
      environment.systemPackages = [ packages.default pkgs.kdePackages.qtstyleplugin-kvantum ]
        ++ lib.optional cfg.appleAssets packages.apple-assets;
      environment.pathsToLink = [ "/share" "/${pkgs.kdePackages.qtbase.qtPluginPrefix}" "/${pkgs.kdePackages.qtbase.qtQmlPrefix}" ];
      environment.sessionVariables = {
        QT_PLUGIN_PATH = map (p: "${p}/${pkgs.kdePackages.qtbase.qtPluginPrefix}") plugins;
        QML2_IMPORT_PATH = map (p: "${p}/${pkgs.kdePackages.qtbase.qtQmlPrefix}") plugins;
      };
    })
    (lib.mkIf cfg.plymouth.enable {
      boot.plymouth = {
        enable = true;
        theme = "MacTahoeLiquidKde";
        themePackages = [ packages.plymouth ];
      };
    })
  ];
}
