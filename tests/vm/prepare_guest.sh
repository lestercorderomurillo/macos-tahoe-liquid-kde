#!/bin/bash
# Run inside an installed official-ISO guest, before desktop qualification.
set -euo pipefail
[[ "$(cat /sys/class/dmi/id/sys_vendor)" == QEMU && "$EUID" == 0 ]] || {
    echo 'Run with sudo inside the disposable QEMU guest.' >&2; exit 1;
}
case "$(findmnt -n -o FSTYPE /)" in
    overlay|squashfs|tmpfs) echo 'Install the distribution to the guest disk first.' >&2; exit 1 ;;
esac
id tester >/dev/null
source /etc/os-release
case "$ID" in
    arch|cachyos|manjaro|endeavouros|garuda)
        pacman -Syu --noconfirm --ask=4 --ignore=plasma-x11-session,plasma-wayland-session \
            --needed openssh rsync sudo python-pyqt6 qt6-tools spectacle firefox
        ;;
    artix)
        # The ISO's separate plasma-x11-session conflicts with Plasma 6.8's
        # merged workspace package. Accept conflict removals in this disposable
        # guest; pacman still enforces dependencies throughout the transaction.
        pacman -Syu --noconfirm --ask=4 --ignore=plasma-x11-session,plasma-wayland-session \
            --needed openssh openssh-openrc rsync sudo \
            python-pyqt6 qt6-tools spectacle firefox cronie cronie-openrc
        ;;
    fedora|nobara)
        dnf upgrade -y
        dnf install -y openssh-server rsync sudo python3-pyqt6 qt6-qtbase-devel qt6-qttools spectacle firefox
        ;;
    ubuntu)
        [[ "$VERSION_ID" == 26.04 ]] && dpkg-query -W -f='${Status}' kubuntu-desktop | grep -qx 'install ok installed' || {
            echo 'Expected the installed Kubuntu 26.04 LTS desktop.' >&2; exit 1;
        }
        # Keep the LTS Plasma stack: no release upgrade or external repositories.
        export DEBIAN_FRONTEND=noninteractive
        apt-get update
        apt-get install -y openssh-server rsync sudo python3-pyqt6 python3-pyqt6.qtqml \
            qdbus-qt6 qmake6 kde-spectacle python3-pytest plasma-sdk xvfb x11-utils
        ;;
    *) echo "Use the cloud recipe for $ID; this helper prepares the official ISO targets." >&2; exit 1 ;;
esac
printf '%s\n' 'tester ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/mttkde-vm
chmod 0440 /etc/sudoers.d/mttkde-vm
printf '%s\n' 'tester:tester' | chpasswd
mkdir -p /etc/ssh/sshd_config.d
printf '%s\n' 'PasswordAuthentication yes' > /etc/ssh/sshd_config.d/00-mttkde-vm.conf
ssh-keygen -A
if [[ "$ID" == artix ]]; then
    rc-update add sshd default
    rc-service sshd restart
    rc-update add cronie default
    rc-service cronie start
elif [[ "$ID" == ubuntu ]]; then
    systemctl enable --now ssh
else
    systemctl enable --now sshd
fi
mkdir -p /home/tester/repo /home/tester/macos-tahoe-liquid-kde
chown tester:tester /home/tester/macos-tahoe-liquid-kde
[[ -d /sys/module/9pnet_virtio ]] || modprobe 9pnet_virtio
if ! grep -q '^repo /home/tester/repo ' /etc/fstab; then
    printf '%s\n' 'repo /home/tester/repo 9p trans=virtio,version=9p2000.L,msize=262144,ro,nofail 0 0' >> /etc/fstab
fi
if ! mountpoint -q /home/tester/repo; then
    existing_mount="$(findmnt -rn -t 9p -S repo -o TARGET | head -n 1)"
    if [[ -n "$existing_mount" ]]; then
        mount --bind -o ro "$existing_mount" /home/tester/repo
    else
        mount /home/tester/repo
    fi
fi
sudo -u tester rsync -a --delete --exclude=.git --exclude=.vm --exclude=build \
    /home/tester/repo/ /home/tester/macos-tahoe-liquid-kde/
# Test theme rendering with a clean GTK profile. Preserve the ISO's overrides
# for inspection: the installer correctly refuses to replace custom gtk.css.
if [[ -d /home/tester/.config/gtk-4.0 && ! -e /home/tester/vm-original-gtk-4.0 ]]; then
    sudo -u tester mv /home/tester/.config/gtk-4.0 /home/tester/vm-original-gtk-4.0
fi
session=plasma.desktop
if [[ ! -f /usr/share/wayland-sessions/$session ]]; then
    session=plasmawayland.desktop
fi
if [[ "$(readlink /etc/systemd/system/display-manager.service || true)" == *plasmalogin* ]]; then
    config=/etc/plasmalogin.conf.d
else
    config=/etc/sddm.conf.d
fi
mkdir -p "$config"
printf '[Autologin]\nUser=tester\nSession=%s\n' "$session" > "$config/mttkde-vm.conf"
echo 'Guest ready. Reboot, then run tests/vm/qualify.py on the host.'
