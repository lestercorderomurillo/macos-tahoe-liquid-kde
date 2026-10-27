#!/bin/bash
# Optional SSH access to an official live ISO, via ./vm's loopback port.
set -euo pipefail
[[ "$(cat /sys/class/dmi/id/sys_vendor)" == QEMU && "$EUID" == 0 ]] || exit 1
case "$(findmnt -n -o FSTYPE /)" in
    overlay|squashfs|tmpfs) ;;
    *) echo 'This helper is only for disposable live media.' >&2; exit 1 ;;
esac
source /etc/os-release
if [[ "$ID" == ubuntu ]]; then
    apt-get update
    apt-get install -y openssh-server
fi
id tester >/dev/null 2>&1 || useradd -m -s /bin/bash tester
printf '%s\n' 'tester:tester' | chpasswd
printf '%s\n' 'tester ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/mttkde-vm
chmod 0440 /etc/sudoers.d/mttkde-vm
mkdir -p /etc/ssh/sshd_config.d
printf '%s\n' 'PasswordAuthentication yes' > /etc/ssh/sshd_config.d/00-mttkde-vm.conf
ssh-keygen -A
if [[ "$ID" == artix ]]; then
    rc-service sshd start
elif [[ "$ID" == ubuntu ]]; then
    systemctl start ssh
else
    systemctl start sshd
fi
