#!/bin/bash
#
# Schreibt ISO auf USB-Stick
#
# Verwendung: ./write-usb.sh <USB_DEVICE>
# Beispiel:   ./write-usb.sh /dev/sdb
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
ISO_FILE="$BASE_DIR/02-create-iso/output/cloudkoffer.iso"

USB_DEVICE="${1:-}"

if [[ -z "$USB_DEVICE" ]]; then
    echo "Verwendung: $0 <USB_DEVICE>"
    echo "Beispiel:   $0 /dev/sdb"
    echo ""
    echo "USB-Geräte:"
    lsblk -d -o NAME,SIZE,MODEL | grep -v "loop\|sr\|nvme"
    exit 1
fi

if [[ ! -f "$ISO_FILE" ]]; then
    echo "FEHLER: ISO nicht gefunden: $ISO_FILE"
    echo "Führe zuerst ../01-create-iso/create-iso.sh aus."
    exit 1
fi

echo "=== USB schreiben ==="
echo "ISO:  $ISO_FILE"
echo "Ziel: $USB_DEVICE"
echo ""
lsblk "$USB_DEVICE"
echo ""
echo "ALLE DATEN WERDEN GELÖSCHT!"
read -p "Fortfahren? (ja/NEIN): " CONFIRM

if [[ "$CONFIRM" != "ja" ]]; then
    echo "Abgebrochen."
    exit 0
fi

umount "${USB_DEVICE}"* 2>/dev/null || true
sudo dd if="$ISO_FILE" of="$USB_DEVICE" bs=4M status=progress conv=fsync

echo ""
echo "=== Fertig! ==="
echo "USB-Stick bereit. Kann für alle 5 NUCs verwendet werden."
