# Installing the dashboard in Home Assistant

One-time setup, about 20 minutes. After this, updates are a `git pull`.

## 1. Install the add-ons from HACS

In **HACS**, search for and download:

| Name | Type | Why |
|------|------|-----|
| **auto-entities** | Dashboard | Lists that fill themselves (low batteries, soil sensors, what's playing) |
| **Kiosk Mode** | Dashboard | Hides the sidebar and menus on the tablet |
| **mini-graph-card** | Dashboard | The garden beds' colour-shaded moisture graphs |

Restart Home Assistant. (Browser Mod is no longer needed: light/dark
switching uses Home Assistant's own default theme. If you installed it
earlier, you can remove it.)

## 2. Make sure there's a weather entity

The dashboard uses `weather.forecast_home`. If you don't have it, add
**Settings → Devices & services → Add integration → Meteorologisk institutt
(Met.no)**. If you already use a different weather integration, replace
`weather.forecast_home` in `dashboard/views/home.yaml` and
`dashboard/views/outdoors.yaml`.

## 3. Put this repo on your Home Assistant

Install the **Studio Code Server** add-on (or **Terminal & SSH**), open its
terminal, and run:

```sh
cd /config
git clone https://github.com/ben-hawks/ha-dashboard.git
```

If the repo is private, use a GitHub personal access token as the password,
or download the repo as a ZIP and upload the folder to `/config/ha-dashboard`
with Studio Code Server.

## 4. Add to `configuration.yaml`

Merge these into `/config/configuration.yaml`. If you already have a
`homeassistant:`, `frontend:` or `lovelace:` section, add the lines under the
existing one rather than creating a second.

```yaml
homeassistant:
  # One line per file in ha-dashboard/packages/. (`packages: !include_dir_named
  # ha-dashboard/packages` also works and picks up new files on its own, but
  # the Studio Code Server extension flags it with a schema warning.)
  packages:
    wall_tablet: !include ha-dashboard/packages/wall_tablet.yaml
    garden: !include ha-dashboard/packages/garden.yaml

frontend:
  themes: !include_dir_merge_named ha-dashboard/themes

lovelace:
  dashboards:
    wall-tablet:
      mode: yaml
      filename: ha-dashboard/dashboard/dashboard.yaml
      title: Wall Tablet
      icon: mdi:tablet-dashboard
      show_in_sidebar: true
      require_admin: false
    chicken-coop:
      mode: yaml
      filename: ha-dashboard/dashboard/chicken_coop.yaml
      title: Chicken Command Center
      icon: mdi:egg
      show_in_sidebar: true
      require_admin: false
```

(If you already load themes from another folder, keep that line and copy
`themes/wall_tablet.yaml` into it instead.)

Go to **Developer Tools → YAML → Check configuration**, then restart.

## 5. Create the tablet's user

**Settings → People → Add person**: name it "Wall Tablet", turn on **Allow
login**, leave **Administrator** off, and turn on **Can only log in from the
local network**. Non-admin users get the locked-down kiosk view; your own
admin account still sees the sidebar and menus.

Then follow [tablet-setup.md](tablet-setup.md).

## Updating later

```sh
cd /config/ha-dashboard && git pull
```

- Dashboard changes (`dashboard/`): Home Assistant only notices when
  `dashboard.yaml` itself changes, not the `views/` files it includes. On
  your admin account open the dashboard, click the pencil, then **⋮ →
  Refresh**, or run `touch dashboard/dashboard.yaml`. Then refresh the
  tablet.
- Package changes (`packages/`): **Developer Tools → YAML → All YAML
  configuration**, or restart.
- Theme changes (`themes/`): **Developer Tools → YAML → Themes**.

## Weather radar

The radar on **Outdoors** is a small page, `www/radar.html`, that centres
Windy's radar map on your **Home** zone. Home Assistant only serves files
from `/config/www`, so copy it there once (and again if it ever changes):

```sh
mkdir -p /config/www && cp /config/ha-dashboard/www/radar.html /config/www/
```

If `/config/www` didn't exist before, restart Home Assistant once so it
starts serving the folder. Map zoom and which forecast conditions bring the
radar up by themselves are `RADAR_ZOOM` and `STORMY` near the top of
`tools/weather.py`.
