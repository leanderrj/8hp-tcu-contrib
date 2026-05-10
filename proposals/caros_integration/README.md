# CarOS integration profile

Drop-in YAML profile that teaches CarOS about the openinverter ZF 8HP
TCU. CarOS supplies the dashboard / MQTT / Matter / trip-logging
surface; this profile maps our DBC frames onto those features.

## Files

```
zombieverter_8hp.yaml    profile in CarOS's profiles/ev_conversions/ format
```

## What it does

Walks every signal in `proposals/dbc/zf8hp-tcu.dbc` and maps it to:

- **An MQTT topic** under `car/telemetry/transmission/...`. CarOS's
  CAN-to-MQTT bridge picks these up automatically.
- **A dashboard widget** (gear indicator, gauges for oil temp / line
  pressure / shaft RPMs, fault lights for park-lock and aux pump).
- **An alert rule** keyed to the four highest-priority HARA hazards:
  T002 (ASIL D — park rollaway), T007 (CAN stale), T009 (aux pump
  during drive), and the generic any-fault catch-all.
- **A Matter device** so HomeKit / Google Home / Alexa can read
  transmission status.

The profile is **read-only**: `vcu_gear_request` is listed as
`direction: rx_monitor` so CarOS can log driver intent but never
inject onto the bus. This is deliberate — CarOS lives in QM/A
territory; gear actuation is the TCU's job (ASIL B/C, see
`proposals/safety/hara.py`).

## Installing into CarOS

Assuming CarOS is at `~/Code/caros/`:

```bash
cp proposals/caros_integration/zombieverter_8hp.yaml \
   ~/Code/caros/profiles/ev_conversions/
cp proposals/dbc/zf8hp-tcu.dbc \
   ~/Code/caros/dbc/

# Then in CarOS .env or config/profile.yaml:
#   active_profile: zombieverter_8hp
```

CarOS picks it up on next start. The dashboard's `Transmission` tab
populates from the `transmission.dashboard_widgets` block.

## Variant note

The default `vehicle.variant` is `GA8P75HZ` (the BMW PHEV hybrid 8HP
variant we've targeted throughout the contribution work). For
non-hybrid 8HP variants:

- Change `variant` to `8HP70`, `8HP90`, etc.
- Mark the `tcu_pump_status` frame `optional: true` already covers
  non-hybrid boxes that don't carry an aux pump.

## What this proves

The TCU and CarOS slot together cleanly via CAN with no code changes
on either side. The DBC is the contract; the YAML is the integration;
CarOS's existing infrastructure (MQTT bridge, dashboard renderer,
alert engine, Matter bridge) handles the rest.
