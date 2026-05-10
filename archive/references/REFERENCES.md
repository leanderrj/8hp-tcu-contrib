# Reference materials — audit trail

Every external source cited in `proposals/` is listed here with its
canonical URL, what we use it for, and (once downloaded) a SHA-256
fingerprint so the file in this directory can be confirmed against
the original.

Files in this directory should be **downloaded manually by the user**
rather than fetched programmatically — Analog Devices, Mouser, and
Google Patents all serve their PDFs via JS / Cloudflare / login walls
that defeat `curl`. The audit value is preserved: each entry below
has the URL, the page hash if from a static source, and an explicit
"why we cite it" line.

## MAX22200 datasheet

**File:** `MAX22200_datasheet.pdf` *(not yet downloaded)*
**Canonical URL:** https://www.analog.com/media/en/technical-documentation/data-sheets/max22200.pdf
**Vendor page:** https://www.analog.com/en/products/max22200.html
**Cited in:** `proposals/tcm_max22200_binding/SOLENOID_BINDING.md`,
`proposals/firmware/solenoid_driver/` (when built).
**Why:** All claims in the binding doc about MAX22200 capabilities
(8 channels, 1 A RMS / channel, SPI daisy-chain, per-channel HIT/HOLD/T_HIT
register, fault-bit positions, drive topology) come from this datasheet.
The shipping firmware needs the register map verbatim.

To download (manually):
```
open https://www.analog.com/media/en/technical-documentation/data-sheets/max22200.pdf
# save as archive/references/MAX22200_datasheet.pdf
shasum -a 256 archive/references/MAX22200_datasheet.pdf >> archive/references/SHA256SUMS
```

## ZF 8HP clutch engagement schedule (SAE 2009-01-1083)

**File:** `SAE_2009-01-1083_ZF_8HP.pdf` *(paywalled, not redistributable)*
**Canonical URL:** https://www.sae.org/publications/technical-papers/content/2009-01-1083/
**Citation:** Greiner, J. and Grumbach, M., "8-Speed Automatic Transmission for
RWD Vehicles," SAE Technical Paper 2009-01-1083, 2009. DOI 10.4271/2009-01-1083.
**Cited in:** `proposals/firmware/shift_logic/clutch_table.h`.
**Why:** Source for the specific clutch engagement schedule encoded in
`kClutchTable`. The paper authoritatively documents which of the five shift
elements (A/B/C/D/E in our naming) is engaged in each gear, plus the
single-element-per-shift design property.

The paper is paywalled by SAE; copyright restricts redistribution. We do
not store it in this repo. The citation gives any auditor enough to
purchase / access it through SAE Mobilus or institutional library.

## ZF 8HP Ravigneaux gearset (US patent 7,789,799 B2)

**File:** `US7789799B2_zf8hp.pdf` *(not yet downloaded — public domain)*
**Canonical URL:** https://patents.google.com/patent/US7789799B2/en
**Direct PDF:** https://patentimages.storage.googleapis.com/  (path varies; use the
"Download PDF" button on the canonical URL)
**Inventors:** Diosi et al. (ZF Friedrichshafen AG), 2010.
**Cited in:** `proposals/firmware/shift_logic/clutch_table.h` (background),
`proposals/test_harness/plant_model.py` (when built — kinematic ratios).
**Why:** Public-domain disclosure of the 8HP Ravigneaux gearset layout
and the resulting forward gear ratios. Useful as a fallback / cross-check
against Greiner & Grumbach 2009.

To download (manually):
```
open https://patents.google.com/patent/US7789799B2/en
# Click "Download PDF" → save as archive/references/US7789799B2_zf8hp.pdf
shasum -a 256 archive/references/US7789799B2_zf8hp.pdf >> archive/references/SHA256SUMS
```

## openinverter forum threads

Already archived as markdown in `archive/forum/`:
- `thread6047_8HP_TCU.md`     — master 8HP TCU project thread
- `thread6926_VCU_V12.md`     — ZombieVerter VCU V1.2/1.3 hardware
- `thread7028_i4_logs.md`     — BMW i4 G26 CAN/LIN captures
- `thread7103.md`             — "Pump of Doom" LIN reverse engineering

These are the audit trail for the LIN pump protocol distillation, the
TCM pinout decoding, and the iX4 capture provenance.

## TCM pinout

Already archived: `archive/forum/TCM_Pinout.pdf` (posted by Damien Maguire
to thread #6047 on 2026-05-10).

## Verifying downloaded files

Once each file is in this directory, append its SHA-256 to `SHA256SUMS`:
```
shasum -a 256 *.pdf > SHA256SUMS
```

Future contributors can verify with `shasum -c SHA256SUMS`.

If a file ever needs to be re-downloaded and the SHA differs, check
whether the upstream document was revised before assuming corruption.
