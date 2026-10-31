# Frigate on the Arc server

Frigate watches the three chicken cameras, looks for hens with the Arc
card, records, and tells Home Assistant what it sees. It's step 2 of the
coop headcount plan. For now it builds up footage and gives HA live bird
counts per camera; the door counter comes later.

Everything is in [`frigate/`](../frigate):

| File | What it is |
|------|------------|
| `docker-compose.yml` | The container: Frigate 0.18.2, the GPUs, storage, ports |
| `.env.example` | Camera stream ids, MQTT login, storage path. Copy to `.env` |
| `config/config.yml` | Frigate's config: detection on the Arc, the three cameras, recording |
| `export-yolov9.sh` | Builds the better detection model (step 7) |

## 1. What the server needs

- Linux with Docker and Docker Compose.
- The Arc's drivers come with the kernel. 6.5 or newer is best: Frigate's
  GPU graphs need it, and Arc B-series cards need 6.12 or newer.
  `ls /dev/dri` should list a `renderD…` entry per GPU.
- Disk space for recordings: see [Storage](#storage).

## 2. Turn on the camera streams in Protect

For each of Chicken Cam 1, Chicken Cam 2 and Chicken Run: **Protect → the
camera → Settings → Advanced → RTSP**, and turn on **High** and **Medium**.
Each shows an address like
`rtsps://192.168.1.1:7441/AbCdEf123?enableSrtp`. The part between the last
`/` and the `?` (here `AbCdEf123`) is the stream id that goes in `.env`.

High is recorded. Medium (usually 720p) is what Frigate looks for hens in:
enough detail for a hen across the run, and much lighter than High.

## 3. MQTT in Home Assistant

Frigate talks to Home Assistant over MQTT. If the Yellow doesn't run it
already:

1. **Settings → Add-ons → Add-on store → Mosquitto broker** → Install →
   Start.
2. **Settings → People → Users → Add user**: `frigate`, with a password.
   Mosquitto accepts Home Assistant logins.
3. **Settings → Devices & services**: the MQTT integration appears as
   discovered; add it.

## 4. Start Frigate

On the server, copy the `frigate/` folder somewhere (or clone this repo),
then in that folder:

```bash
cp .env.example .env
```

Fill in `.env`: the Protect console's address, the six stream ids, the MQTT
login, and where recordings go (`STORAGE_PATH`).

```bash
docker compose up -d
```

```bash
docker compose logs frigate | grep -i password
```

That prints the admin password, created on first start.

**With Portainer instead:**

1. Put `config/config.yml` in a folder on the server, e.g.
   `/srv/frigate-config/config.yml`.
2. Fill in a copy of `.env.example`. Set `CONFIG_PATH` to that folder and
   `STORAGE_PATH` to a full path too. Portainer doesn't keep the stack's
   files in a folder of yours, so relative paths like `./config` end up
   inside Portainer's own storage.
3. **Stacks → Add stack → Web editor**: paste `docker-compose.yml`. Under
   **Environment variables**, **Load variables from .env file** and pick the
   filled-in copy. Deploy.
4. The admin password is in **Containers → frigate → Logs**; search for
   "password".

Portainer's environment variables only reach Frigate through the
`environment:` list in `docker-compose.yml`. If you change one later, use
**Update the stack**; restarting the container keeps the old values. A
missing one stops the deploy with "required variable FRIGATE_… is missing
a value".

Then open
`http://<server>:8971`: plain http, because TLS is off in the config so
Home Assistant can connect (step 6). Log in as `admin`, change the
password (**Settings → Users**), and the three cameras should be live
within a minute.

**`SSL_ERROR_RX_RECORD_TOO_LONG` or a similar SSL error** means the
browser is using https. Check the address starts with `http://`. If the
browser keeps switching it back to https, it's remembering an instruction
Frigate sent while TLS was on: Frigate tells browsers to use only https for
that server for two years. Clear it (Firefox: **History → Manage History**,
right-click the server → **Forget About This Site**; Chrome or Edge:
`chrome://net-internals/#hsts` → **Delete domain security policies**), or
use the server's IP address, which browsers don't apply this to. It
applies to the whole server name, so other plain-http services on that
server are affected too until you clear it.

If a camera stays black, check **Settings → System → Logs → go2rtc**. A
literal `{FRIGATE_…}` in an address means that variable is missing from
`.env`. "401" or "404" means the stream id is wrong, or that stream isn't
turned on in Protect.

## 5. Check the Arc is doing the work

In **System metrics**:

- **Detectors**: `arc` should show an inference speed of roughly 5–15 ms.
  Over 50 ms means it's running on the CPU, not the Arc.
- **GPUs**: the Arc should show load (decoding and detection).

If the server also has an integrated GPU, Frigate may have picked that one.
List what OpenVINO sees:

```bash
docker exec frigate python3 -c "import openvino as ov; c = ov.Core(); print({d: c.get_property(d, 'FULL_DEVICE_NAME') for d in c.available_devices})"
```

If the Arc is `GPU.1`, set `device: GPU.1` under `detectors` in
`config/config.yml`. Also add `gpu: 1` under `ffmpeg` so video decoding
moves to the Arc too. Then:

```bash
docker compose restart frigate
```

## 6. Home Assistant

1. **HACS → search "Frigate" → Download**, then restart Home Assistant.
   The Frigate card is also on HACS, for the dashboard.
2. **Settings → Devices & services → Add integration → Frigate**, URL
   `http://<server>:8971`. Create a user for it in Frigate first
   (**Settings → Users**) and give the integration that login. TLS is off in
   the config so HA can use plain HTTP on the LAN, and port 8971 still needs
   a login. If your version of the integration doesn't ask for a login, use
   port 5000 instead: add `- "5000:5000"` to the ports in
   `docker-compose.yml`. Port 5000 has no login, so keep it off anything
   outside the LAN.
3. You get, per camera, a live **bird count** sensor (and cat, dog,
   person), motion and occupancy sensors, and Frigate's camera views. These
   are the first building blocks for the flock status.

## 7. Which camera sees the door

In `config/config.yml`, under that camera, add:

```yaml
    detect:
      fps: 10
```

Following hens through the door needs more frames than spotting them in
the run. Later, a **door zone** goes on that camera (**Settings → Masks /
Zones**, drawn over the pop door and ramp), which gives HA a count of hens
at the door.

## If a camera is offline when Frigate starts

Frigate asks each camera for its picture size when it starts. If a camera
doesn't answer, Frigate falls back to a default size until the next
restart, which can squash that camera's picture. Since the cameras drop out
now and then, write the sizes in once they're known. With the camera
online, this prints its Medium stream's size (swap in each camera's name):

