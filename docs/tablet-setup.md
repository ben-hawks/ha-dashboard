# Setting up the Lenovo tablet (TB-X306F)

The Tab M10 HD is a modest tablet, so the dashboard sticks to built-in cards
that render quickly. These steps keep it on the dashboard 24/7.

The tablet runs LineageOS without Google apps (see
[lineageos.md](lineageos.md)). On stock Android the steps are the same, except
that apps come from the Play Store.

## 1. Prepare Android

1. **Settings → System → Updater** (LineageOS) or **System update** (stock):
   install everything. On LineageOS this also updates WebView, which Fully
   Kiosk uses to draw the dashboard.
2. **Settings → Battery**: turn on the charge limit (80%). A tablet that's
   always plugged in ages its battery quickly otherwise.
3. **Settings → Security → Screen lock**: None.
4. **Developer options → USB debugging**: on, for installing apps with `adb`.

## 2. Fully Kiosk Browser

Download the APK from <https://www.fully-kiosk.com> and install it with
`adb install <file>.apk` (on stock Android, the Play Store works too). Buy the
**Plus** licence (one-time, per device). It's needed for kiosk lock, motion
wake, and the Home Assistant integration.

In Fully's settings:

| Setting | Value |
|---------|-------|
| Web Content → **Start URL** | `http://<your-HA-IP>:8123/wall-tablet/home` |
| Device Management → **Keep Screen On** | On |
| Device Management → **Launch on Boot** | On |
| Web Auto Reload → **Auto Reload on Network Reconnect** | On |
| Web Browsing → **Pull to Refresh** | On |
| Remote Administration → **Enable** | On, with a password |
| Kiosk Mode → **Enable Kiosk Mode** | On, with a PIN (do this last) |

Optional: **Motion Detection** → turn the screen on when someone walks up
(uses the front camera; nothing is recorded).

If tiles look cramped or too big, adjust **Web Zoom and Scaling → Initial
scale** (try 90–110%).

## 3. Log in and register the tablet

1. On the tablet, log in as the **Wall Tablet** user and tick
   **Keep me logged in**.
2. Go to `http://<your-HA-IP>:8123/browser-mod`, tick **Register**, and
   set **Browser ID** to `wall_tablet` exactly. The light/dark automation
   targets this ID.
3. Go back to the start URL.

## 4. Connect Fully Kiosk to Home Assistant

**Settings → Devices & services → Add integration → Fully Kiosk Browser**,
using the tablet's IP and the remote admin password. This adds the tablet's
screen brightness, screen on/off, and a reload button to Home Assistant, so
automations can dim it at night or wake it when the doorbell rings.

## Light and dark mode

The **Theme** control at the bottom of the **Devices** tab has three
settings:

- **Auto**: light during the day, dark after sunset (default).
- **Dark** / **Light**: stays that way.
