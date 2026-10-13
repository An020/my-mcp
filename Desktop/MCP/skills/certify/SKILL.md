---
name: certify
description: "Full quality certification with badge"
---

# Command: certify

You are running the `certify` command from the `plugin-eval` plugin.

## Protocol

Run the complete PluginEval certification pipeline (all three layers + Elo ranking) and assign a quality badge.

This takes 15-20 minutes and uses your Max plan for all LLM calls.

## Running

```bash
cd plugins/plugin-eval
uv run plugin-eval certify {argument} --output markdown
```

Arguments: <path>

$ARGUMENTS

