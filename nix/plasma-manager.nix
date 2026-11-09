# Optional: the user imports plasma-manager separately. No dependency is added.
{ config, lib, pkgs, ... }:
{
  options.programs.mac-tahoe.panels = {
    enable = lib.mkEnableOption "the MacTahoe top bar and Dock (replaces the declarative panel layout)";
    launchers = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [];
      example = [ "applications:org.kde.dolphin.desktop" ];
      description = "Explicit Dock launchers; existing imperative pins are not migrated.";
    };
  };
  config = lib.mkIf config.programs.mac-tahoe.panels.enable {
    programs.mac-tahoe.enable = true;
    programs.plasma = {
      enable = true;
      panels = [
        {
          location = "top";
          height = 32;
          floating = false;
          opacity = "translucent";
          widgets = [
            "org.kde.mac.tahoe.liquid.globalmenu"
            "org.kde.plasma.panelspacer"
            "org.kde.plasma.systemtray"
            "org.kde.plasma.digitalclock"
          ];
        }
        {
          location = "bottom";
          height = 64;
          floating = true;
          opacity = "translucent";
          hiding = "autohide";
          lengthMode = "fit";
          alignment = "center";
          widgets = [
            "org.kde.mac-tahoe-liquid-kde.launcher"
            { name = "org.kde.mac.tahoe.liquid.icontasks";
              config.General.launchers = lib.concatStringsSep "," config.programs.mac-tahoe.panels.launchers; }
            "org.kde.mac-tahoe-liquid-kde.trashcan"
          ];
        }
      ];
      # Run after plasma-manager has created the panel view groups. The
      # command is idempotent and does not reapply the entire global theme.
      startup.desktopScript."mac-tahoe-panel-appearance" = {
        priority = 3;
        text = "// Panel appearance is finalized after layout creation.";
        postCommands = "${(import ./packages.nix { inherit pkgs; }).tools}/bin/mac-tahoe-theme-switch patch-dock";
      };
    };
  };
}
