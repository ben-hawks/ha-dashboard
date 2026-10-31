# The hen model

A detection model trained on our own cameras, to replace Frigate's stock
model on the chicken cameras. The stock model has never seen a chicken
labelled as one. It calls hens "bird", misses bunched-up ones, and
struggles on night vision. A model trained on a few hundred of our own
frames (day, dusk and night, from all three cameras) is the biggest single
improvement to the coop headcount.

It knows the classes in [`hen_model/classes.yaml`](../hen_model/classes.yaml):

| Class | Why |
|-------|-----|
| hen | the point of it all |
| person | Frigate uses one model for every camera, so it must still see people |
| cat, dog, fox, raccoon, skunk | predators on the ground |
| raptor | hawks, owls and eagles |

Once labelling has started, only ever **add** classes, at the end of the
list. Reordering or removing one scrambles every label already made.
Opossum or coyote can be added later if they turn up.

## How it fits together

| Where | What runs there |
|-------|-----------------|
| **TrueNAS** | Frigate (records, keeps 3 days of continuous footage), Label Studio (where boxes get drawn), a `hens` dataset holding the frames, shared over SMB, and a **daily harvest** that copies frames out of Frigate before they expire |
| **Training machine** (with an NVIDIA GPU) | The other Python scripts in `hen_model/`, with the `hens` share mounted |

Harvesting runs on TrueNAS because it can't wait: Frigate deletes
continuous footage after 3 days, so a week with the training machine off
would lose a week of frames. Everything else can wait until you sit down
to it.

The loop, each round:

1. **harvest.py** pulls frames out of Frigate into the share, every night
   on TrueNAS.
2. **prelabel.py** has YOLOE, a model you can ask for things by name, draw
   first-guess boxes, and sends the frames to Label Studio.
3. **You** fix the boxes in Label Studio.
4. **dataset.py** turns the finished labels into a training set.
5. **train.py** trains, exports `hens.onnx`, and writes the Frigate config
   lines.
6. Frigate runs the new model. Frames where it gets things wrong go into
   the next round.

## One-time setup

### On TrueNAS

1. **A dataset for the frames**: e.g. `tank/hens`, shared over SMB
   (**Shares → SMB → Add**). Mount it on the training machine.
2. **A dataset for Label Studio's own database**: e.g.
   `tank/apps/label-studio`. Label Studio runs as user 1001, so in
   **System → Shell**:

   ```bash
   sudo chown -R 1001:1001 /mnt/tank/apps/label-studio
   ```

3. **Label Studio in Portainer**: **Stacks → Add stack**, paste
   [`hen_model/label-studio/docker-compose.yml`](../hen_model/label-studio/docker-compose.yml),
   and add the environment variables:

   | Variable | Example |
   |----------|---------|
   | `LS_DATA_PATH` | `/mnt/tank/apps/label-studio` |
   | `HENS_PATH` | `/mnt/tank/hens` |
   | `LS_USERNAME` | your email address (the first login) |
   | `LS_PASSWORD` | a password for it |

   Deploy, then open `http://<truenas>:8085` and log in.
4. **An access token for the scripts**: in Label Studio, your avatar (top
   right) → **Account & Settings → Personal Access Token → Create**. Copy
   it somewhere safe. Label Studio 1.23 has the older "legacy" tokens
   switched off, so it has to be this kind.
5. **A Frigate user for harvesting**: in Frigate, **Settings → Users → Add**,
   role **viewer**.
