# Chicken Command Center (Surface Go 2)

A one-screen dashboard at `/chicken-coop/coop`: three live coop cameras and a
panel of controls and sensors in a 2×2 grid. Feeds are 16:9 and each takes a
quarter of the screen (about 640×360 at the Surface's default 150% scaling).
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
3. Optional, lighter streams: in the UniFi Protect device page for each
   camera, enable **Medium resolution channel** and use those entities
   instead.
4. The tablet can share the **Wall Tablet** user, or have its own non-admin
   user. Either way it gets no sidebar or header.

## Surface Go 2 setup (Windows)

1. **Power:** Settings → System → Power & battery → Screen and sleep:
   **Never** when plugged in.
2. **Battery:** it'll be plugged in all the time. Turn on **Battery Limit**
   in Surface UEFI (hold Volume Up while powering on → Boot configuration →
   Advanced options), which caps the charge at 50%.
3. **Rotation:** hold it in landscape and turn on **Rotation lock** in Quick
   Settings.
4. **Sign in automatically:** Settings → Accounts → Sign-in options: turn off
   "only allow Windows Hello sign-in", then run `netplwiz` and untick
   "Users must enter a user name and password".
5. **Updates:** Settings → Windows Update → Advanced → set **Active hours**
   so it doesn't restart while you're watching.
6. **Log in once:** open Edge normally, go to
   `http://<HA-IP>:8123/chicken-coop/coop`, log in as the tablet user with
   **Keep me logged in**.
7. **Browser Mod:** in the same Edge, open `http://<HA-IP>:8123/browser-mod`,
   set Browser ID to `coop_tablet` and tick Register. The theme automation
   then switches this screen along with the wall tablet.
8. **Start full screen on boot:** press Win+R, type `shell:startup`, and
   create a shortcut there with this target:

   ```
   "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --kiosk http://<HA-IP>:8123/chicken-coop/coop --edge-kiosk-type=fullscreen --no-first-run
   ```

   This uses your normal Edge profile, so the login and Browser Mod ID stick.
   (Windows' built-in "Kiosk" account uses a private browsing mode that
   forgets the login, so avoid it.)

To get out of kiosk mode: attach the keyboard and press **Alt+F4**.

If the feeds are slightly too tall and the page scrolls, lower Edge's zoom
(Ctrl+−, before step 8) or set Windows display scaling to 175%.
