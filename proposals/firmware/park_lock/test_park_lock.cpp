#include "park_lock.h"
#include "test_list.h"

#include <iostream>

using namespace std;
using namespace zf8hp;

static ParkSensors EngagedStill() { return {true, false, 0}; }
static ParkSensors DisengagedStill() { return {false, true, 0}; }
static ParkSensors EngagedMoving(uint16_t speed) { return {true, false, speed}; }
static ParkSensors DisengagedMoving(uint16_t speed) { return {false, true, speed}; }
static ParkSensors BothContactsHigh() { return {true, true, 0}; }
static ParkSensors BothContactsLow() { return {false, false, 0}; }

static void TestStartsEngagedOnEngagedSensors() {
    ParkLock pl;
    auto cmd = pl.Tick(0, EngagedStill());
    ASSERT(cmd.state == ParkState::Engaged);
    ASSERT(cmd.park_lock_engaged);
    ASSERT(!cmd.hold_energise);
    ASSERT(!cmd.release_energise);
    ASSERT(cmd.fault == ParkFault::None);
}

static void TestSteadyStateNoSolenoidsEnergised() {
    /* Default state when nothing's changing: both solenoids off. */
    ParkLock pl;
    pl.RequestEngaged(true);
    for (uint32_t t = 0; t < 100; ++t) {
        auto cmd = pl.Tick(t, EngagedStill());
        ASSERT(!cmd.hold_energise);
        ASSERT(!cmd.release_energise);
    }
}

static void TestDisengageStillVehicle() {
    ParkLock pl;
    pl.Tick(0, EngagedStill());
    pl.RequestEngaged(false);
    auto cmd = pl.Tick(1, EngagedStill());
    ASSERT(cmd.state == ParkState::Disengaging);
    ASSERT(cmd.release_energise);
    ASSERT(!cmd.hold_energise);

    /* Sensors swap to disengaged after a few ms (mechanical action). */
    cmd = pl.Tick(50, DisengagedStill());
    ASSERT(cmd.state == ParkState::Disengaged);
    ASSERT(!cmd.release_energise);
    ASSERT(!cmd.hold_energise);
    ASSERT(!cmd.park_lock_engaged);
    ASSERT(cmd.fault == ParkFault::None);
}

static void TestDisengageBlockedAtSpeed() {
    ParkLock pl;
    pl.Tick(0, EngagedStill());
    pl.RequestEngaged(false);
    /* 5 km/h is well above kEngageMaxKmh = 0.02 km/h equivalent. */
    auto cmd = pl.Tick(1, EngagedMoving(500));
    ASSERT(cmd.fault == ParkFault::DisengageBlockedBySpeed);
    ASSERT(!cmd.release_energise);
    ASSERT(cmd.park_lock_engaged);
}

static void TestEngageBlockedAtSpeed() {
    ParkLock pl;
    pl.Tick(0, DisengagedStill());
    pl.RequestEngaged(true);
    auto cmd = pl.Tick(1, DisengagedMoving(500));
    ASSERT(cmd.fault == ParkFault::EngageBlockedByMotion);
    ASSERT(!cmd.hold_energise);
}

static void TestSensorBothHighIsFault() {
    ParkLock pl;
    auto cmd = pl.Tick(0, BothContactsHigh());
    ASSERT(cmd.state == ParkState::Fault);
    ASSERT(cmd.fault == ParkFault::SensorImpossibleReading);
    ASSERT(!cmd.hold_energise);
    ASSERT(!cmd.release_energise);
    ASSERT(!cmd.park_lock_engaged);
}

static void TestSensorBothLowIsFault() {
    ParkLock pl;
    auto cmd = pl.Tick(0, BothContactsLow());
    ASSERT(cmd.state == ParkState::Fault);
    ASSERT(cmd.fault == ParkFault::SensorImpossibleReading);
}

static void TestMutualExclusionInvariantHoldsAcrossManyTicks() {
    /* The single most important safety check: hold and release are
     * NEVER simultaneously commanded. */
    ParkLock pl;
    pl.RequestEngaged(false);
    for (uint32_t t = 0; t < 5000; ++t) {
        ParkSensors s = (t < 100) ? EngagedStill()
                       : (t < 200) ? EngagedMoving(50)   // briefly moving
                       : DisengagedStill();
        auto cmd = pl.Tick(t, s);
        ASSERT(!(cmd.hold_energise && cmd.release_energise));
    }
}

static void TestDisengageTimeoutRecoversToEngaged() {
    ParkLock pl;
    pl.Tick(0, EngagedStill());
    pl.RequestEngaged(false);
    /* Sensors stuck at Engaged — release pulse never succeeds. */
    for (uint32_t t = 1; t < 1500; ++t) {
        pl.Tick(t, EngagedStill());
    }
    auto cmd = pl.Tick(1500, EngagedStill());
    ASSERT(cmd.fault == ParkFault::DisengageTimeout);
    ASSERT(cmd.park_lock_engaged); // refused to leave engaged
    ASSERT(!cmd.release_energise);
}

static void TestClearFaultRecovers() {
    ParkLock pl;
    pl.Tick(0, BothContactsHigh());
    ASSERT(pl.fault() == ParkFault::SensorImpossibleReading);
    pl.ClearFault();
    auto cmd = pl.Tick(10, EngagedStill());
    ASSERT(cmd.fault == ParkFault::None);
    ASSERT(cmd.state == ParkState::Engaged);
}

void ParkLockTest::RunTest() {
    TestStartsEngagedOnEngagedSensors();
    TestSteadyStateNoSolenoidsEnergised();
    TestDisengageStillVehicle();
    TestDisengageBlockedAtSpeed();
    TestEngageBlockedAtSpeed();
    TestSensorBothHighIsFault();
    TestSensorBothLowIsFault();
    TestMutualExclusionInvariantHoldsAcrossManyTicks();
    TestDisengageTimeoutRecoversToEngaged();
    TestClearFaultRecovers();
}
