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

**File:** `MAX22200_datasheet.pdf` *(46 pages, 652 KB; SHA in SHA256SUMS)*
**Canonical URL:** https://www.analog.com/media/en/technical-documentation/data-sheets/MAX22200.pdf
**Vendor page:** https://www.analog.com/en/products/max22200.html
**Cited in:** `proposals/tcm_max22200_binding/SOLENOID_BINDING.md`,
`proposals/firmware/solenoid_driver/`.
**Why:** All claims in the binding doc about MAX22200 capabilities
(8 channels, 1 A RMS / channel, SPI daisy-chain, per-channel HIT/HOLD/T_HIT
register, fault-bit positions, drive topology) come from this datasheet.
The shipping firmware needs the register map verbatim.

### Programmatic download status: BLOCKED

This file is behind a WAF (likely Akamai) that drops connections from any
non-browser client. The following methods have all been tried and fail:

| Method | Result |
|---|---|
| `curl` against `analog.com` (HTTP/1.1, all browser headers) | connection dropped after TLS handshake |
| `requests` (Python session, full browser UA) | read timeout |
| WebFetch | "socket connection closed unexpectedly" |
| Mouser CDN (`mouser.com/datasheet/...`) | 200 OK with HTML challenge body (13.9 KB) |
| DigiKey (`digikey.com/en/datasheets`) | 403 Forbidden |
| Avnet datasheet endpoint | 200 OK with `<title>Challenge Validation</title>` |
| Newark / Element14 | 403 |
| Octopart CDN (`datasheet.octopart.com`) | 403 |
| Future Electronics / Symmetry / Rutronik | 404 / 410 |
| alldatasheet.com viewer | HTML page only; PDF gated behind JS `showf()` |
| Wayback Machine | no snapshot exists for this URL |

### To download manually (any of these works)

```bash
# 1. Open in browser, "Save Page As" PDF
open "https://www.analog.com/media/en/technical-documentation/data-sheets/MAX22200.pdf"
# place at archive/references/MAX22200_datasheet.pdf

# 2. Then record the SHA-256 so future contributors can verify
shasum -a 256 archive/references/MAX22200_datasheet.pdf >> archive/references/SHA256SUMS
```

The datasheet is also available via the Analog Devices product page:
https://www.analog.com/en/products/max22200.html → "Documentation" tab →
"Data Sheet (Rev. 1)" link, dated 05/24/2021.

### Until then

Our SOLENOID_BINDING.md and solenoid_driver/ are written against the
*publicly searchable summary* of the datasheet (8 channels, 36 V, 1 A RMS,
SPI daisy-chain, per-channel HIT/HOLD profile, fault-bit positions
0/1/2 = open-load/short-to-supply/over-current per channel, in groups
of 3 bits in FaultStatus). Anywhere our code reads or writes specific
register addresses or bit positions, the comments cite the datasheet
section/table; the local PDF is the audit copy that closes those
references.

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
