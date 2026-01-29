#!/bin/bash
#
# Erstellt ein bootfähiges Ubuntu ISO mit Autoinstall für alle Nodes
#
# Verwendung: ./create-iso.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
ISO_URL="https://releases.ubuntu.com/24.04/ubuntu-24.04.3-live-server-amd64.iso"
ISO_FILE="$SCRIPT_DIR/ubuntu-24.04-server.iso"
OUTPUT_DIR="$SCRIPT_DIR/output"
WORK_DIR="$SCRIPT_DIR/work"

AUTOINSTALL_DIR="$BASE_DIR/01-generate-configs/autoinstall"

echo "=== Cloudkoffer ISO Builder ==="
echo ""

# Prüfen ob Konfiguration existiert
if [[ ! -f "$AUTOINSTALL_DIR/user-data" ]]; then
    echo "FEHLER: Konfiguration nicht gefunden!"
    echo "Führe zuerst aus: ../02-generate-configs/generate-all.sh"
    exit 1
fi

mkdir -p "$OUTPUT_DIR" "$WORK_DIR"

# Ubuntu ISO herunterladen
if [[ ! -f "$ISO_FILE" ]]; then
    echo "[1/5] Ubuntu Server ISO herunterladen..."
    wget -O "$ISO_FILE" "$ISO_URL"
else
    echo "[1/5] Ubuntu ISO bereits vorhanden"
fi

# ISO entpacken
echo "[2/5] ISO entpacken..."
if [[ -d "$WORK_DIR/iso-extract" ]]; then
    sudo rm -rf "$WORK_DIR/iso-extract"
fi
xorriso -osirrox on -indev "$ISO_FILE" -extract / "$WORK_DIR/iso-extract"
# Berechtigungen korrigieren (xorriso erstellt read-only Dateien)
chmod -R u+w "$WORK_DIR/iso-extract"

# EFI-Partition aus Original-ISO extrahieren (ist als versteckte Partition eingebettet)
echo "[2.5/5] EFI-Partition extrahieren..."
dd if="$ISO_FILE" bs=512 skip=6441216 count=10160 of="$WORK_DIR/iso-extract/boot/grub/efi.img" status=none 

# Autoinstall Konfiguration kopieren
echo "[3/5] Autoinstall Konfiguration einbinden..."
mkdir -p "$WORK_DIR/iso-extract/autoinstall"
cp "$AUTOINSTALL_DIR/user-data" "$WORK_DIR/iso-extract/autoinstall/user-data"
cp "$AUTOINSTALL_DIR/meta-data" "$WORK_DIR/iso-extract/autoinstall/meta-data"

# GRUB anpassen
echo "[4/5] GRUB Konfiguration..."
cat > "$WORK_DIR/iso-extract/boot/grub/grub.cfg" << 'EOF'
set timeout=5
loadfont unicode

menuentry "Cloudkoffer Autoinstall" {
    set gfxpayload=keep
    linux   /casper/vmlinuz autoinstall ds=nocloud\;s=/cdrom/autoinstall/ ---
    initrd  /casper/initrd
}

menuentry "Ubuntu Server (Manuell)" {
    set gfxpayload=keep
    linux   /casper/vmlinuz ---
    initrd  /casper/initrd
}
EOF

# ISO erstellen
echo "[5/5] ISO erstellen..."
xorriso -as mkisofs \
    -r -V "CLOUDKOFFER" \
    -o "$OUTPUT_DIR/cloudkoffer.iso" \
    -J -joliet-long -iso-level 3 \
    -partition_offset 16 \
    --grub2-mbr /usr/lib/grub/i386-pc/boot_hybrid.img \
    -append_partition 2 0xef "$WORK_DIR/iso-extract/boot/grub/efi.img" \
    -appended_part_as_gpt \
    -c boot.catalog \
    -b boot/grub/i386-pc/eltorito.img \
    -no-emul-boot -boot-load-size 4 -boot-info-table --grub2-boot-info \
    -eltorito-alt-boot \
    -e '--interval:appended_partition_2:all::' \
    -no-emul-boot \
    "$WORK_DIR/iso-extract" 2>/dev/null

echo ""
echo "=== Fertig! ==="
echo "ISO: $OUTPUT_DIR/cloudkoffer.iso"
