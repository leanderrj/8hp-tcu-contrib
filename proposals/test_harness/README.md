# Capture-replay test harness

Python pytest harness that pairs with the C++ host tests in
`proposals/firmware/`. The C++ tests cover hand-picked fixtures; this
harness replays the **full corpus** of captured frames against a Python
reference decoder, plus DBC round-trip property tests.

## Layout

```
proposals/test_harness/
├── pyproject.toml             dependencies (cantools, pytest)
├── conftest.py                pytest fixtures (capture paths, DBC path)
├── replay.py                  SavvyCAN CSV loader, helpers
├── ix4_lever.py               Python ref impl mirroring iX4_Lever.cpp
└── tests/
    ├── test_ix4_lever_full_capture.py
    └── test_dbc_roundtrip.py
```

## Run

```
cd proposals/test_harness
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
pytest
```

## What it covers

- **iX4_Lever full corpus replay** — every one of the 553 captured 0x3F9
  frames from `archive/captures/` decoded with the same CRC8/0x1D,
  counter, and gear-byte logic as the C++ class. Asserts the global
  invariants the C++ test can't easily express:
  - 553/553 frames CRC-validate
  - byte-1 high nibble is always 0xF
  - byte 6 only ever holds {0x31, 0x32, 0x33, 0x35} across the corpus
    (a future capture introducing 0x34 will flag here, prompting us to
    extend the mapping)
  - the poweroff and idrive-buttons captures keep gear in PARK
  - the rotation capture visits every gear and ends back in PARK

- **DBC round-trip** — encode → bytes → decode → struct identity for
  every message in the protocol, plus targeted scaling tests
  (0.01 km/h, 0.1 V, 0.1 bar) and the pump-state enum width check.
  This catches schema drift between the DBC and the generated C source.

## Why this exists

The C++ unit tests need fixtures bundled into a `.h` file — practical
for 12 frames, brittle for 553. The pytest harness reads the original
SavvyCAN CSVs directly, so the test set grows automatically with each
new capture posted on the forum.

## Adding a new capture

Drop the file in `archive/captures/`, add its name to `CAPTURE_FILES`
in `conftest.py`. If it's a vehicle that should pass the same
invariants, the existing tests pick it up automatically; if it's a
new vehicle / gearbox, add a dedicated test module.
