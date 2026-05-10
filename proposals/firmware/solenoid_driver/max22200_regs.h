/*
 * MAX22200 — Octal serial-controlled solenoid driver register definitions.
 *
 * Source: MAX22200 datasheet, Analog Devices (formerly Maxim Integrated).
 * https://www.analog.com/en/products/max22200.html
 *
 * The datasheet identifies the chip as an "Octal 36 V Serial-Controlled
 * Solenoid Driver" with 8 independent half-bridges, 1 A RMS per channel,
 * 200 mΩ on-resistance, push-pull outputs configurable as low-side,
 * high-side, or full-bridge by paralleling channel pairs. Per-channel
 * HIT current, HOLD current, and HIT time configuration via SPI.
 *
 * The register/bit layout below follows the convention documented in the
 * Analog Devices datasheet. Where a specific bit position is asserted,
 * the constant is named so that any disagreement with a future datasheet
 * revision is a one-line change. Auditors should compare against:
 *   archive/references/MAX22200_datasheet.pdf
 *
 * This header has no I/O — it defines the wire format that
 * Solenoids.cpp constructs and parses. The actual SPI driver is the
 * caller's problem (libopencm3 SPI3 in production; a stub in the host
 * tests).
 */

#ifndef MAX22200_REGS_H
#define MAX22200_REGS_H

#include <stdint.h>

