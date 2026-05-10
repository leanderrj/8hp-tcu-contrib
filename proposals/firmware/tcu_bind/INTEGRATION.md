# tcu_bind — integration

The bind layer wires `ShiftLogic` + `ParkLock` + `Solenoids` + `Can_ZF8HP`
into a single per-tick orchestrator with all hardware I/O behind
function-pointer callbacks. This is the firmware module that the TCU's
main loop drives directly.

## Files

```
include/tcu_bind.h
src/tcu_bind.cpp
test/test_tcu_bind.cpp
```

Depends on the four sibling modules: `shift_logic`, `park_lock`,
`solenoid_driver`, `can_codegen` (plus the cantools-generated
`zf8hp_tcu.{h,c}`).

## Public API

```cpp
TcuBind bind(io, calibration);
bind.OnCanRx(can_id, bytes, dlc);   // call from CAN ISR / RX queue
bind.Tick(now_ms);                   // call every 1 ms from main()
```

`TcuIo` is a struct of four function pointers:

| Callback | Purpose |
|---|---|
| `spi_write_max22200(chip, bytes[4])` | emit one 32-bit MAX22200 SPI write |
| `spi_read_fault_status(chip)` | read FaultStatus register, return 24-bit value |
| `can_send(can_id, bytes[8], dlc)` | transmit one CAN frame |
| `read_park_sensors()` | sample park-position switches + vehicle speed |

The unit tests bind these to recording stubs; the production target
binds them to libopencm3 SPI3, bxCAN, and GPIO read functions.

## Per-tick scheduling

| Action | Cadence | Source |
|---|---|---|
| `ShiftLogic::Tick`, `ParkLock::Tick` | every 1 ms | `RunShiftAndPark` |
| MAX22200 SPI command stream | every 10 ms | `EmitSolenoids` |
| MAX22200 fault polling | every 100 ms | `PollMaxFaults` |
| `TCU_Status1`, `TCU_ShiftStatus` | every 20 ms | `EmitCanStatus` |
| `TCU_Status2`, `TCU_PumpStatus` | every 100 ms | `EmitCanStatus` |

All cadence checks fire on first call (UINT32_MAX sentinel for "never
fired") so the bus comes up immediately after boot rather than waiting
for the first 100 ms tick.

## CAN-stale handling

Once a `VCU_GearRequest` has ever been seen, the bind layer tracks the
elapsed time since the last RX. If it exceeds 200 ms (`kVcuStaleThresholdMs`
matching HARA T007 / STR008) the bind layer:

- Sets `FaultBits[CanStale]` (bit 6 of `TCU_Status2.FaultBits`).
- Holds the current gear (does NOT auto-engage Neutral or Park,
  per the safety requirement).

When a fresh `VCU_GearRequest` arrives, the stale flag is cleared
and gear changes resume.

## Fault-bit mapping

The 16-bit `TCU_Status2.FaultBits` field has a fixed layout — the bind
layer is the source of truth for which bit means what:

| Bit | Meaning | Source |
|---|---|---|
| 0 | Solenoid open-load (any chip, any channel) | `Solenoids::FaultsToTcuStatus2Bits` |
| 1 | Solenoid short-to-supply | same |
| 2 | Oil temperature high | (TBD — temperature sensor reader) |
| 3 | Line pressure low | (TBD — pressure sensor reader) |
| 4 | Speed sensor fault | (TBD — STR011) |
| 5 | LIN comm fault | (TBD — pump LIN driver) |
| 6 | CAN stale | `TcuBind::Tick` staleness check |
| 7 | Solenoid over-current | `Solenoids::FaultsToTcuStatus2Bits` |
| 8 | Park position sensor fault | `TcuBind::RunShiftAndPark` |
| 9 | MAX22200 chip 0 unresponsive | (TBD) |
| 10 | MAX22200 chip 1 unresponsive | (TBD) |

## Test coverage

10 host-runnable assertions in `test_tcu_bind.cpp`:

- First Tick emits `TCU_Status1` (no warm-up delay).
- `TCU_Status1` cyclic at 50 Hz over 200 ms (~10 emissions).
- `TCU_Status2` cyclic at 10 Hz over 1 s (~10 emissions).
- `VCU_GearRequest(D)` initiates a Forward1 shift and settles.
- `VCU_GearRequest(P)` at rest engages park.
- Solenoid SPI loop fires at ~100 Hz.
- SPI writes distributed across both MAX22200 chips.
- Open-load fault on chip 0 channel 2 propagates to `FaultBits[0]`.
- VCU silence > 200 ms raises `FaultBits[CanStale]`.
- `ShiftActive` bit tracks the shift state machine.

## What's still TBD inside the bind layer

The pump LIN driver, oil temp / line pressure / hardware temp sensor
reads, and the speed-sensor cross-check (HARA T010 / STR011) are
declared in the fault-bit table above but not yet implemented. They
slot in as additional callbacks on `TcuIo` plus per-source bit
updates inside `RunShiftAndPark` or new sub-orchestrators.

The shift state machine's calibration (`ShiftCalibration`) and the
solenoid HIT/HOLD calibration (`SolenoidCalibration`) are passed in
at construction time; on the production target they're loaded from
NVM at boot.

## Verified end-to-end

Built against unmodified `damienmaguire/Stm32-vcu` master with all
five firmware modules + bind layer + tests linked into a single
`test_all` binary. All assertions pass:

```
ShiftLogicTest         12 assertions
ParkLockTest           10 assertions
SolenoidsTest          13 assertions
Can_ZF8HPTest          26 assertions
TcuBindTest            10 assertions
                       --
                       71 host C++ assertions, all passing
```
