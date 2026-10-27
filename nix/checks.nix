{ nixpkgs, home-manager, pkgs, modules }:
let
  lib = pkgs.lib;
  home = extra: home-manager.lib.homeManagerConfiguration {
    inherit pkgs;
    modules = [ modules.home {
      home.username = "test";
      home.homeDirectory = "/home/test";
      home.stateVersion = "26.05";
      programs.mac-tahoe.enable = true;
    } extra ];
  };
  fixed = home { programs.mac-tahoe = { mode = "dark"; }; };
  customPaths = home {
    home.sessionVariables = {
      QT_PLUGIN_PATH = "/custom/qt/plugins";
      QML2_IMPORT_PATH = "/custom/qt/qml";
    };
  };
  pluginHook = "plasma-workspace/env/mac-tahoe-plugin-paths.sh";
  hook = pkgs.writeText "mac-tahoe-plugin-paths.sh" (
    builtins.unsafeDiscardStringContext fixed.config.xdg.configFile.${pluginHook}.text
  );
  packages = import ./packages.nix { inherit pkgs; };
  plugins = [ packages.global-menu packages.task-manager packages.acrylic-glass packages.rounded-corners ];
  expectedPaths = prefix: builtins.unsafeDiscardStringContext (
    lib.concatMapStringsSep ":" (p: "${p}/${prefix}") plugins
  );
  conflict = home { xdg.configFile."kwinrc".text = "[Plugins]"; };
  system = nixpkgs.lib.nixosSystem {
    inherit pkgs;
    modules = [ modules.system {
      system.stateVersion = "26.05";
      services.desktopManager.plasma6.enable = true;
      services.mac-tahoe = { enable = true; plymouth.enable = true; };
      boot.loader.grub.enable = false;
      fileSystems."/" = { device = "none"; fsType = "tmpfs"; };
    } ];
  };
in
assert fixed.config.systemd.user.timers == { };
assert !(fixed.config.xdg.configFile ? "mac-tahoe-liquid-kde/appearance.json");
assert !(builtins.tryEval conflict.activationPackage.drvPath).success;
assert !(fixed.config.home.sessionVariables ? QT_PLUGIN_PATH);
assert !(fixed.config.home.sessionVariables ? QML2_IMPORT_PATH);
assert customPaths.config.home.sessionVariables.QT_PLUGIN_PATH == "/custom/qt/plugins";
assert customPaths.config.home.sessionVariables.QML2_IMPORT_PATH == "/custom/qt/qml";
assert customPaths.config.xdg.configFile.${pluginHook}.text == fixed.config.xdg.configFile.${pluginHook}.text;
assert system.config.boot.plymouth.theme == "MacTahoeLiquidKde";
assert lib.length (lib.splitString ":" system.config.environment.sessionVariables.QT_PLUGIN_PATH) == 4;
pkgs.runCommand "mac-tahoe-module-checks" {
  # Force evaluation of the complete system, including module assertions.
  systemDrv = builtins.unsafeDiscardStringContext system.config.system.build.toplevel.drvPath;
} ''
  checkHook() (
    set -eu
    inheritedPlugins=
    inheritedQml=
    inheritedData=/usr/local/share:/usr/share
    case "$1" in
      unset)
        unset QT_PLUGIN_PATH QML2_IMPORT_PATH XDG_DATA_DIRS
        ;;
      empty)
        export QT_PLUGIN_PATH= QML2_IMPORT_PATH= XDG_DATA_DIRS=
        ;;
      populated)
        inheritedPlugins='/etc/profiles/per-user/test/lib/qt-6/plugins:/custom plugins'
        inheritedQml='/etc/profiles/per-user/test/lib/qt-6/qml:/home/test/.nix-profile/lib/qt-6/qml:/custom qml'
        inheritedData=/run/current-system/sw/share:/custom/share
        export QT_PLUGIN_PATH="$inheritedPlugins" QML2_IMPORT_PATH="$inheritedQml" XDG_DATA_DIRS="$inheritedData"
        ;;
    esac
    . ${hook}
    # Read through a child process to verify export as well as preservation.
    test "$(printenv QT_PLUGIN_PATH)" = "${expectedPaths pkgs.kdePackages.qtbase.qtPluginPrefix}''${inheritedPlugins:+:$inheritedPlugins}"
    test "$(printenv QML2_IMPORT_PATH)" = "${expectedPaths pkgs.kdePackages.qtbase.qtQmlPrefix}''${inheritedQml:+:$inheritedQml}"
    test "$(printenv XDG_DATA_DIRS)" = "${builtins.unsafeDiscardStringContext "${packages.default}/share"}:$inheritedData"
  )
  checkHook unset
  checkHook empty
  checkHook populated
  printf '%s\n' "$systemDrv" > "$out"
''
