# ZF 8HP TCU ↔ VCU CAN Protocol — Draft 0.1

A starter protocol for the in-Mechatronik openinverter TCU board (Damien Maguire,
Project 03 video, May 2026) talking to the openinverter `Stm32-vcu` over the
vehicle CAN bus.

**Status: draft for forum discussion. Nothing here is final.**

## Bus

- **500 kbit/s, classic CAN, 8-byte frames, standard 11-bit IDs.**
- Matches the `Stm32-vcu` default and `oi-inverter.dbc` style.
- IDs in `0x520` / `0x540` band — clear of existing OpenInverter usage
  (`0x190` inverter feedback, `0x100`–`0x10F` BMS, `0x420`+ chargers).

## Frames

| ID     | Dir       | Name             | Period  | Purpose                                           |
|--------|-----------|------------------|---------|---------------------------------------------------|
| 0x520  | VCU → TCU | VCU_GearRequest  |  20 ms  | Target gear, drive mode, accel/brake, fault clear |
| 0x521  | VCU → TCU | VCU_VehicleInfo  | 100 ms  | Actual torque, motor RPM/temp, SOC                |
| 0x540  | TCU → VCU | TCU_Status1      |  20 ms  | Current/target gear, shaft RPMs, oil T, line P    |
| 0x541  | TCU → VCU | TCU_Status2      | 100 ms  | Solenoid currents, faults, shift count, HW temp   |
| 0x542  | TCU → VCU | TCU_PumpStatus   | 100 ms  | Aux 12 V LIN pump state (HZ hybrid 'boxes only)   |

20 ms on the hot frames is a compromise: fast enough that the VCU can blend
torque around shifts, slow enough that bus load stays trivial.

## Design choices

**No CRC, no rolling counter mandatory.** A 4-bit counter is reserved on each
hot frame so we can add freshness checks later. Going without CRC matches the
existing `oi-inverter.dbc` precedent for frames *between* OpenInverter modules
on a private bus. CRC is needed when we have to interoperate with factory BMW
modules — different protocol, separate work item.

**Intel byte order, signed where it matters.** `TorqueRequest`,
`ActualTorque`, `MotorRPM`, all temps — signed so regen / reverse rotation
work without sentinel hacks. Matches `oi-inverter.dbc`.

**Gear encoding.** `TargetGear` and `CurrentGear` use *different* enums on
purpose:
- Request side (`TargetGear`) is in driver terms: P / R / N / D / S /
  M1..M8 / Limp.
- Status side (`CurrentGear`) is in mechanical terms: 0 = Neutral, 1..8 =
  engaged forward gear, 9 = Reverse, 14 = mid-shift, 15 = invalid.
  This matches what the gearbox actually has engaged and is what the VCU
  needs for shift-quality / torque blending.
- `TargetGearEcho` lets the VCU verify the TCU received the right request
  without parsing the request format twice.

**Fault bits packed into one 16-bit field** (`TCU_Status2.FaultBits`) rather
than separate flags — gives us 16 cheap fault categories and one place to
hang DTC mapping later.

**Pump frame is optional.** Non-hybrid 'boxes (vanilla 8HP70/90, no LIN aux
pump) will simply not transmit `0x542`. The VCU should treat its absence as
"no aux pump fitted," not as a fault.

## Open questions

1. **Manual gear range.** 4 bits gives us up to M8 plus P/R/N/D/S/Limp
   exactly. If we ever need M9 (the 8HP doesn't, but ZF has 9HP/9R variants)
   we'd need to widen — easier to widen now than after deployment.
2. **Counter / CRC.** Worth adding a J1939-style 4-bit counter + CRC8 on the
   request frame even on a private bus? Adds 1 byte cost, gains us
   freshness/integrity at almost zero cost. Lean yes but punted to v0.2.
3. **Torque handshake.** Real factory ZF 8HP shifts depend on the engine
   ECU pulling torque during a shift. This protocol declares the *request*
   side (`TorqueRequest` / `ActualTorque`) but doesn't yet have a shift-active
   torque-reduction request from TCU back to VCU. Probably needs an extra
   field in `TCU_Status1` or a new frame.
4. **Adaptation values.** Factory TCMs persist learned shift adapts. Do we
   want a `0x543` config/adapt frame for write/read of these, or punt to the
   web interface (likely better)?
5. **IDs.** `0x520`/`0x540` is just my pick. Whatever Damien uses elsewhere
   wins.

## Validation hooks

The DBC parses with `cantools` (Python) and `dbcc`. Quick check:

```bash
python -m pip install cantools
python -c "import cantools; db = cantools.database.load_file('zf8hp-tcu.dbc'); \
           [print(m.name, hex(m.frame_id), m.length) for m in db.messages]"
```

A C99 encoder/decoder is **generated** from this DBC and lives at
`proposals/firmware/can_codegen/zf8hp_tcu.{h,c}`, with a C++ wrapper at
`Can_ZF8HP.{h,cpp}` and 7 host-runnable unit tests covering round-trip,
range clamping, and counter advance. Schema changes go here in the DBC; run
`bash proposals/firmware/can_codegen/generate.sh` to refresh the C source.
Hand edits to the generated files will be lost.
