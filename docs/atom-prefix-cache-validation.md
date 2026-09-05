# Atom development prefix-cache overlay

This branch integrates upstream `3021f24` and PR 125 (`318795b`, still open at
review time). It preserves the fork's eight-image default and native
`VLLM_API_KEY` transport. Upstream now implements the same key transport.

PR 125 enables the existing fine-grained lookup path by excluding transient
groups from its eligibility check. It changes no physical KV page sizes,
weights, kernels, sampling, or Mamba state layout. The DCP and partial-Mamba
eligibility gates remain intact. Reusable MLA and Mamba groups continue to
constrain the hybrid cache minimum; KpoolTail remains request-local scratch.

The local overlay adds three conservative checks to PR 125:

- Only an explicit `participates_in_prefix_caching is False` opts a manager out.
- Manager/spec lists must have equal lengths (`zip(..., strict=True)`).
- All installed patch blocks must be present exactly once, and the final source
  must compile before any write. Markers alone do not bypass validation.

The existing drafter-window behavior is unchanged. PR 130 is not included.

## Minimal deployment

Only `overlay/patch_hybrid_prefix_hit.py` is needed to change runtime behavior.
The existing launcher mounts it on both nodes and applies it before vLLM starts.
With the currently verified E2 image and `SKIP_BUILD=1`, no image rebuild is
required. Keep the previous overlay and environment beside the known-good image
tag for rollback; restore them and restart the cluster to undo the experiment.

The two optional validation files are `tests/test_hybrid_prefix_hit.py` and
`tests/test_hybrid_prefix_hit_safety.py`. The first uses
`GLM53_KV_COORDINATOR_PY_SRC` to select an actual coordinator source, then applies
the patch to a temporary copy. The second is CPU-only and needs no vLLM import.
The Dockerfile also runs both tests on future full image builds.

## Local validation

The coordinator copied from the running Atom image accepted the additive patch,
compiled, and accepted a second identical application. Fourteen CPU tests cover
eligibility, MLA/Mamba minimum constraints, transient-tail classification,
additive upgrades, idempotence, malformed source, and fail-closed behavior.

Launcher caller overrides, eight-image defaults, API-key transport (2 tests),
chat-template behavior (7 tests), bring-up anchors, and `bash -n start.sh` passed.
The newly merged caller-override tests reuse the existing Git Bash path helper
on Windows. The numeric-config suite also passed on the Atom's Linux host;
the Windows Git Bash literal-carriage-return argument issue was therefore
isolated to that test environment.

Before deployment, copies of the coordinator from both live containers had
SHA256 `1f4f11011bff2a4aab1f0deaaa1c77878c354e939e19441064bd56933c50919d`.
Both passed additive installation, compilation and idempotence checks. The
14 CPU safety tests also passed on the Atom host without changing live source.

An image already carrying the original PR 125 fine-grained marker, without
these extra checks, is deliberately rejected by installed-source verification.
Preflight the exact image before switching; do not bypass a mismatch. This
deployment starts from the earlier hybrid overlay, which was verified above.

These source checks do not establish output equivalence or performance on the
two GPUs. Retention decisions require live cold/warm semantic and coding
canaries, prompt/cache counters, TTFT, decode speed, and engine health.

## Live Atom validation, 2026-09-05

The unchanged E2 image (`sha256:27777801ee6570a705e8732631debf18e43854fe029c77774a214488c5f943c7`)
started on both nodes with this mounted overlay. Both installed coordinators
had SHA256 `a31d38775b59f9981cc6f969f240ed2b6ef77270dd579131e24cebe7989be584`.

At MNBT 2048 with `GLM53_INDEXER_WORKSPACE=rightsize`, two repetitions of the
development quick suite passed all 12 requests, including exact marker lookup,
append-only continuation, tool arguments and thinking-enabled code validated
against 18 interval-merging cases. No request was truncated and no external
traffic or preemption was detected. The approximately 13.7K-token continuation
computed 32 tokens rather than the baseline's roughly 2,977; approximately
27.5K-token continuations computed 92 rather than 2,393. These are small
synthetic canaries, not proof of unrestricted long-context output equivalence.

The control-plane repository contains the workload, raw results and subsequent
batch-size comparisons. Its report distinguishes cache latency, KV capacity,
decode throughput and variable reasoning length.

Source: <https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks/pull/125>