```bash
docker exec frigate /usr/lib/ffmpeg/8.0/bin/ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 rtsp://127.0.0.1:8554/chicken_run_detect
```

Add it under each camera in `config/config.yml`, e.g.:

```yaml
    detect:
      width: 1280
      height: 720
```

## 8. Better detection: YOLOv9

The model built into Frigate gets things going, but it misses a lot: given
a photo of eight birds perched together, it found three. YOLOv9 is better
at small and bunched-up birds.

`frigate/export-yolov9.sh` builds it. It only needs `docker run`, so it
works in the TrueNAS shell (**System → Shell**). Copy the script anywhere on
the server, e.g. next to the config folder, and point `CONFIG_PATH` at the
folder holding Frigate's `config.yml`, the same folder as in the Portainer
stack:

```bash
sudo CONFIG_PATH=/mnt/tank/apps/frigate/config bash export-yolov9.sh
```

(With the docker compose command, run it from the `frigate/` folder without
`CONFIG_PATH`; it uses `config/` there.)

That builds `yolov9-s` at 320×320 into `model_cache/yolo.onnx` inside the
config folder. It takes 5–15 minutes, once, and a few GB of Docker space
while it runs. Afterwards only the `python:3.11` image is left, which
`sudo docker image rm python:3.11` removes. Then replace the `model:` block
in `config.yml` with:

```yaml
model:
  model_type: yolo-generic
  width: 320
  height: 320
  input_tensor: nchw
  input_dtype: float
  path: /config/model_cache/yolo.onnx
  labelmap_path: /labelmap/coco-80.txt
```

```bash
docker compose restart frigate
```

The Arc can manage a bigger model: add `c 320` to the end of the command, keeping an
eye on **System metrics** for skipped detections. 320 is Frigate's
recommended size, because Frigate already zooms in on wherever there's
motion before it looks.

## Storage

| | Kept |
|-|------|
| Continuous recording | 3 days |
| Anything with motion | 14 days |
| Anything with a hen, cat, dog or person | 30 days |
| Snapshots | 30 days |

Protect's High streams run at a few Mbit/s. At 4 Mbit/s a camera writes
about 1.8 GB an hour, so three days of continuous recording for three
cameras is roughly 400 GB, plus the motion and detection footage. After a
day, **System metrics → Storage** shows the real rate per camera. Change
`continuous: days:` in `config/config.yml` to fit the disk. Frigate
deletes the oldest recordings first if the disk fills up.

## Footage for the feasibility test

Frigate's recordings are where clips for
[the feasibility test](chicken-vision-test.md) come from. In the Frigate
UI, find a bedtime on the door camera's timeline, then **Export** the
range. Exports land in `$STORAGE_PATH/exports`, ready for
`tools/chicken_vision_test.py`. Detect and record streams also come out
of Frigate's restream, `rtsp://<server>:8554/chicken_run_detect`, for
running the test live.

## Updating Frigate

Read the release notes (github.com/blakeblackshear/frigate/releases) for
config changes, change the image tag in `docker-compose.yml`, then:

```bash
docker compose pull
```

```bash
docker compose up -d
```
