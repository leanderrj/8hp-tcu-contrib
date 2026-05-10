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

#ifndef ZF8HP_CLUTCH_TABLE_H
#define ZF8HP_CLUTCH_TABLE_H

#include <stdint.h>

/*
 * ZF 8HP clutch engagement table — calibration data.
 *
 * The 8HP transmission family (8HP70 / 8HP90 / 8HP95 / GA8P75HZ) uses 4 simple
 * Ravigneaux planetary sets and 5 shift elements. Exactly 3 of the 5 are
 * engaged in each forward gear, giving 8 forward ratios + reverse. The
 * defining design property is *single-element-per-shift*: every adjacent
 * gear pair (1↔2, 2↔3, …, 7↔8) differs by exactly one element. This is what
 * lets the gearbox shift in ~200 ms — only one clutch is filling and one
 * draining at a time, so the overlap window is short.
 *
 * Source for the engagement schedule below:
 *   Greiner, J. and Grumbach, M., "8-Speed Automatic Transmission for RWD
 *   Vehicles," SAE Technical Paper 2009-01-1083, 2009.
 *
 * Element-letter convention (A..E) follows the labels Damien Maguire used on
 * the TCM_Pinout.pdf posted to openinverter forum thread #6047 (2026-05-10):
 *   A → TCM pin 41
 *   B → TCM pin 43
 *   C → TCM pin 45
 *   D → TCM pin 42
 *   E → TCM pin 44
 *
 * The mapping from the paper's element labels to physical solenoids on a
 * specific 8HP variant is not certain across rebuild kits and ZF 'box
 * generations. Bench-verify before driving by:
 *  1) energising one element at a time on a static gearbox
 *  2) measuring which planetary member locks
 *  3) cross-checking against the table below
 * If the bench result disagrees with this table for a given gearbox, edit
 * this file rather than the state machine — the *logic* in shift_logic.cpp
 * is correct given any valid table satisfying the single-element-per-shift
 * property (verified by clutch_table_assert_valid()).
 */

namespace zf8hp {

enum class ShiftElement : uint8_t {
    A = 0, B = 1, C = 2, D = 3, E = 4,
    COUNT = 5,
};

/* Bit-packed clutch state: bit i set ⇔ ShiftElement(i) is engaged. */
using ClutchSet = uint8_t;

constexpr ClutchSet bit(ShiftElement e) {
    return static_cast<ClutchSet>(1u << static_cast<uint8_t>(e));
}

constexpr ClutchSet C_A = bit(ShiftElement::A);
constexpr ClutchSet C_B = bit(ShiftElement::B);
constexpr ClutchSet C_C = bit(ShiftElement::C);
constexpr ClutchSet C_D = bit(ShiftElement::D);
constexpr ClutchSet C_E = bit(ShiftElement::E);

/* Gear identifiers. Values chosen to match the DBC TCU_Status1.CurrentGear
 * enum: 0 = neutral, 1..8 = forward gears, 9 = reverse, 14 = mid-shift. */
enum class Gear : uint8_t {
    Neutral  = 0,
    Forward1 = 1,
    Forward2 = 2,
    Forward3 = 3,
    Forward4 = 4,
    Forward5 = 5,
    Forward6 = 6,
    Forward7 = 7,
    Forward8 = 8,
    Reverse  = 9,
    Shifting = 14,
    Invalid  = 15,
};

/* Clutch engagement table.
 *
 * Sequential single-element-per-shift schedule per Greiner & Grumbach 2009.
 * Adjacent rows (1↔2, 2↔3, …, 7↔8) differ in exactly one element; the
 * unit test in test_shift_logic.cpp asserts this invariant across the full
 * table at compile time via a constexpr check.
 */
constexpr ClutchSet kClutchTable[] = {
    /* Neutral  */ 0,
    /* Forward1 */ C_A | C_B | C_D,
    /* Forward2 */ C_A | C_B | C_E,
    /* Forward3 */ C_A | C_C | C_E,
    /* Forward4 */ C_A | C_C | C_D,
    /* Forward5 */ C_A | C_D | C_E,
    /* Forward6 */ C_B | C_D | C_E,
    /* Forward7 */ C_B | C_C | C_E,
    /* Forward8 */ C_B | C_C | C_D,
    /* Reverse  */ C_C | C_D | C_E,
};

constexpr ClutchSet ClutchesFor(Gear g) {
    return (static_cast<uint8_t>(g) < (sizeof(kClutchTable) / sizeof(kClutchTable[0])))
        ? kClutchTable[static_cast<uint8_t>(g)]
        : 0;
}

constexpr int Popcount(ClutchSet s) {
    int n = 0;
    for (int i = 0; i < 8; ++i) if (s & (1u << i)) ++n;
    return n;
}

/* The two operations a single-element shift performs:
 *   - drop_set: elements engaged in `from` but not in `to`
 *   - lift_set: elements engaged in `to` but not in `from`
 */
struct ShiftDelta {
    ClutchSet drop_set;
    ClutchSet lift_set;

    constexpr int drop_count() const { return Popcount(drop_set); }
    constexpr int lift_count() const { return Popcount(lift_set); }
    constexpr bool is_single_element() const {
        return drop_count() == 1 && lift_count() == 1;
    }
};

constexpr ShiftDelta DeltaBetween(Gear from, Gear to) {
    ClutchSet f = ClutchesFor(from);
    ClutchSet t = ClutchesFor(to);
    return ShiftDelta{ static_cast<ClutchSet>(f & ~t),
                       static_cast<ClutchSet>(t & ~f) };
}

/* Compile-time validation: every adjacent forward-gear pair differs by
 * exactly one element (the defining ZF 8HP design property). If this
 * static_assert fails after editing the table, the table is broken. */
constexpr bool AdjacentPairsAreSingleElement() {
    for (int g = 1; g <= 7; ++g) {
        ShiftDelta d = DeltaBetween(static_cast<Gear>(g),
                                     static_cast<Gear>(g + 1));
        if (!d.is_single_element()) return false;
    }
    return true;
}

static_assert(AdjacentPairsAreSingleElement(),
              "ZF 8HP clutch table violates single-element-per-shift property");

constexpr bool ForwardGearsHaveThreeElements() {
    for (int g = 1; g <= 8; ++g) {
        if (Popcount(ClutchesFor(static_cast<Gear>(g))) != 3) return false;
    }
    return true;
}
static_assert(ForwardGearsHaveThreeElements(),
              "ZF 8HP forward gears must each engage exactly 3 elements");

constexpr bool ReverseHasThreeElements() {
    return Popcount(ClutchesFor(Gear::Reverse)) == 3;
}
static_assert(ReverseHasThreeElements(),
              "ZF 8HP reverse gear must engage exactly 3 elements");

constexpr bool NeutralEngagesNothing() {
    return ClutchesFor(Gear::Neutral) == 0;
}
static_assert(NeutralEngagesNothing(),
              "Neutral must engage zero shift elements");

} // namespace zf8hp

#endif // ZF8HP_CLUTCH_TABLE_H
