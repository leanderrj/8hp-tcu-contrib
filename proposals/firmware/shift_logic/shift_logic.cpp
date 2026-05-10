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

#include "shift_logic.h"

namespace zf8hp {

ShiftLogic::ShiftLogic(ShiftCalibration cal) : cal_(cal) {}

void ShiftLogic::RequestGear(Gear target) {
    target_ = target;
}

/*
 * PlanNextStep — choose the single-element step from `current_` toward
 * `target_`. The 8HP gear graph is mostly linear (1↔2↔3↔…↔8) so for
 * forward shifts the step is +1 or -1. Reverse and Neutral are isolated
 * nodes: from any forward gear we go via Neutral. This is the same path
 * the OEM Mechatronik takes (you can't shift directly D→R without a
 * Neutral pause; the brake-pedal interlock enforces it from the lever
 * side, but the TCM still walks it).
 */
Gear ShiftLogic::PlanNextStep() const {
    if (current_ == target_) return current_;

    auto cur = static_cast<uint8_t>(current_);
    auto tgt = static_cast<uint8_t>(target_);

    // Forward gear adjacency: 1..8 walk one step at a time.
    if (cur >= 1 && cur <= 8 && tgt >= 1 && tgt <= 8) {
        return static_cast<Gear>(tgt > cur ? cur + 1 : cur - 1);
    }

    // Anything involving Neutral or Reverse goes via Neutral first.
    if (current_ == Gear::Neutral) {
        // From N we can engage gear 1 directly (incoming-only "clutch fill",
        // no outgoing element to drain). Same for Reverse.
        if (target_ == Gear::Reverse) return Gear::Reverse;
        if (tgt >= 1 && tgt <= 8)     return Gear::Forward1;
        return Gear::Neutral;
    }

    // Any forward gear or Reverse → must pass through Neutral first.
    return Gear::Neutral;
}

void ShiftLogic::EnterPhase(ShiftPhase p, uint32_t now_ms) {
    phase_ = p;
    phase_started_ms_ = now_ms;
    if (p == ShiftPhase::Idle) {
        torque_cut_ack_ = false;
    }
}

ShiftCommand ShiftLogic::Tick(uint32_t now_ms) {
    // Validate target gear up front. Any out-of-range request is a fault
    // and falls to limp (target = current_, no shift attempted).
    auto t = static_cast<uint8_t>(target_);
    bool target_valid =
        target_ == Gear::Neutral ||
        target_ == Gear::Reverse ||
        (t >= 1 && t <= 8);
    if (!target_valid) {
        fault_ = ShiftFault::InvalidTargetGear;
        target_ = current_;
        EnterPhase(ShiftPhase::Idle, now_ms);
    }

    switch (phase_) {
        case ShiftPhase::Idle: {
            if (current_ != target_ && fault_ == ShiftFault::None) {
                next_step_ = PlanNextStep();
                // Engaging from Neutral or releasing into Neutral does
                // not require torque-cut (no overlap window — there's
                // either no incoming or no outgoing element). Skip
                // straight to overlap-equivalent ramp.
                if (current_ == Gear::Neutral || next_step_ == Gear::Neutral) {
                    EnterPhase(ShiftPhase::Overlap, now_ms);
                } else {
                    EnterPhase(ShiftPhase::PreFill, now_ms);
                }
            }
            break;
        }

        case ShiftPhase::PreFill: {
            if (PhaseElapsed(now_ms, cal_.pre_fill_ms)) {
                EnterPhase(ShiftPhase::TorqueCut, now_ms);
            }
            break;
        }

        case ShiftPhase::TorqueCut: {
            if (torque_cut_ack_) {
                EnterPhase(ShiftPhase::Overlap, now_ms);
            } else if (PhaseElapsed(now_ms, cal_.torque_cut_ack_ms)) {
                fault_ = ShiftFault::TorqueCutTimeout;
                // Abort to the original gear. Don't latch limp yet —
                // a single missed handshake shouldn't disable the box.
                target_ = current_;
                EnterPhase(ShiftPhase::Idle, now_ms);
            }
            break;
        }

        case ShiftPhase::Overlap: {
            if (PhaseElapsed(now_ms, cal_.overlap_ms)) {
                current_ = next_step_;
                EnterPhase(ShiftPhase::Complete, now_ms);
            }
            break;
        }

        case ShiftPhase::Complete: {
            if (PhaseElapsed(now_ms, cal_.torque_restore_ms)) {
                EnterPhase(ShiftPhase::Idle, now_ms);
            }
            break;
        }

        case ShiftPhase::Limp: {
            // Stay limp. Recovery requires a power cycle (or an
            // explicit FaultClear from the VCU — handled at the
            // bind layer, not here).
            break;
        }
    }

    // Build the command output for this tick.
    ClutchSet engaged = ClutchesFor(current_);
    ClutchSet target_set = ClutchesFor(next_step_);

    ShiftCommand cmd{};
    cmd.current_gear = current_;
    cmd.target_gear  = target_;
    cmd.phase        = phase_;
    cmd.fault        = fault_;
    cmd.shift_active = (phase_ != ShiftPhase::Idle && phase_ != ShiftPhase::Limp);

    switch (phase_) {
        case ShiftPhase::Idle:
        case ShiftPhase::Limp:
            cmd.engaged_set     = engaged;
            cmd.ramping_in_set  = 0;
            cmd.ramping_out_set = 0;
            cmd.ramp_progress   = 100;
            cmd.torque_cut_request = false;
            break;

        case ShiftPhase::PreFill: {
            ShiftDelta d = DeltaBetween(current_, next_step_);
            cmd.engaged_set     = engaged;
            cmd.ramping_in_set  = d.lift_set;
            cmd.ramping_out_set = 0;
            uint32_t elapsed = now_ms - phase_started_ms_;
            cmd.ramp_progress = cal_.pre_fill_ms ?
                static_cast<uint8_t>((elapsed * cal_.pre_fill_pct) / cal_.pre_fill_ms) : 0;
            cmd.torque_cut_request = false;
            break;
        }

        case ShiftPhase::TorqueCut: {
            ShiftDelta d = DeltaBetween(current_, next_step_);
            cmd.engaged_set     = engaged;
            cmd.ramping_in_set  = d.lift_set;
            cmd.ramping_out_set = 0;
            cmd.ramp_progress   = cal_.pre_fill_pct;
            cmd.torque_cut_request = true;
            break;
        }

        case ShiftPhase::Overlap: {
            ShiftDelta d = DeltaBetween(current_, next_step_);
            // During overlap, both sides change. The bind layer chooses
            // the actual current ramps; we report the sets and progress.
            cmd.engaged_set     = static_cast<ClutchSet>(engaged & target_set);
            cmd.ramping_in_set  = d.lift_set;
            cmd.ramping_out_set = d.drop_set;
            uint32_t elapsed = now_ms - phase_started_ms_;
            cmd.ramp_progress = cal_.overlap_ms ?
                static_cast<uint8_t>((elapsed * 100u) / cal_.overlap_ms) : 100;
            // Only request torque cut for forward-to-forward shifts (where
            // both an incoming and outgoing element exist). N→1 / 1→N /
            // N→R / R→N are one-sided ramps with no overlap to manage, so
            // the engine/motor doesn't need to be cut.
            const bool one_sided = (current_ == Gear::Neutral) ||
                                   (next_step_ == Gear::Neutral);
            cmd.torque_cut_request = !one_sided;
            break;
        }

        case ShiftPhase::Complete:
            cmd.engaged_set     = engaged;
            cmd.ramping_in_set  = 0;
            cmd.ramping_out_set = 0;
            cmd.ramp_progress   = 100;
            cmd.torque_cut_request = false;
            break;
    }

    return cmd;
}

} // namespace zf8hp
