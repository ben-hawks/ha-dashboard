# Coop fan controller enclosure (DC fan)

Sealed, wall-mounted enclosure for the 93 × 87 mm ESP32-WROOM-32E 4-relay board, plus a separate shield for a metal-cased SHT40 probe. The board runs from a DC supply through its 7–30 V terminal and switches a low-voltage DC fan. No mains goes into the box.

Everything is parametric OpenSCAD; STLs are in `out/`.

The board's firmware is [`esphome/coop-fan.yaml`](../../esphome/coop-fan.yaml): fan on relay 1 (GPIO32), SHT40 on GPIO21 (SDA) / GPIO22 (SCL), which matches the wiring below.

## Files

| File | What it is |
|---|---|
| `coop_controller.scad` | Base, lid, gasket, fit-check template (`part=` selects) |
| `sensor_shield.scad` | Sensor shield: cap with probe clamp, stacked plates, wall bracket |
| `out/coop_fitcheck.stl` | **Print this first** (10 min) to confirm mounting-hole pitch |
| `out/coop_base.stl`, `coop_lid.stl`, `coop_gasket.stl` | Enclosure parts |
| `out/shield_cap.stl`, `shield_plate.stl` (×4), `shield_bracket.stl` | Sensor shield |

Outer size: 135 × 141 × 51 mm body (+4 mm lid). The base with its mounting ears is 176 mm wide, so it needs a 220 mm or larger bed.

The lid reads "12 VDC". Change `lid_line2` if your supply is a different voltage.

## Before you print: check the hole pitch

The mounting-hole spacing (`hole_dx = 87`, `hole_dy = 81`) was estimated from the listing photo. Print `coop_fitcheck.stl`; the pegs should drop into the board's corner holes. If they don't, measure the board with calipers, edit `hole_dx`/`hole_dy`, and re-export with:

```
openscad -D 'part="base"' -o coop_base.stl coop_controller.scad
```

## Layout

The board mounts with the relay terminals (NO/COM/NC) facing the gland wall. Mount the box **vertically, glands pointing down**, so water and condensate can't run into the cable entries.

- **Left channel, marked POWER.** DC supply cable from its gland up to the 7–30 V / GND terminal.
- **Right channel, marked LOW VOLTAGE.** Sensor cable up to the ESP32 header. A low rib keeps it away from relay terminal J4.
- **Glands, left to right:** PG9 DC in, PG7 fan, M12 breather vent, PG7 sensor.
- **Lid.** Screws thread into blind M4 inserts, so there are no holes through to the interior. A TPU gasket sits in the lid groove, and the lid overhangs the walls by 3 mm as a drip edge.
- **Mounting ears.** They sit outside the sealed volume, so you never drill the box.

## Bill of materials