6. **The harvester in Portainer.** It's a small container that copies
   frames out of Frigate every night. Find the `hens` folder's owner (the
   two numbers by `hens`, e.g. `3000 3000`):

   ```bash
   ls -ln /mnt/tank
   ```

   Then **Stacks → Add stack → Repository**:

   | Field | Value |
   |-------|-------|
   | Repository URL | `https://github.com/ben-hawks/ha-dashboard` |
   | Repository reference | `refs/heads/main` |
   | Compose path | `hen_model/harvester/docker-compose.yml` |

   and add the environment variables:

   | Variable | Example | |
   |----------|---------|-|
   | `HENS_PATH` | `/mnt/tank/hens` | the shared folder |
   | `HENS_OWNER` | `3000:3000` | its owner, from `ls -ln` |
   | `FRIGATE_USER` | `hens` | the login from step 5 |
   | `FRIGATE_PASSWORD` | | its password |
   | `HARVEST_AT` | `23:30` | when to run each day, in TrueNAS's time zone; several are fine, e.g. `12:00,23:30` |
   | `HARVEST_ARGS` | `--busy 06:30-08:30,17:00-19:30` | your let-out and bedtime windows, sampled more often |
   | `LABEL_STUDIO_URL` | `http://127.0.0.1:8085` | Label Studio on the same server; with the token, new frames are pre-labelled and sent there after each harvest |
   | `LABEL_STUDIO_TOKEN` | | the personal access token from step 4 |
   | `PRELABEL_THREADS` | `4` | CPU threads YOLOE may use (default 4), so it doesn't crowd out Frigate |
   | `PRELABEL_ARGS` | `--model yoloe-26s-seg.pt` | optional prelabel.py options |

   Deploy. Portainer builds the image from the repo, which takes a minute
   the first time. The harvester runs once straight away, so
   **Containers → hen-harvester → Logs** shows within a few minutes whether
   it reached Frigate and how many frames it added, then the time of the
   next run.

   **"Can't write to the hens folder"** in the logs comes with what the
   container saw and what to change. Most often on TrueNAS, the dataset
   belongs to root and an ACL decides who can write, which is normal for SMB
   datasets. In that case **Datasets →** the hens dataset **→ Permissions →
   Edit**, add the user whose uid is in `HENS_OWNER` (e.g. your own user,
   3000) with **Modify**, tick **Apply permissions recursively**, and save.
   Then restart the container.

   Each run looks back to the last one that worked (plus two hours of
   overlap), up to the 3 days Frigate keeps, so if the server was off for a
   day the next run catches up. To pick up changes to the code later, open
   the stack and **Pull and redeploy**. To have Portainer do that by itself,
   turn on **GitOps updates** on the stack (**Automatic updates** in older
   Portainer versions).

### On the training machine

Python 3.10 or newer. For an NVIDIA GPU, install PyTorch with CUDA first
(pytorch.org shows the command for your system), then:

```bash
python3 -m venv ~/hens
```

```bash
~/hens/bin/pip install ultralytics
```

Clone this repo (or copy `hen_model/` across). The commands below assume
the share is mounted at `/mnt/hens`, with `TRUENAS` standing in for the
server's address. Set the two secrets once per terminal so they stay out
of your shell history:

```bash
read -s FRIGATE_PASSWORD && export FRIGATE_PASSWORD
```

```bash
read -s LABEL_STUDIO_TOKEN && export LABEL_STUDIO_TOKEN
```

## Each round

### 1. Harvest frames

The harvester container does this every night on TrueNAS (setup step 6). Each run
samples each camera's recordings every 30 minutes, and every 5 minutes in
the busy windows: let-out and bedtime, when the light changes and the hens
crowd the door. It also takes the snapshot of every bird, person, cat and
dog detection. Frames nearly identical to one already kept are skipped, so
an empty run at noon gives a handful of frames, not fifty.

To harvest by hand from the training machine instead (for the busy
windows, use its own time zone):

```bash
~/hens/bin/python hen_model/harvest.py --frigate http://TRUENAS:8971 --user hens --out /mnt/hens --days 3
```

### 2. Pre-label and send to Label Studio

With `LABEL_STUDIO_URL` and `LABEL_STUDIO_TOKEN` set on the harvester
(setup step 6), this happens by itself: after each harvest, YOLOE draws
its guesses on the new frames and they appear in Label Studio's **Hen
model** project, which is created the first time. It runs on TrueNAS's
CPU, roughly a few seconds per frame, so a night's frames take a few
minutes, and needs about 1 GB of memory while it runs. The first time also downloads YOLOE (a few hundred MB), which is
then kept. The harvester's log shows how many boxes of each class it drew.

To run it by hand from the training machine instead (faster on a GPU, with
`--device 0`):

```bash
~/hens/bin/python hen_model/prelabel.py --data /mnt/hens --ls http://TRUENAS:8085
```

Either way, only frames not sent before are processed (the list is
`labelstudio/prelabelled.txt` in the share), so the two never send a frame
twice. Add `--limit 20` to try it on a few frames first.

### 3. Label

Open the **Hen model** project and click **Label All Tasks**. Each frame
arrives with YOLOE's guesses already drawn.

- **Fix, don't redraw.** Drag a box's edges to fit, change its class with
  the number keys (1 hen … 8 raptor, shown under the image), delete
  wrong boxes with Backspace, and draw missed ones.
- **Every hen gets a box**, including half-hidden ones; box the part you
  can see. Being consistent matters more than being perfect.
- **Wild birds are not hens.** Delete those boxes. That's how the model
  learns the difference.
- **Nothing in the frame?** Submit it with no boxes. Empty frames teach
  the model what "no hens" looks like.
