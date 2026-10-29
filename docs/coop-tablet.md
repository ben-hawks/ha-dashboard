# Chicken Command Center (coop tablet)

A one-screen dashboard at `/chicken-coop/coop`: three live coop cameras and a
panel of controls and sensors in a 2×2 grid. Feeds are 16:9 and each takes a
quarter of the screen (about 640×360 on a 1280×800 tablet).
A single stacked column of three would only fit about 505×284 per feed.

## What's on it

| Quadrant | Content |
|----------|---------|
| Top left | Coop Cam 1 (live), motion icon |
| Top right | Coop Cam 2 (live), motion icon |
| Bottom left | Chicken Run (live), motion icon |
| Bottom right | Outside temperature, then every light, switch, door (cover) and lock in the **Chicken Coop** area, then its temperature and humidity sensors |

Tap a feed to open it full screen. The controls and sensors fill themselves
in from the area, so when the automatic door or heat lamp is added, put it in
the **Chicken Coop** area and it appears.

## Home Assistant side

1. Add the `chicken-coop` block from [install.md](install.md) step 4 to
   `configuration.yaml` and restart.
2. Check the camera entity IDs: **Settings → Entities**, search "chicken",
   and compare with the three `camera.` lines in
   `dashboard/chicken_coop.yaml`.
3. **Enable the low-resolution streams** the dashboard uses: Settings →
   Devices & services → UniFi Protect → each camera → its **Low resolution
   channel** entity is disabled by default; enable it. (About 640×360, the
   size of one quarter of the screen; much lighter for the tablet to decode
   than the full-resolution stream.)
4. The tablet can share the **Wall Tablet** user, or have its own non-admin
   user. Either way it gets no sidebar or header.

## Android tablet setup (Fully Kiosk)

Same base as the wall tablet: follow [tablet-setup.md](tablet-setup.md)
(Android prep, landscape lock, Fully Kiosk Plus). Differences:

| Setting | Value |
|---------|-------|
| Web Content → **Start URL** | `http://<HA-IP>:8123/chicken-coop/coop` |
| Browser Mod **Browser ID** | `coop_tablet` (the theme automation targets it) |
| Device Management → **Keep Screen On** | On |
| Device Management → **Launch on Boot** | On |
| Web Auto Reload → **Auto Reload on Network Reconnect** | On |
| Motion detection / screensaver | Off: the feeds should always be on screen |

### Keeping a slow tablet happy

- **Streams:** use the low-resolution channels (step 3 above). If the feeds
  still stutter or the tablet runs hot, change `camera_view: &camera_view
  live` to `auto` in `dashboard/chicken_coop.yaml`. The feeds then become
  stills refreshed every 10 seconds, which costs almost nothing.
- **WebView:** keep it updated (LineageOS updates it with the system; on
  stock Android, update **Android System WebView** in the Play Store).
  Newer versions decode video in hardware more reliably.
- **Nightly reload:** hours of live video can slowly eat a 2 GB tablet's
  memory. Add the **Fully Kiosk Browser** integration for this tablet and
  reload the page once a night:

  ```yaml
  automation:
    - alias: "Coop tablet: nightly reload"
      triggers:
        - trigger: time
          at: "03:30:00"
      actions:
        - action: button.press
          target:
            entity_id: button.coop_tablet_load_start_url   # check the name under the tablet's device
  ```

- **Nothing else running:** don't install other apps; no Google sign-in.

## Alternative: Surface Go 2 (CachyOS)

The earlier plan, kept in case the coop screen moves to the Surface. On a
faster machine the full-resolution channels work too.

### Setup

The kiosk is **cage** (a minimal Wayland compositor that runs one app full
screen) running **Chromium**, started at boot by **greetd** as a dedicated
`kiosk` user. No desktop and no screensaver; if Chromium crashes, it restarts.

### 1. Firmware (before installing)

Hold **Volume Up** while powering on to open Surface UEFI:
- **Boot configuration → Advanced options → Battery Limit**: on. Caps the
  charge at 50%, since it'll be plugged in permanently.
- **Security → Secure Boot**: disable it if the CachyOS installer won't boot.

Install CachyOS normally (any desktop; it gets bypassed). Connect to Wi-Fi in
the installer and make the connection available to all users.

### 2. Packages

```sh
sudo pacman -S --needed cage chromium greetd intel-media-driver libva-utils
vainfo | head -5        # should list the Intel iHD driver: hardware video decode
```

Touch, Wi-Fi and the Type Cover work on the stock kernel. If touch doesn't,
install the [linux-surface](https://github.com/linux-surface/linux-surface)
kernel.

### 3. Kiosk user and launcher

```sh
sudo useradd -m kiosk
sudo tee /usr/local/bin/coop-kiosk >/dev/null <<'SH'
#!/bin/sh
# First run: set URL to http://<HA-IP>:8123/browser-mod, log in and register
# the browser, then change it back.
URL="http://<HA-IP>:8123/chicken-coop/coop"
while true; do
  chromium --kiosk "$URL" \
    --ozone-platform=wayland \
    --force-device-scale-factor=1.5 \
    --enable-features=AcceleratedVideoDecodeLinuxGL,VaapiVideoDecoder \
    --password-store=basic \
    --no-first-run --noerrdialogs --disable-session-crashed-bubble \
    --autoplay-policy=no-user-gesture-required
  sleep 2
done
SH
sudo chmod +x /usr/local/bin/coop-kiosk
```

Replace `<HA-IP>` (use the IP, not `homeassistant.local`).
`--password-store=basic` stops Chromium waiting on a keyring prompt that
nobody can see.

### 4. Start it at boot

`/etc/greetd/config.toml`:

```toml
[terminal]
vt = 1

[initial_session]
command = "cage -s -- /usr/local/bin/coop-kiosk"
user = "kiosk"

[default_session]
command = "agreety --cmd bash"
user = "greeter"
```

```sh
sudo systemctl disable sddm       # or whichever display manager CachyOS installed
sudo systemctl enable greetd
```

### 5. Never sleep

```sh
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
sudo mkdir -p /etc/systemd/logind.conf.d
printf '[Login]\nHandleLidSwitch=ignore\nHandleLidSwitchExternalPower=ignore\nHandlePowerKey=ignore\n' \
  | sudo tee /etc/systemd/logind.conf.d/kiosk.conf
```

The lid switch matters: folding the Type Cover over the screen counts as
closing a lid.

### 6. First boot: log in and register

1. In `/usr/local/bin/coop-kiosk`, temporarily set
   `URL="http://<HA-IP>:8123/browser-mod"`, then reboot.
2. With the Type Cover attached, log in as the tablet user (tick **Keep me
   logged in**). Set Browser ID to `coop_tablet` and tick **Register**.
3. Switch to another console (**Ctrl+Alt+F2**), log in as yourself, put the
   URL back to `/chicken-coop/coop`, and reboot.

Chromium keeps the login and the Browser Mod ID in `/home/kiosk`, so they
survive reboots.

### Day to day

- **Get to a console:** Ctrl+Alt+F2 (Type Cover attached).
- **Reload the page:** `sudo pkill -u kiosk chromium` from a console, or over
  SSH; the loop restarts it.
- **Too big or small:** change `--force-device-scale-factor` (1.5 gives the
  1280×853 layout the dashboard is sized for; 1.6 shrinks things a little if
  the page scrolls).
- **Updates:** CachyOS is rolling-release. Update when you're around to check
  it comes back (`sudo pacman -Syu`, reboot), not automatically.