| Qty | Part |
|---|---|
| 1 | PG9 nylon IP68 cable gland (4–8 mm cable), DC in |
| 2 | PG7 nylon IP68 cable gland (3–6.5 mm), fan and sensor |
| 1 | M12×1.5 ePTFE breather/vent plug ("waterproof vent valve") |
| 4 | M3 heat-set insert (4 mm OD) + M3×6 screw, for the PCB |
| 4 | M4 heat-set insert (5.6 mm hole) + M4×12 screw + bonded sealing (Dowty) washer, for the lid |
| 1 | Gasket: print `coop_gasket.stl` in TPU 85A–95A at 100% infill, or press 3 mm closed-cell foam cord into the groove |
| 1 | DC supply matching the fan voltage (e.g. 12 V, with ≥1 A headroom over the fan's rated current) |
| 1 | Inline blade or 5×20 mm fuse on the supply + lead, sized ~2× the fan current |
| 1 | 1N4007 or 1N5819 diode (flyback across the fan) |
| 2 | 4.7 kΩ resistors (I²C pull-ups, if the probe doesn't have them) |
| — | 2-conductor cable for supply and fan (18 AWG is plenty) |
| 1 | Silica gel pack (indicating type), taped to the lid |
| — | Silicone conformal coating (e.g. MG Chemicals 422C) |
| 3 | M3 threaded rod ~90 mm + 6 nuts/washers, for the sensor shield |
| 4 | #8 or 4 mm screws, for the wall ears |

## Printing

- **Material: ASA if you can, PETG otherwise. Not PLA.** PLA creeps under the lid screws, gets brittle when cold, and softens near heat lamps.
- **Base:** open side up, 4 walls, 5 top/bottom layers, 25–30% gyroid. No supports needed.
- **Lid:** outside face down, as exported. The embossed text reads correctly on the outside.
- **Shield plates:** inner ring down, as exported. They are 45° cones, so they print without supports.
- **Shield cap:** roof down, as exported.
- **Color:** use white or light filament for the shield so it doesn't heat up under a heat lamp or in sun through a window.

## Wiring

```
Supply + ──[fuse]──┬── board 7-30V
                   └── relay K1 COM1
relay K1 NO1 ──────────── fan +
Supply − ──────────┬───── board GND
                   └───── fan −

Flyback diode across the fan: cathode (stripe) to fan +, anode to fan −
```

- **Leave the N/L mains terminals unused.**
- **Fit the flyback diode.** It stops the motor's turn-off spike from arcing the relay contacts and resetting the ESP32. Put it at the fan or at the terminal block.
- **Use NO, not NC,** so the fan is off if the ESP32 is unpowered or crashed.
- **Supply voltage:** the board's 7–30 V input feeds its own 5 V buck. A 12 V or 24 V fan can share one supply with the board.
  - For a 5 V fan, feed the board's 5 V terminal instead.
- **Supply placement:** keep the wall-wart or DIN supply in a dry spot (garage or house side), not in the coop, and run DC in. If it plugs into a coop outlet, that outlet should be GFCI.
- **Relay rating:** a single DC fan is well within the relay's 10 A / 30 VDC rating.
- **Glands:** use one per cable and tighten until the seal grips. Leave a drip loop below the box on every cable.

### Optional: speed control instead of on/off

A 4-wire PWM PC-style fan can be speed-controlled directly from a GPIO on its PWM wire, with the relay just cutting power when it's off. That lets you run it slow in winter for gentle moisture removal.

## SHT40 probe

### Wiring

- **Connections:** VCC to 3.3 V (not 5 V), GND to GND, SDA and SCL to two free GPIOs.
  - The ESP32 defaults are 21 (SDA) and 22 (SCL), but check that your board's relays aren't on them.
  - Avoid strapping pins 0, 2, 12 and 15, and input-only pins 34–39.
- **Pull-ups:** many probe breakouts include them. If yours doesn't, fit 4.7 kΩ from SDA and SCL to 3.3 V at the board end.
- **Bus speed:** 1 m of cable is fine at 100 kHz. If you see read errors, drop it to 50 kHz.
- **Cable length:** don't extend past about 2–3 m without an I²C bus extender.
- **Placement:** the 1 m cable means the box has to mount within about a metre of the shield. Put them side by side on the same wall.
- **Connectors:** if the cable ends in a Dupont or JST plug, it won't pass through the PG7 gland (3–6.5 mm). Either thread the gland on before crimping, or switch that entry to PG9 (change the sensor entry in `glands` to `15.7`).

### Mounting in the shield

- Push the probe up into the cap's split clamp until it hits the shoulder. The tip then points down into the middle of the plate stack.
- Cinch two zip ties in the grooves to grip it.
- `probe_d` defaults to 12 mm. Measure yours (16 mm is also common) and re-export the cap if it differs.
- The cap and bracket have a side slot for the cable, so a pre-terminated cable slips in sideways and nothing needs threading through.

## Cold weather and coop survival

Cold isn't the main threat. Condensation, ammonia, and dust are.

- **Rated range:** the ESP32 module and relays are rated to −40 °C. Northern Illinois lows of about −30 °C are within range.
- **Self-heating:** the board's buck converter and ESP32 dissipate around half a watt to a watt. That keeps the sealed box slightly above ambient, which works in your favor against condensation.
- **Breather vent:** it lets the box equalize pressure without pulling in humid air through the gasket every time the temperature swings.
- **Desiccant:** the silica pack absorbs what's sealed in at assembly. Check it every few months.
- **Conformal coating:** coat the board, masking the relays, terminal blocks, buttons and header pins. Ammonia corrodes bare copper and solder joints over time, and dust plus humidity creates leakage paths. This is the single biggest lifespan improvement.
- **The fan itself:** sleeve-bearing fans stiffen up and can fail to start in deep cold once the oil thickens. A ball-bearing or fluid-dynamic-bearing fan copes much better. Expect to clean dust off the blades a couple of times a year.
- **Placement:** mount the box high, out of beak reach, and away from heat lamps and bedding.

## About the SHT40 in a coop

- **Housing:** the sintered metal housing keeps dust and droppings off the sensor. The plate shield still matters: it keeps beaks, heat-lamp radiation and drafts off it.
- **Accuracy over time:** the SHT40 handles high humidity far better than the DHT22. It also has a built-in heater that can drive off condensation and reset humidity creep after long periods near 100% RH.
  - In ESPHome this is the `sht4x` component's `heater_max_duty` option.
  - Readings taken right after a heater pulse run warm, so keep the duty low.
- **Cleaning:** tap or blow the dust out of the sintered cap once a season. Don't use solvents on it.

## Mounting the sensor shield

- **Height:** roughly roost height, where the birds are breathing.
- **Placement:** not directly in the fan's intake path, and not near the heat lamp or waterer.
- **Clearance:** the bracket holds it about 80 mm off the wall so it reads coop air, not wall temperature.
