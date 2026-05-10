# PR draft: firmware skeleton + OEM connector model for damienmaguire/8HP-TCU

Status: branch ready locally, **not yet pushed** to fork, **not yet
opened** as a PR. Stopping here pending review.

## Where it lives

| Resource | Path |
|---|---|
| Local working clone of fork | `/tmp/8HP-TCU-fork/` |
| Branch | `feat/firmware-skeleton-and-connector-model` |
| Fork on GitHub | https://github.com/leanderrj/8HP-TCU |
| Upstream | https://github.com/damienmaguire/8HP-TCU |
| PR body draft | [`PR_BODY.md`](PR_BODY.md) |

## Verified

```
cd /tmp/8HP-TCU-fork/Software/test
make
./test_8hp
=> All tests passed
```

35 host assertions across the three firmware modules. Stock g++ -std=c++17.
No libopencm3, no libopeninv, no peripheral access.

## Diff stats vs upstream/main

```
26 files changed, 3054 insertions(+), 1 deletion(-)
  Hardware/OEM_Connector_Model/  5 files (CSV + generator + .kicad_sym + README)
  Software/                       21 files (3 modules + test harness + READMEs)
```

Two commits, scope-disciplined:
1. `Hardware: add OEM Mechatronik connector KiCad model` — purely
   additive in Hardware/.
2. `Software: add firmware skeleton (shift_logic, park_lock,
   solenoid_driver)` — replaces the placeholder Software/test.a.

## Honest reservation

I argued in the prior conversation thread that this PR is parallel
work rather than addition to Damien's track. Submitting it anyway is
the user's call. The PR body (`PR_BODY.md`) frames it explicitly as
"work that happens to fit your folder structure cleanly, pull or
ignore freely."

The scope was kept tight to limit overreach:
- No DBC.
- No CAN protocol claim.
- No bind layer.
- No SPI driver.
- No PCB layout.

Only the three CAN-agnostic firmware modules + the connector symbol
library that uses Damien's published pinout.

## To open the PR

```bash
# 1. Push the branch to the fork
cd /tmp/8HP-TCU-fork
git push -u origin feat/firmware-skeleton-and-connector-model

# 2. Open the PR with the prepared body
gh pr create \
  --repo damienmaguire/8HP-TCU \
  --base main \
  --head leanderrj:feat/firmware-skeleton-and-connector-model \
  --title "Software: firmware skeleton + Hardware: OEM connector KiCad model" \
  --body-file /Users/leanderrj/Code/8hp-tcu-contrib/proposals/contributions/8hp_tcu_software_skeleton/PR_BODY.md
```

Stopping before either step.