- **Can't tell (too dark, too blurry)?** Skip it. Skipped frames stay out
  of the dataset.

Aim for 300–500 frames in the first round, spread over all three cameras
and including at least 100 from dusk and night. A frame takes 10–30
seconds once you're in the swing of it.

### 4. Build the dataset

```bash
~/hens/bin/python hen_model/dataset.py --data /mnt/hens --ls http://TRUENAS:8085
```

It prints how many frames and boxes went into training and validation.
About a fifth of the camera-hours are held back to check the model on,
grouped by hour, because frames minutes apart look nearly identical.

### 5. Train

```bash
~/hens/bin/python hen_model/train.py --dataset /mnt/hens/dataset
```

Training takes roughly 30–90 minutes on a mid-range NVIDIA GPU and stops
early once it stops improving. At the end it prints a score per class,
from 0 to 1: above 0.8 is good. The results land in
`/mnt/hens/models/hens-<date>/`, alongside charts of how training went in
`train/`.

### 6. Put it in Frigate

1. Copy `hens.onnx` and `hens-labels.txt` from the model folder into
   Frigate's `config/model_cache/`.
2. Open `frigate.yml` from the same folder. It has the `model:`, `objects:`
   and `review:` blocks for the new classes; replace those blocks in
   Frigate's `config.yml` with them.
3. Restart Frigate. In **System metrics** the `arc` detector should show
   an inference speed, and hens should start appearing as "hen" in
   **Review**.

Keep the old `model:` block in a comment, so going back is one edit.

### 7. Next round

Harvest again a few days later and label the new frames. Concentrate on
what the model got wrong: missed hens at the door, wild birds called hens,
night frames. Every round makes the next model better.

## Predators: public photos

Foxes, raccoons, skunks and raptors rarely show up on our cameras, so
there's little of our own footage to learn them from. `public.py`
downloads photos of them from Open Images, Google's public photo set with
boxes drawn by people. They go straight into the training set, with no
Label Studio pass. Once is enough; run it again only after changing the
classes:

```bash
~/hens/bin/python hen_model/public.py --data /mnt/hens --sheets
```

The first run reads Open Images' box lists (about 2 minutes, a 2.3 GB
download read on the fly and never stored), then downloads 200 photos per
class into `public/`. It picks only photos with no drawings, toys or boxes
round a whole group, and boxes every one of our classes in them: a dog
photo with a person in it gets both boxes.

How many photos Open Images has to choose from:

| Class | Usable photos |
|-------|---------------|
| dog | about 18,500 |
| cat | about 11,500 |
| raptor (eagle, falcon, owl) | about 2,800 |
| fox | about 420 |
| raccoon | about 280 |
| skunk | about 40 |

Skunk stays weak: 40 photos is thin, and there's nothing to add. Opossum
and coyote aren't in Open Images at all.

**Check the photos.** Open Images has mistakes; in testing, a
black-and-white cat was labelled skunk and a wolf fox. `--sheets` writes
contact sheets per class to `public/review/`, with each photo's file name
above it. Delete bad ones from `public/images/`. The next run notes them in
`public/rejected.txt`, never downloads them again, and tops the class back
up.

All of these are daytime photos, mostly close up. The model will still be
weaker on predators at night, on night vision, than on hens; the few real
predator visits the cameras do catch are the most valuable frames you can
label.

`dataset.py` adds the public photos to training automatically (leave them
out with `--no-public`). They're never used for the validation score,
which stays about our own cameras. 200 per class is a balance: many more
and the model spends its effort on Flickr photos rather than our coop.

## Files

| File | What it does |
|------|--------------|
| `hen_model/classes.yaml` | the classes, YOLOE's prompts for each, matching Open Images classes |
| `hen_model/harvest.py` | pulls frames out of Frigate into the share |
| `hen_model/harvester/` | the harvester container for Portainer: Dockerfile, compose file, daily schedule (harvest, then pre-label) |
| `hen_model/public.py` | downloads boxed predator photos from Open Images |
| `hen_model/prelabel.py` | YOLOE's first-guess boxes, sent to Label Studio |
| `hen_model/dataset.py` | Label Studio labels → YOLO training set |
| `hen_model/train.py` | trains, exports `hens.onnx`, writes the Frigate config lines |
| `hen_model/common.py` | shared code: the class list, Frigate and Label Studio clients |
| `hen_model/label-studio/docker-compose.yml` | the Label Studio stack for Portainer |

Ultralytics (training, YOLOE) is AGPL-licensed, which is fine for home use
like this.
