# AI energy seed map

This file is a short note for the built-in `ai-energy` seed pool.

The runnable pool data lives in `ai_energy_pool_2026-05-19.csv`. The seed pool is kept for examples, tests, and regression coverage only; product work should target the broader `all-a` flow.

Rules:

- Treat the CSV as a review seed, not a complete securities master.
- Preserve `raw` fields and data quality flags when loading it.
- Keep public notes short and free of personal sources, accounts, local paths, tokens, and real holdings.
- Move durable concepts into reusable fields: industry, concepts, index membership, coverage state, research status, holdings exposure, and risk flags.
