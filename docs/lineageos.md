# LineageOS on the Lenovo Tab M10 HD (TB-X306F)

What actually worked, from a Linux PC (CachyOS), October 2026. The tablet is
the Wi-Fi model (`amar_row_wifi`, MT8768, 2 GB RAM); the ROM is the
maintainer's LTE build, which runs fine on it once the steps below are
followed exactly.

**Sources**
- ROM: `https://ota.vistaslayer.ovh/` → `lineage-23.2-20261018-UNOFFICIAL-amar_row_lte.zip`
  (check the MD5 listed on the page)
- Stock firmware: `https://mirror.vistaslayer.ovh/Firmwares/amar_row_lte/X306F/`
  - `TB-X306F_S100152_210205_BMP.zip` — the base LineageOS expects
  - `TB-X306F_S120637_230301_BMP.zip` — the original firmware, to return to stock
- Install guide: `https://mirror.vistaslayer.ovh/lineageos-firmware-guide.html`

## Tools

```sh
sudo pacman -S --needed git python android-tools libusb
git clone https://github.com/bkerler/mtkclient && cd mtkclient
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
sudo groupadd -f plugdev && sudo usermod -aG plugdev,uucp $USER
sudo cp Setup/Linux/*.rules /etc/udev/rules.d/ && sudo udevadm control -R && sudo udevadm trigger
# log out and back in
sudo systemctl stop ModemManager      # while flashing; start it again afterwards
```

Plus **SP Flash Tool V5** (Linux build).

**Entering BROM mode** (needed for every mtkclient command and for SP Flash
Tool): tablet off and unplugged → start the command → hold **Vol+ and Vol−**
→ plug in USB.

In shell commands, use `$HOME/...` rather than `~/...` after a comma —
the shell only expands `~` at the start of a word.

## 1. Back up (once, before anything else)

```sh
python mtk.py rl $HOME/x306f-backup --skip=userdata
python mtk.py rf $HOME/x306f-backup/boot1.bin --parttype=boot1
cd $HOME/x306f-backup && sha256sum * > SHA256SUMS
```

`nvram.bin` (Wi-Fi/Bluetooth MAC addresses, calibration) and `proinfo.bin`
(serial number) are unique to this tablet. Keep copies off the PC.

## 2. Flash the S100152 base with SP Flash Tool — FORMAT ALL

The tablet's flashing protection (DAA) is handled by Lenovo's own files in
the firmware zip, so no exploit is needed.

- Download-Agent: `MTK_AllInOne_DA_6765.bin`
- Authentication file: `auth_sv5.auth`
- Scatter: `MT6765_Android_scatter.txt`
- Mode: **Format All + Download**

This must be a real FORMAT ALL with SP Flash Tool. A partial wipe with
mtkclient (everything except nvram/seccfg/proinfo/preloader), plus recovery's
Format data, led to a boot loop with `enablefilecrypto_failed`.

## 3. Unlock and write LineageOS recovery (mtkclient)

FORMAT ALL re-locks the bootloader, so SP Flash Tool refuses to write
the unsigned LineageOS recovery (`STATUS_ERR (-1073676287)`). Use mtkclient:

```sh
python mtk.py da seccfg unlock
python mtk.py r seccfg $HOME/seccfg_now.bin && xxd -s 12 -l 4 $HOME/seccfg_now.bin   # 0300 0000 = unlocked

unzip -j lineage-23.2-*.zip recovery.img -d $HOME/lineage-recovery/
python mtk.py w recovery,nvram,proinfo $HOME/lineage-recovery/recovery.img,$HOME/x306f-backup/nvram.bin,$HOME/x306f-backup/proinfo.bin
```

## 4. Install

1. Unplug, hold **Power + Vol+** → LineageOS recovery (after the "Orange
   state" warning, which is normal when unlocked).
2. **Apply update → Apply from ADB**, then
   `adb sideload lineage-23.2-...-amar_row_lte.zip`
   (the PC side stopping at ~47% is normal).
3. **Reboot system now.** Do **not** Format data: FORMAT ALL already
   flashed a clean `userdata`.
4. The first boot sits on the LineageOS logo for several minutes.

Check afterwards: Wi-Fi/Bluetooth addresses are real (not
`02:00:00:00:00:00`) and the serial is correct. Set **Settings → Battery**
charge limit to 80%.

## Troubleshooting

**Boot loops back to recovery asking to format data.** Read the reason and
vold's log from recovery (**Advanced → Enable ADB**):

```sh
rm -rf pstore
adb shell cat /tmp/recovery.log | grep 'reason='
adb shell 'mount -t pstore pstore /sys/fs/pstore'
adb pull /sys/fs/pstore ./pstore
strings pstore/pmsg-ramoops-0 | grep -iE -A3 'vold.*(fail|unable|error)|Falling back'
```

`enablefilecrypto_failed` / `Unable to find device keyring` meant the
FORMAT ALL step hadn't been done properly. Redo steps 2–4.

**Back to stock.** Use SP Flash Tool with the S120637 firmware (FORMAT ALL +
Download), then restore `nvram` and `proinfo` with mtkclient as in step 3.

## Updates

LineageOS updates come through **Settings → System → Updater** from the
maintainer's server. Before a major version jump, check their Telegram
group for X306F reports.

## Apps without Google

- Fully Kiosk Browser: APK from <https://www.fully-kiosk.com>,
  `adb install <file>.apk` (the Plus licence works without the Play Store).
- Home Assistant: the F-Droid build of the companion app.
- WebView is updated with LineageOS itself.
