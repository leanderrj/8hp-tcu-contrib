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

#include "park_lock.h"

namespace zf8hp {

ParkLock::ParkLock(ParkCalibration cal) : cal_(cal) {}

ParkState ParkLock::DecodeSenseState(const ParkSensors& s) const {
    /* Park-lock position switch reads Pos1 = engaged, Pos2 = released.
     * Both 0 means open-circuit (broken wire / connector unseated).
     * Both 1 means short to supply or fixture wiring fault.
     * In either fault case, default-safe: report Fault, hold pawl
     * wherever it is, refuse to move it. */
    if (s.pos1_contact && s.pos2_contact)   return ParkState::Fault;
    if (!s.pos1_contact && !s.pos2_contact) return ParkState::Fault;
    return s.pos1_contact ? ParkState::Engaged : ParkState::Disengaged;
}

bool ParkLock::VehicleStationaryEnough(const ParkSensors& s) const {
    return s.vehicle_speed_kmh_x100 <= cal_.engage_max_kmh_x100;
}

ParkCommand ParkLock::Tick(uint32_t now_ms, const ParkSensors& sensors) {
    /* Always classify the sensors first. A sensor fault overrides any
     * pending operation — we do not attempt to move the pawl when we
     * can't tell where it is. */
    ParkState observed = DecodeSenseState(sensors);
    if (observed == ParkState::Fault) {
        fault_ = ParkFault::SensorImpossibleReading;
        state_ = ParkState::Fault;
        ParkCommand cmd{};
        cmd.hold_energise     = false;
        cmd.release_energise  = false;
        cmd.state             = ParkState::Fault;
        cmd.fault             = fault_;
        cmd.park_lock_engaged = false;  // unknown — safer to report not engaged
        return cmd;
    }

    /* On Init, latch whatever the sensors say. Real boards spring the
     * pawl to engaged on power loss, so observed == Engaged after a
     * cold boot is the expected default. */
    if (state_ == ParkState::Init) {
        state_ = observed;
        phase_started_ms_ = now_ms;
    }

    /* If the observed state already matches the request, we're done.
     * This is the steady-state path on every tick when the driver
     * isn't asking for anything to change. */
    bool want_engaged = request_engaged_;
    bool is_engaged   = (observed == ParkState::Engaged);

    if (want_engaged == is_engaged) {
        state_ = observed;
        ParkCommand cmd{};
        cmd.hold_energise     = false;
        cmd.release_energise  = false;
        cmd.state             = state_;
        cmd.fault             = fault_;
        cmd.park_lock_engaged = is_engaged;
        return cmd;
    }

    /* Driver wants engagement to change. */
    if (want_engaged && !is_engaged) {
        /* Disengaged → Engaged. Block if vehicle is moving — pawl
         * impact at speed will damage the detent. */
        if (!VehicleStationaryEnough(sensors)) {
            fault_ = ParkFault::EngageBlockedByMotion;
            state_ = ParkState::Disengaged;
            ParkCommand cmd{};
            cmd.hold_energise     = false;
            cmd.release_energise  = false;
            cmd.state             = state_;
            cmd.fault             = fault_;
            cmd.park_lock_engaged = false;
            return cmd;
        }

        /* Drive Hold solenoid for engage_pulse_ms. Most 8HP variants
         * spring the pawl to Engaged when the box is stationary, so
         * this pulse is mostly belt-and-braces; the detent does the
         * actual mechanical work. */
        if (state_ != ParkState::Engaging) {
            state_ = ParkState::Engaging;
            phase_started_ms_ = now_ms;
        }
        bool pulse_active = (now_ms - phase_started_ms_) < cal_.engage_pulse_ms;
        if (!pulse_active &&
            (now_ms - phase_started_ms_) >= cal_.engage_budget_ms) {
            fault_ = ParkFault::EngageTimeout;
            state_ = ParkState::Disengaged;
            ParkCommand cmd{};
            cmd.hold_energise     = false;
            cmd.release_energise  = false;
            cmd.state             = state_;
            cmd.fault             = fault_;
            cmd.park_lock_engaged = false;
            return cmd;
        }
        ParkCommand cmd{};
        cmd.hold_energise     = pulse_active;
        cmd.release_energise  = false;
        cmd.state             = state_;
        cmd.fault             = fault_;
        cmd.park_lock_engaged = false;
        return cmd;
    }

    /* want_engaged == false && is_engaged: Engaged → Disengaged.
     * This is the dangerous direction. Refuse if the vehicle is moving
     * (it shouldn't be, but the sensors might be lying — and refusing
     * here is the cheap correct action). The bind layer is expected
     * to additionally require brake-pedal pressed before passing
     * RequestEngaged(false) through; we don't second-guess that here. */
    if (!VehicleStationaryEnough(sensors)) {
        fault_ = ParkFault::DisengageBlockedBySpeed;
        state_ = ParkState::Engaged;
        ParkCommand cmd{};
        cmd.hold_energise     = false;
        cmd.release_energise  = false;
        cmd.state             = state_;
        cmd.fault             = fault_;
        cmd.park_lock_engaged = true;
        return cmd;
    }

    if (state_ != ParkState::Disengaging) {
        state_ = ParkState::Disengaging;
        phase_started_ms_ = now_ms;
    }
    bool pulse_active = (now_ms - phase_started_ms_) < cal_.disengage_pulse_ms;
    if (!pulse_active &&
        (now_ms - phase_started_ms_) >= cal_.disengage_budget_ms) {
        fault_ = ParkFault::DisengageTimeout;
        state_ = ParkState::Engaged;
        ParkCommand cmd{};
        cmd.hold_energise     = false;
        cmd.release_energise  = false;
        cmd.state             = state_;
        cmd.fault             = fault_;
        cmd.park_lock_engaged = true;
        return cmd;
    }
    ParkCommand cmd{};
    cmd.hold_energise     = false;
    cmd.release_energise  = pulse_active;
    cmd.state             = state_;
    cmd.fault             = fault_;
    cmd.park_lock_engaged = true; // still engaged until sensors say otherwise
    return cmd;
}

} // namespace zf8hp
