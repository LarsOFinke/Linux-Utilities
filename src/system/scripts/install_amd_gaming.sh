#!/usr/bin/env bash
# Ubuntu Gaming-Setup für AMD Radeon RX 6600 + Ryzen 5 5500
set -euo pipefail

if [[ $EUID -eq 0 ]]; then
  echo "Bitte ohne sudo starten: ./install-amd-gaming.sh"
  exit 1
fi

sudo dpkg --add-architecture i386
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y universe
sudo add-apt-repository -y multiverse
sudo apt update

sudo apt install -y \
  steam-installer \
  mesa-vulkan-drivers mesa-vulkan-drivers:i386 \
  libvulkan1 libvulkan1:i386 \
  libgl1-mesa-dri libgl1-mesa-dri:i386 \
  mesa-utils vulkan-tools \
  gamemode libgamemode0 libgamemode0:i386 \
  mangohud protontricks \
  amd64-microcode linux-firmware

echo
echo "Installation abgeschlossen."
echo "Bitte neu starten: sudo reboot"
echo "Danach prüfen mit:"
echo "  lspci -k | grep -EA3 'VGA|3D|Display'"
echo "  vulkaninfo --summary"
echo "  glxinfo -B"
