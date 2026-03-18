## Experiment Memory (auto-generated 2026-03-18 08:31)

**Status:** Baseline — first-run setup complete. No training runs completed yet.

**Platform:** No GPU detected in current environment — experiments to be run on CUDA-capable host.

**Baseline configuration (from model.json):**
- Architecture: `depth=8, aspect_ratio=128, head_dim=64, window_pattern=SL`
- Model dim: `8 × 128 = 1024`, heads: `1024 / 64 = 16`
- Batch: `total_batch_size=2^17=131072`, `device_batch_size=16`, `grad_accum=4`
- LR: `matrix=0.01, embedding=0.1, unembedding=0.002, scalar=0.25`
- Schedule: `warmup=0.20, warmdown=0.75, final_lr_frac=0.1`
- Time budget: `test=60s`, `train=300s` (ground.json, mode=test)

**Orientation checklist (program.md §1):**
- [x] Read ground.json — mode=test, time_budget_test=60s
- [x] Read model.json — depth=8, SL window pattern, 1024-dim
- [x] Read prepare.py — platform detection, dataloader, evaluate_bpb exports
- [x] Read train.py — GPT model, MuonAdamW optimizer, 5-min training loop
- [x] Metric: val_bpb (bits per byte), lower is better

**Infrastructure setup (program.md §4 first-run):**
- [x] sessions/ directory created
- [x] results.tsv initialized with header
- [ ] uv run prepare.py (requires network + ~2 min)
- [ ] baseline training run

**Experiment-1 hypothesis (applied):**
Change: `warmup_ratio` `0.20` → `0.10` in model.json.
Reasoning: The warmdown schedule starts at `progress = 1 - warmdown_ratio = 1 - 0.75 = 0.25`.
With `warmup_ratio=0.20`, the full-LR window is only `0.25 - 0.20 = 0.05` (5% of budget = 15s).
With `warmup_ratio=0.10`, the full-LR window becomes `0.25 - 0.10 = 0.15` (15% of budget = 45s) —
a 3× increase in time at peak LR. The Muon momentum ramp (independent, over 300 steps) provides
gradient stabilisation, so a shorter LR warmup carries low risk of divergence.
Expected outcome: improved val_bpb from more effective high-LR training steps.
