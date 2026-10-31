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
| **TrueNAS** | Frigate (records, keeps 3 days of continuous footage), Label Studio (where boxes get drawn), and a `hens` dataset holding the frames, shared over SMB |
| **Training machine** (with an NVIDIA GPU) | The Python scripts in `hen_model/`, with the `hens` share mounted |

The loop, each round:

1. **harvest.py** pulls frames out of Frigate into the share.
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

```bash
~/hens/bin/python hen_model/harvest.py --frigate http://TRUENAS:8971 --user hens --out /mnt/hens --days 3
```

It samples each camera's recordings every 30 minutes, and every 5 minutes
in the busy windows: let-out and bedtime, when the light changes and the
hens crowd the door. It also takes the snapshot of every bird, person, cat
and dog detection. Set `--busy` to your real times, in the training
machine's time zone, e.g. `--busy 06:30-08:30,17:00-19:30`. Frames nearly
identical to one already kept are skipped, so an empty run at noon gives a
handful of frames, not fifty. Run it every few days, because Frigate keeps
only 3 days of continuous footage.

### 2. Pre-label and send to Label Studio

```bash
~/hens/bin/python hen_model/prelabel.py --data /mnt/hens --ls http://TRUENAS:8085
```

Only frames not sent before are processed. Add `--limit 20` the first time
to see how it does. The first run downloads YOLOE (a few hundred MB).

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

## Predators

Foxes, raccoons, skunks and raptors rarely show up on our cameras, so
there's little to learn them from. `classes.yaml` lists the matching
Open Images classes for adding public photos of them; that step is the
next piece to build. Until then the model will rarely report predators.
Leave Frigate on the stock model if that matters more to you than better
hen detection.

## Files

| File | What it does |
|------|--------------|
| `hen_model/classes.yaml` | the classes, YOLOE's prompts for each, matching Open Images classes |
| `hen_model/harvest.py` | pulls frames out of Frigate into the share |
| `hen_model/prelabel.py` | YOLOE's first-guess boxes, sent to Label Studio |
| `hen_model/dataset.py` | Label Studio labels → YOLO training set |
| `hen_model/train.py` | trains, exports `hens.onnx`, writes the Frigate config lines |
| `hen_model/common.py` | shared code: the class list, Frigate and Label Studio clients |
| `hen_model/label-studio/docker-compose.yml` | the Label Studio stack for Portainer |

Ultralytics (training, YOLOE) is AGPL-licensed, which is fine for home use
like this.
