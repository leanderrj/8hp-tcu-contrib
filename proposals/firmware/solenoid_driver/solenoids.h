/*
 * This file is part of the Zombieverter project.
 *
 * Copyright (C) 2026 ZF_8HP contributor
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 */

#ifndef ZF8HP_SOLENOIDS_H
#define ZF8HP_SOLENOIDS_H

#include "max22200_regs.h"
#include <stdint.h>

namespace zf8hp {

/* All nine ZF G8P75HZ shift solenoids (per archive/forum/TCM_Pinout.pdf,
 * decoded in proposals/tcm_max22200_binding/PINOUT.md). The order here
 * matches the SolenoidId enum used by ShiftLogic / ParkLock so that
 * intent-level commands map cleanly onto channel binding. */
enum class SolenoidId : uint8_t {
    ClutchA = 0,        // TCM pin 41
    ClutchB,            // TCM pin 43
    ClutchC,            // TCM pin 45
    ClutchD,            // TCM pin 42
    ClutchE,            // TCM pin 44
    Tcc,                // TCM pin 46
    LinePressure,       // TCM pin 47
    ParkHold,           // TCM pin 5
    ParkRelease,        // TCM pin 48
    COUNT = 9,
};

/* Per-solenoid binding: which MAX22200 chip + channel it lives on.
 * See proposals/tcm_max22200_binding/SOLENOID_BINDING.md for the
 * recommended two-chip daisy-chain wiring. The HIT/HOLD/T_HIT
 * defaults below are conservative starting points; real numbers
 * come from the bench. */
struct SolenoidBinding {
    uint8_t  chip_index;          // 0 = first MAX22200, 1 = second
    uint8_t  channel;             // 0..7 within the chip
    bool     proportional;        // true → use HIT/HOLD; false → on/off
    uint16_t hit_ma;              // peak current setpoint
    uint16_t hold_ma;             // steady-state setpoint
    uint16_t hit_ms;              // duration to hold at HIT
    max22200::Topology topology;  // typically LowSide for 8HP solenoids
};

constexpr SolenoidBinding kSolenoidBinding[static_cast<uint8_t>(SolenoidId::COUNT)] = {
    /* ClutchA      */ { 0, 0, true,  800, 400, 30, max22200::Topology::LowSide },
    /* ClutchB      */ { 0, 1, true,  800, 400, 30, max22200::Topology::LowSide },
    /* ClutchC      */ { 0, 2, true,  800, 400, 30, max22200::Topology::LowSide },
    /* ClutchD      */ { 0, 3, true,  800, 400, 30, max22200::Topology::LowSide },
    /* ClutchE      */ { 0, 4, true,  800, 400, 30, max22200::Topology::LowSide },
    /* Tcc          */ { 0, 5, true,  900, 500, 30, max22200::Topology::LowSide },
    /* LinePressure */ { 0, 6, true,  900, 700, 30, max22200::Topology::LowSide },
    /* ParkHold     */ { 1, 0, false, 800, 800, 100, max22200::Topology::LowSide },
    /* ParkRelease  */ { 1, 1, false, 900, 0,   200, max22200::Topology::LowSide },
};

static_assert(static_cast<uint8_t>(SolenoidId::COUNT) == 9,
              "ZF G8P75HZ has nine solenoids — see TCM_Pinout.pdf");

/* Bit-pack the per-solenoid state into a single byte. Used to translate
 * ShiftLogic's ClutchSet output into a hardware command set. */
constexpr uint8_t SolenoidBit(SolenoidId s) {
    return static_cast<uint8_t>(1u << static_cast<uint8_t>(s));
}

/* The intent-level command from the rest of the firmware. Solenoids
 * doesn't decide which gear we're in; the layer above (ShiftLogic +
 * ParkLock) does, and produces this command. */
struct SolenoidCommand {
    uint8_t  chip_index;
    uint8_t  channel;
    bool     enable;             // false → channel off, regardless of currents
    uint16_t i_hit_ma;
    uint16_t i_hold_ma;
    uint16_t t_hit_ms;
    max22200::Topology topology;
};

/* Per-channel fault summary, decoded from MAX22200 FaultStatus reg. */
struct ChannelFault {
    bool open_load;
    bool short_to_supply;
    bool over_current;
};

/*
 * Solenoid command builder. Pure logic, no hardware. Construct command
 * frames from the binding table + intent inputs; decode fault frames
 * back into per-channel statuses; map decoded faults onto the
 * TCU_Status2.FaultBits field for CAN reporting.
 *
 * The actual SPI bus driver is injected by the caller — this class
 * only builds the bytes that go onto the wire and consumes the bytes
 * that come back. That separation lets the entire driver be unit-
 * tested without ever touching libopencm3 / a real STM32.
 */
class Solenoids {
public:
    /* Encode a configuration write for one channel at the levels in
     * `cmd`. Return value is the 4-byte SPI frame ready for the bus. */
    static max22200::SpiFrame BuildConfigWrite(const SolenoidCommand& cmd);

    /* Build a "disable channel" frame — same address as Config but
     * with enable bit cleared and current setpoints zeroed. */
    static max22200::SpiFrame BuildDisable(uint8_t chip_index, uint8_t channel);

    /* Convenience: turn an engagement bitmask + chip-index filter into
     * a sequence of frames to write. The caller streams them out. */
    static uint8_t BuildFramesForChipMask(
        uint8_t chip_index,
        uint8_t engaged_mask_per_solenoid,        // SolenoidBit packed
        const uint16_t hit_currents_ma[9],
        const uint16_t hold_currents_ma[9],
        max22200::SpiFrame out_frames[8],
        uint8_t out_solenoid_ids[8]);

    /* Decode an SPI read response from the FaultStatus register into
     * eight per-channel fault summaries. */
    static void DecodeFaults(uint32_t fault_status_reg,
                              ChannelFault out[8]);

    /* Map an array of per-chip per-channel faults onto a single 16-bit
     * mask compatible with TCU_Status2.FaultBits in our DBC. The bit
     * layout is fixed and documented in solenoids.cpp. */
    static uint16_t FaultsToTcuStatus2Bits(const ChannelFault chip0[8],
                                           const ChannelFault chip1[8]);

    /* Resolve a SolenoidId to its binding entry. */
    static const SolenoidBinding& BindingFor(SolenoidId id) {
        return kSolenoidBinding[static_cast<uint8_t>(id)];
    }
};

} // namespace zf8hp

#endif // ZF8HP_SOLENOIDS_H
