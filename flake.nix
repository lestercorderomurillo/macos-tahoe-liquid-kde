{
  description = "Independent macOS Tahoe-inspired KDE Plasma themes and modules";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };
  outputs = { self, nixpkgs, home-manager }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      eachSystem = nixpkgs.lib.genAttrs systems;
    in {
      packages = eachSystem (system: builtins.removeAttrs (import ./nix/packages.nix {
        pkgs = import nixpkgs { inherit system; };
      }) [ "apple-assets" ]);
      # Optional non-free assets use the caller's explicit license policy.
      lib.mkPackages = pkgs: import ./nix/packages.nix { inherit pkgs; };
      nixosModules.default = import ./nix/nixos.nix;
      homeManagerModules.default = import ./nix/home-manager.nix;
      homeManagerModules.plasma-manager = import ./nix/plasma-manager.nix;
      checks = eachSystem (system:
        let
          pkgs = import nixpkgs { inherit system; };
          packages = self.packages.${system};
          home = home-manager.lib.homeManagerConfiguration {
            inherit pkgs;
            modules = [ self.homeManagerModules.default {
              home.username = "test";
              home.homeDirectory = "/home/test";
              home.stateVersion = "26.05";
              programs.mac-tahoe.enable = true;
            } ];
          };
        in {
          inherit (packages) theme-assets global-menu task-manager acrylic-glass rounded-corners tools;
          home-manager = home.activationPackage;
          module-evaluation = import ./nix/checks.nix {
            inherit nixpkgs home-manager pkgs;
            modules = { home = self.homeManagerModules.default; system = self.nixosModules.default; };
          };
          installed-icons = pkgs.runCommand "mac-tahoe-installed-icons" {
            nativeBuildInputs = [ (pkgs.python3.withPackages (ps: [ ps.pyqt6 ps.pillow ])) ];
          } ''
            export HOME="$TMPDIR" XDG_DATA_DIRS="$TMPDIR" XDG_CONFIG_DIRS="$TMPDIR"
            export QT_QPA_PLATFORM=offscreen QT_QPA_PLATFORMTHEME=generic
            export QT_PLUGIN_PATH="${pkgs.kdePackages.qtsvg}/${pkgs.kdePackages.qtbase.qtPluginPrefix}:${pkgs.kdePackages.qtbase}/${pkgs.kdePackages.qtbase.qtPluginPrefix}"
            PYTHONPATH=${./src/scripts} python ${./tests/containers/installed_icons.py} \
              --theme-root ${packages.theme-assets}/share/icons
            touch "$out"
          '';
          installed-artifacts = pkgs.runCommand "mac-tahoe-installed-artifacts" { } ''
            test -s ${packages.global-menu}/${pkgs.kdePackages.qtbase.qtPluginPrefix}/plasma/applets/org.kde.mac.tahoe.liquid.globalmenu.so
            test -s ${packages.task-manager}/${pkgs.kdePackages.qtbase.qtPluginPrefix}/plasma/applets/org.kde.mac.tahoe.liquid.taskmanager.so
            test -s ${packages.acrylic-glass}/${pkgs.kdePackages.qtbase.qtPluginPrefix}/kwin/effects/plugins/liquidglass.so
            test -s ${packages.rounded-corners}/${pkgs.kdePackages.qtbase.qtPluginPrefix}/kwin/effects/plugins/kwin4_effect_shapecorners.so
            test -s ${packages.rounded-corners}/share/kwin/shaders/shapecorners_core.frag
            if ${packages.tools}/bin/mac-tahoe-theme-switch > usage.txt 2>&1; then exit 1; fi
            grep -q 'Usage: mac-tahoe-theme-switch' usage.txt
            touch "$out"
          '';
        });
    };
}
