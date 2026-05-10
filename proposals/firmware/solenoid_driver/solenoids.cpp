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

#include "solenoids.h"

namespace zf8hp {

using max22200::Reg;
using max22200::SpiFrame;

static constexpr uint32_t EncodeChannelCfg(const SolenoidCommand& cmd) {
    uint32_t v = 0;
    v |= (max22200::MaToCode(cmd.i_hit_ma)  << max22200::CFG_IHIT_SHIFT)
         & max22200::CFG_IHIT_MASK;
    v |= (max22200::MaToCode(cmd.i_hold_ma) << max22200::CFG_IHOLD_SHIFT)
         & max22200::CFG_IHOLD_MASK;
    v |= (max22200::MsToHitCode(cmd.t_hit_ms) << max22200::CFG_THIT_SHIFT)
         & max22200::CFG_THIT_MASK;
    v |= (static_cast<uint32_t>(cmd.topology) << max22200::CFG_TOPO_SHIFT)
         & max22200::CFG_TOPO_MASK;
    if (cmd.enable) v |= max22200::CFG_ENABLE;
    /* All fault disables left at 0 — we want OCP/OLF/HHF to actively
     * shut the channel down on a fault rather than burning the
     * solenoid winding. */
    return v;
}

static constexpr Reg ChannelCfgReg(uint8_t channel) {
    return static_cast<Reg>(static_cast<uint8_t>(Reg::Cfg_Ch0) + channel);
}

SpiFrame Solenoids::BuildConfigWrite(const SolenoidCommand& cmd) {
    return max22200::BuildWrite(ChannelCfgReg(cmd.channel), EncodeChannelCfg(cmd));
}

SpiFrame Solenoids::BuildDisable(uint8_t /*chip_index*/, uint8_t channel) {
    /* All-zero payload writes: enable bit cleared, currents zero,
     * topology defaults to low-side. The chip drops the output to
     * high-Z. */
    return max22200::BuildWrite(ChannelCfgReg(channel), 0);
}

uint8_t Solenoids::BuildFramesForChipMask(
    uint8_t chip_index,
    uint8_t engaged_mask,
    const uint16_t hit_currents_ma[9],
    const uint16_t hold_currents_ma[9],
    SpiFrame out_frames[8],
    uint8_t out_solenoid_ids[8])
{
    uint8_t n = 0;
    for (uint8_t s = 0; s < static_cast<uint8_t>(SolenoidId::COUNT); ++s) {
        const SolenoidBinding& b = kSolenoidBinding[s];
        if (b.chip_index != chip_index) continue;
        if (n >= 8) break;
        bool engaged = (engaged_mask & (1u << s)) != 0;
        SolenoidCommand cmd{};
        cmd.chip_index = b.chip_index;
        cmd.channel    = b.channel;
        cmd.enable     = engaged;
        cmd.i_hit_ma   = engaged ? hit_currents_ma[s]  : 0;
        cmd.i_hold_ma  = engaged ? hold_currents_ma[s] : 0;
        cmd.t_hit_ms   = b.hit_ms;
        cmd.topology   = b.topology;
        out_frames[n] = BuildConfigWrite(cmd);
        out_solenoid_ids[n] = s;
        ++n;
    }
    return n;
}

void Solenoids::DecodeFaults(uint32_t fault_status_reg, ChannelFault out[8]) {
    for (uint8_t ch = 0; ch < 8; ++ch) {
        uint32_t bits = max22200::ChannelFault(ch, fault_status_reg);
        out[ch].open_load        = (bits & max22200::FAULT_OPEN_LOAD)       != 0;
        out[ch].short_to_supply  = (bits & max22200::FAULT_SHORT_TO_SUPPLY) != 0;
        out[ch].over_current     = (bits & max22200::FAULT_OVER_CURRENT)    != 0;
    }
}

/*
 * TCU_Status2.FaultBits layout — 16 bits of fault summary published on
 * CAN. We define the bit layout here as the source of truth; the DBC
 * comment must match this. The layout is intentionally compact: each
 * fault category gets one bit OR'd across all channels of that category.
 *
 *   bit  0  Solenoid open-load (any channel, any chip)
 *   bit  1  Solenoid short-to-supply (any channel)
 *   bit  2  Oil temperature high (set elsewhere; not by this function)
 *   bit  3  Line pressure low    (set elsewhere)
 *   bit  4  Speed sensor fault   (set elsewhere)
 *   bit  5  LIN comm fault       (set elsewhere)
 *   bit  6  CAN stale            (set elsewhere)
 *   bit  7  Solenoid over-current (any channel)
 *   bit  8  Park position sensor fault (set elsewhere)
 *   bit  9  MAX22200 chip 0 unresponsive
 *   bit 10  MAX22200 chip 1 unresponsive
 *   bit 11..15 reserved
 */
uint16_t Solenoids::FaultsToTcuStatus2Bits(const ChannelFault chip0[8],
                                            const ChannelFault chip1[8]) {
    uint16_t bits = 0;
    for (uint8_t ch = 0; ch < 8; ++ch) {
        if (chip0[ch].open_load       || chip1[ch].open_load)        bits |= 1u << 0;
        if (chip0[ch].short_to_supply || chip1[ch].short_to_supply)  bits |= 1u << 1;
        if (chip0[ch].over_current    || chip1[ch].over_current)     bits |= 1u << 7;
    }
    return bits;
}

} // namespace zf8hp
