# Chicken Command Center (coop tablet)

A one-screen dashboard at `/chicken-coop/coop`, sized for a 1280×800 tablet.

| Where | What |
|-------|------|
| Left, top | Coop Cam 1 and Coop Cam 2 side by side |
| Left, bottom | Chicken Run, wide |
| Right column | The animated coop scene, chicken comfort, controls, coop graphs |

Only one feed plays live video at a time (Chicken Run by day, Coop Cam 2 at
night); the others are stills that refresh every 10 seconds. Tap any feed to
open it live, full screen.

**Coop scene.** The coop (soft green, darker green trim) and run, with the sky
following the weather station: sun, drifting clouds, falling rain or snow,
the moon and twinkling stars at night. By day all nine hens are in the run,
each in her breed's colours, pecking and pottering. After sunset they're
silhouettes in the windows, with sleepy z's. The windows glow in the Coop
Light's colour and brightness.

**Chicken comfort.** A cartoon hen who's content, fluffed up in a scarf,
shivering, or panting, with a plain-language status, a tip and a meter from
0 °F to 100 °F. By day it uses the station's feels-like temperature (wind
chill and heat index included); at night the sensor inside the coop (with
a heat index when it's hot), falling back to the station if that sensor is
offline. Levels: Very cold < 10 °F, Chilly < 32 °F, Comfy up to 75 °F, Warm
up to 85 °F, Hot up to 95 °F, then Heat danger. A cold, damp coop (humidity
80% or more below 40 °F) gets a ventilation warning.

**Controls and graphs.** Every light, switch, door and lock in the Chicken
Coop area, so the automatic door appears once it's in that area; coop
temperature (with the outside temperature as a faint line) and humidity.

To change the flock, colours or comfort levels, edit `tools/coop.py` and run
`python3 tools/coop.py`.

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
| Device Management → **Keep Screen On** | On |
| Device Management → **Launch on Boot** | On |
| Web Auto Reload → **Auto Reload on Network Reconnect** | On |
| Motion detection / screensaver | Off: the feeds should always be on screen |

### Keeping a slow tablet happy

- **Streams:** use the low-resolution channels (step 3 above), and only one
  plays live: Chicken Run while the sun is up, Coop Cam 2 after sunset. To
  change which, edit the `conditional` cards in
  `dashboard/chicken_coop.yaml` (each switching feed has a live and a still
  version). If even one live feed stutters, set its `camera_view` to `auto`
  too.
- **Frame rate:** some UniFi models let you lower the frame rate (camera
  Settings → Advanced), which halves the decoding work at 15 fps. Many
  models, including ours, don't offer it.
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
# First run: log in once (Type Cover attached), ticking "Keep me logged in".
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

### 6. First boot: log in

With the Type Cover attached, log in as the tablet user and tick **Keep me
logged in**. Chromium keeps the login in `/home/kiosk`, so it survives
reboots. The light/dark theme follows Home Assistant's default theme, so
there's nothing else to register.

### Day to day

- **Get to a console:** Ctrl+Alt+F2 (Type Cover attached).
- **Reload the page:** `sudo pkill -u kiosk chromium` from a console, or over
  SSH; the loop restarts it.
- **Too big or small:** change `--force-device-scale-factor` (1.5 gives the
  1280×853 layout the dashboard is sized for; 1.6 shrinks things a little if
  the page scrolls).
- **Updates:** CachyOS is rolling-release. Update when you're around to check
  it comes back (`sudo pacman -Syu`, reboot), not automatically.