namespace max22200 {

/* SPI is 32 bits per transaction. The first byte is the command/address
 * byte; the remaining 24 bits are register data. Bit 7 of the command
 * byte selects read (1) or write (0). Bit 0 is reserved and should be
 * written 0. */
constexpr uint8_t CMD_READ_BIT  = 0x80;
constexpr uint8_t CMD_WRITE_BIT = 0x00;

/* Register addresses (datasheet Table — Register Map). One R/W status
 * register, eight per-channel configuration registers, one fault
 * status, one fault mask. */
enum class Reg : uint8_t {
    Status        = 0x00,  // device-wide status: enable, mode, fault summary
    Cfg_Ch0       = 0x01,  // channel 0 HIT/HOLD/T_HIT + flags
    Cfg_Ch1       = 0x02,
    Cfg_Ch2       = 0x03,
    Cfg_Ch3       = 0x04,
    Cfg_Ch4       = 0x05,
    Cfg_Ch5       = 0x06,
    Cfg_Ch6       = 0x07,
    Cfg_Ch7       = 0x08,
    FaultStatus   = 0x09,  // per-channel fault flags (read-clear)
    FaultMask     = 0x0A,  // per-channel fault enable mask
};

/* ----------------------------------------------------------------- */
/* Status register (R0)                                              */
/* ----------------------------------------------------------------- */

constexpr uint32_t STATUS_ACTIVE     = 1u <<  0; // device active (CFG OK)
constexpr uint32_t STATUS_MODE_PWM   = 1u <<  1; // 1 = chopper mode, 0 = full-on
constexpr uint32_t STATUS_OVT_FAULT  = 1u <<  2; // global over-temp shutdown
constexpr uint32_t STATUS_OCP_FAULT  = 1u <<  3; // any channel in over-current
constexpr uint32_t STATUS_OLF_FAULT  = 1u <<  4; // any channel in open-load fault
constexpr uint32_t STATUS_HHF_FAULT  = 1u <<  5; // any channel hit-time exceeded

/* ----------------------------------------------------------------- */
/* Per-channel configuration register layout                         */
/* ----------------------------------------------------------------- */

/* HIT current setpoint: 7-bit field, raw 0..127 maps to 0..1.0 A in
 * approximately 7.87 mA steps (datasheet I_HIT vs DAC code).
 * Storage: bits 0..6 of cfg word. */
constexpr uint32_t CFG_IHIT_MASK    = 0x0000007Fu;
constexpr unsigned CFG_IHIT_SHIFT   = 0;

/* HOLD current setpoint: 7-bit field, same scale as HIT. Held after
 * t_HIT expires. Bits 7..13 of cfg word. */
constexpr uint32_t CFG_IHOLD_MASK   = 0x00003F80u;
constexpr unsigned CFG_IHOLD_SHIFT  = 7;

/* HIT time: 7-bit field, raw 0..127 maps to 0..200 ms.
 * Bits 14..20. */
constexpr uint32_t CFG_THIT_MASK    = 0x001FC000u;
constexpr unsigned CFG_THIT_SHIFT   = 14;

/* Channel enable. */
constexpr uint32_t CFG_ENABLE       = 1u << 21;

/* Output topology select for this channel.
 *   00 = low-side driver (output to GND when on)
 *   01 = high-side driver (output to V_BAT when on)
 *   10 = paralleled with adjacent channel for 2 A capability
 *   11 = full-bridge (this channel + adjacent form an H-bridge)
 */
enum class Topology : uint8_t {
    LowSide    = 0b00,
    HighSide   = 0b01,
    Paralleled = 0b10,
    FullBridge = 0b11,
};
constexpr uint32_t CFG_TOPO_MASK    = 0x00C00000u;
constexpr unsigned CFG_TOPO_SHIFT   = 22;

/* Fault enable mask bits — when a fault is allowed to disable the
 * channel automatically. Always-on for OCP and OLF in our use; HHF
 * (hit-time exceeded) we leave enabled too. */
constexpr uint32_t CFG_FAULT_DISABLE_OCP = 1u << 24;
constexpr uint32_t CFG_FAULT_DISABLE_OLF = 1u << 25;
constexpr uint32_t CFG_FAULT_DISABLE_HHF = 1u << 26;

/* ----------------------------------------------------------------- */
/* Per-channel current setpoint helpers                              */
/* ----------------------------------------------------------------- */

constexpr uint16_t kIRangeMa = 1000;     // datasheet I_HIT, I_HOLD full scale
constexpr uint16_t kIDacSteps = 128;     // 7-bit DAC

constexpr uint8_t MaToCode(uint16_t milliamps) {
    if (milliamps >= kIRangeMa) return kIDacSteps - 1;
    /* 1000 mA / 128 codes ≈ 7.81 mA per LSB. */
    return static_cast<uint8_t>((milliamps * (kIDacSteps - 1)) / kIRangeMa);
}

constexpr uint16_t CodeToMa(uint8_t code) {
    if (code >= kIDacSteps) code = kIDacSteps - 1;
    return static_cast<uint16_t>((static_cast<uint32_t>(code) * kIRangeMa)
                                 / (kIDacSteps - 1));
}

/* HIT-time: full scale 200 ms across 7-bit field, ≈ 1.57 ms / LSB. */
constexpr uint16_t kTHitFullMs  = 200;
constexpr uint16_t kTHitDacSteps = 128;
constexpr uint8_t MsToHitCode(uint16_t ms) {
    if (ms >= kTHitFullMs) return kTHitDacSteps - 1;
    return static_cast<uint8_t>((ms * (kTHitDacSteps - 1)) / kTHitFullMs);
}

/* ----------------------------------------------------------------- */
/* Fault status decoding                                             */
/* ----------------------------------------------------------------- */

/* The FaultStatus register packs per-channel fault summaries: each
 * channel gets 3 bits at positions 3*ch..3*ch+2. */
constexpr uint32_t FaultBitsForChannel(uint8_t ch) {
    return 0x7u << (3u * ch);
}

constexpr uint32_t FAULT_OPEN_LOAD       = 0b001;
constexpr uint32_t FAULT_SHORT_TO_SUPPLY = 0b010;
constexpr uint32_t FAULT_OVER_CURRENT    = 0b100;

constexpr uint32_t ChannelFault(uint8_t ch, uint32_t fault_mask) {
    return (fault_mask >> (3u * ch)) & 0x7u;
}

/* ----------------------------------------------------------------- */
/* Frame construction                                                */
/* ----------------------------------------------------------------- */

/* Build a 32-bit SPI write frame: cmd byte = WRITE | (addr << 1),
 * payload = 24-bit register value. Returned big-endian (MSB first)
 * because that's how MAX22200 expects it on the wire. */
struct SpiFrame {
    uint8_t bytes[4];
};

constexpr SpiFrame BuildWrite(Reg addr, uint32_t value24) {
    SpiFrame f{};
    f.bytes[0] = static_cast<uint8_t>(CMD_WRITE_BIT |
                                       (static_cast<uint8_t>(addr) << 1));
    f.bytes[1] = static_cast<uint8_t>((value24 >> 16) & 0xFF);
    f.bytes[2] = static_cast<uint8_t>((value24 >>  8) & 0xFF);
    f.bytes[3] = static_cast<uint8_t>( value24        & 0xFF);
    return f;
}

constexpr SpiFrame BuildRead(Reg addr) {
    SpiFrame f{};
    f.bytes[0] = static_cast<uint8_t>(CMD_READ_BIT |
                                       (static_cast<uint8_t>(addr) << 1));
    /* payload bytes are don't-care on read. */
    return f;
}

/* Decode a 32-bit SPI read response back into a 24-bit register value.
 * Byte 0 of the response carries the command echo; bytes 1..3 are data. */
constexpr uint32_t DecodeReadResponse(const uint8_t bytes[4]) {
    return (static_cast<uint32_t>(bytes[1]) << 16) |
           (static_cast<uint32_t>(bytes[2]) <<  8) |
            static_cast<uint32_t>(bytes[3]);
}

} // namespace max22200

#endif // MAX22200_REGS_H
