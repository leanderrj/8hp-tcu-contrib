# PR draft: `iX4_Lever` for damienmaguire/Stm32-vcu

Status: branch ready locally, not yet pushed to fork, not yet opened
as a PR.

## Where it lives

| Resource | Path |
|---|---|
| Local working clone of fork | `/tmp/Stm32-vcu-fork/` |
| Branch | `feat/ix4-lever-bmw-g26` |
| Fork on GitHub | https://github.com/leanderrj/Stm32-vcu *(empty until pushed)* |
| Upstream | https://github.com/damienmaguire/Stm32-vcu |
| PR body draft | [`PR_BODY.md`](PR_BODY.md) |

## Verified

`make Test && ./test/test_vcu` against the patched fork prints
`All tests passed` covering 33 new iX4_Lever assertions plus the
existing throttle suite.

## Diff stats

```
 include/iX4_Lever.h       |  59 +++++++++++++++++++++
 include/param_prj.h       |   3 +-
 src/iX4_Lever.cpp         | 132 ++++++++++++++++++++++++++++++++++++++++++++++
 src/stm32_vcu.cpp         |   6 +++
 test/Makefile             |   5 +-
 test/canhardware_stub.cpp |  12 +++++
 test/test_fixtures.h      |  33 ++++++++++++
 test/test_iX4_Lever.cpp   |  97 ++++++++++++++++++++++++++++++++++
 test/test_list.h          |   7 ++-
 9 files changed, 351 insertions(+), 3 deletions(-)
```

## To open the PR

```bash
# 1. Push the branch to the fork
cd /tmp/Stm32-vcu-fork
git push -u origin feat/ix4-lever-bmw-g26

# 2. Open the PR with the prepared body
gh pr create \
  --repo damienmaguire/Stm32-vcu \
  --base master \
  --head leanderrj:feat/ix4-lever-bmw-g26 \
  --title "Add iX4_Lever shifter for BMW G-chassis (G26 i4)" \
  --body-file /Users/leanderrj/Code/8hp-tcu-contrib/proposals/contributions/stm32_vcu_ix4_lever/PR_BODY.md
```

Stopping before either step so you can review the local diff first.
