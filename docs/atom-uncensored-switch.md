# Dual ATOM: permanent abliterated checkpoint

Deployment completed on 2026-09-06. This is an operator note for
the existing ATOM installation, not a portable default profile.

## Checkpoint and runtime

- Model: `lovesenko/GLM-5.3-Flash-tr3-4bpw-Abliterated`
- Revision: `c8f58e6aa9117c73607d692978b22f091d80450c`
- Recipe on head: `/home/kira/glm53-flash-exl3-eb0469f`
- Head HF cache: `/home/kira/glm53-flash-exl3-cache`
- Worker HF cache: `/home/kira/.cache/huggingface`
- Worker SSH alias from head: `ds4flash-worker` (DAC network)
- Served model name: `GLM-5.3-Flash-EXL3`; LiteLLM alias remains `glm53flash`.
- Existing EXL3 image, TP2, DFlash2 k=7, draft TP2, FP8 KV,
  `MAX_MODEL_LEN=1000000`, `GPU_MEM_UTIL=0.82`, `ABLIT=0`.

New and original checkpoints have identical config, tokenizer, processor,
quantization settings, and all 150,226 tensor names/shapes/dtypes. The 120 new
weight shards total 175,642,157,752 bytes. This structural comparison is not a
full numerical quality evaluation or a proof of 1M-context accuracy.

The head snapshot was hard-linked from the completed download into its own HF
repository cache, then copied to the worker with `rsync -a --partial` over DAC.
The downloaded source and head snapshot share inodes: do not edit either copy
of the weights in place.

The recipe `.env` pins MODEL and MODEL_FALLBACK to the same new repository,
and MODEL_REVISION to the commit above, preventing fallback to original weights.
Keep runtime ABLIT disabled: this checkpoint already contains weight edits.
No credentials belong in this document or Git.

## Runtime verification

- Worker has all 120 shards; the DAC rsync completed successfully.
- Engine logs confirm the pinned abliterated snapshot, TP2, DFlash2 k=7,
  FP8 KV and maximum sequence length 1,000,000.
- Reported KV cache capacity: 1,256,038 tokens.
- Health passed after 450 seconds; launcher completed its post-ready warmup.
- Through `http://192.168.0.135:4000/v1` and alias `glm53flash`, an arithmetic
  request returned `396` with `finish_reason=stop` (0.66 seconds for this tiny
  request; not a throughput benchmark).
- A tool-call request correctly returned `get_status({"host":"atom-2"})`
  with `finish_reason=tool_calls`. No actual status tool was executed.
- No full 1M-context or capability/refusal benchmark was performed.

## Start the prepared installation

On ATOM-2, after confirming both caches are complete and the known image is
already installed on both nodes:

```sh
cd /home/kira/glm53-flash-exl3-eb0469f
SKIP_DOWNLOAD=1 SKIP_SYNC=1 SKIP_PULL=1 SKIP_SHIP=1 SKIP_BUILD=1 \
  SKIP_OVERLAY_VERIFY=1 bash start.sh restart
```

These flags reuse the already-verified deployment and deliberately skip
artifact preparation. Do not copy this command to a fresh installation.
Restart interrupts the API. The launcher brings up worker before head and
waits for health followed by shape warmup. Verify actual MODEL_DIR on both
containers, then test a request through LiteLLM; health alone is insufficient.

## Roll back

The original weights remain available. The pre-switch configuration is
`.env.before-uncensored-20260906` in the recipe directory (contains private
deployment configuration; do not commit it).

On ATOM-2:

```sh
cd /home/kira/glm53-flash-exl3-eb0469f
cp -p .env .env.uncensored.saved
cp -p .env.before-uncensored-20260906 .env
SKIP_DOWNLOAD=1 SKIP_SYNC=1 SKIP_PULL=1 SKIP_SHIP=1 SKIP_BUILD=1 \
  SKIP_OVERLAY_VERIFY=1 bash start.sh restart
```

Verify the restored MODEL_DIR and a real completion before declaring rollback
successful. Keep both checkpoints until the new model has passed user workload
evaluation; DFlash acceptance and long-context quality require separate tests.
