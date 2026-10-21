# Setting up the Lenovo tablet (TB-X306F)

The Tab M10 HD is a modest tablet, so the dashboard sticks to built-in cards
that render quickly. These steps keep it on the dashboard 24/7.

## 1. Prepare Android

1. **Settings → System → System update**: install everything.
2. **Play Store**: update **Android System WebView** and **Chrome**.
   Fully Kiosk uses WebView to draw the dashboard, and older versions break
   newer Home Assistant cards.
3. **Settings → Battery**: if there's a **Battery protection** /
   **Conservation mode** option, turn it on. A tablet plugged in forever
   ages its battery fast; this caps the charge level.
4. **Settings → Security → Screen lock**: None.

## 2. Fully Kiosk Browser

Install **Fully Kiosk Browser** from the Play Store and buy the **Plus**
licence (one-time, per device). It's needed for kiosk lock, motion wake, and
the Home Assistant integration.

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
