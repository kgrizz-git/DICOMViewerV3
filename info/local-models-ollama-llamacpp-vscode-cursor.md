# Running Local AI Models with Ollama and llama.cpp (VS Code and Cursor)

Last updated: 2026-04-05

## Why this file exists

This is a practical guide for running modern open models locally and connecting them to AI-first coding workflows.

Focus areas:
- Ollama and llama.cpp runtime options
- VS Code and Cursor integration patterns
- What is realistic on consumer Apple Silicon, Apple desktop class systems, and RTX 4090 systems
- Current model families to watch: Qwen3.5 / Qwen3-Coder-Next, Gemma4, plus a few others

## Quick reality check

- There are now many "latest" models with huge total parameter counts that still run locally via quantization or MoE active-parameter tricks.
- Local viability is mostly a memory question first, then throughput.
- Context length can dominate memory use. A model that "fits" at 8K context may fail at 128K to 256K context.

## Local runtimes

### Ollama

Ollama exposes a local API by default:
- Base: `http://localhost:11434/api`

Tag note:
- `ollama pull gemma4` resolves to `gemma4:latest`
- At the time of writing, `gemma4:latest` points to `gemma4:e4b`
- If you need stable behavior over time, prefer explicit tags such as `gemma4:e2b`, `gemma4:e4b`, `gemma4:26b`, or `gemma4:31b`

Example:

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "gemma4",
  "prompt": "Summarize the key differences between Q4 and Q5 quantization.",
  "stream": false
}'
```

### llama.cpp

llama.cpp supports:
- Apple Metal acceleration on macOS
- CUDA on Nvidia
- OpenAI-compatible server mode (`llama-server`)
- Quantization from very low bit to higher bit formats (including modern K-quant families)

Example server launch:

```bash
llama-server -m /path/to/model.gguf --port 8080
# OpenAI-compatible chat endpoint: http://localhost:8080/v1/chat/completions
```

### Unsloth Studio

Unsloth Studio is a local web UI that sits a bit higher in the stack than Ollama or raw llama.cpp.

What it is good at:
- Running GGUF and safetensor models locally in a GUI
- Side-by-side model comparison
- Built-in code execution, web search, and tool-calling workflows
- No-code dataset preparation and fine-tuning workflows
- Exporting trained models back out to GGUF or safetensors for use with llama.cpp, Ollama, LM Studio, and similar stacks

Important current constraint:
- On Mac and CPU-only systems, Unsloth Studio currently supports chat inference and data recipes, but not full local training yet
- Current local training support is aimed at Nvidia and Intel GPU systems
- Unsloth documents Apple MLX training support as coming soon

Practical takeaway:
- If your goal is local inference plus IDE use, Ollama or llama.cpp remain the simpler base layer
- If your goal includes dataset prep, LoRA-style experimentation, export, and model comparison in one place, Unsloth Studio is worth knowing about

Quickstart:

```bash
curl -fsSL https://unsloth.ai/install.sh | sh
unsloth studio -H 0.0.0.0 -p 8888
```

## IDE integration

## Ollama integrations list (from docs overview)

Source: https://docs.ollama.com/integrations

### Coding Agents

- Claude Code
- Codex
- OpenCode
- Droid
- Goose
- Pi

### Assistants

- OpenClaw

### IDEs & Editors

- VS Code
- Cline
- Roo Code
- JetBrains
- Xcode
- Zed

### Chat & RAG

- Onyx

### Automation

- n8n

### Notebooks

- marimo

## VS Code

There are now first-party Ollama docs for VS Code integration.

Fast path:

```bash
ollama launch vscode
```

This wires Ollama models into the VS Code model picker (Copilot Chat with local model selection enabled). You can also set up manually from the model picker and add Ollama models.

Also common in VS Code:
- Cline: set API provider to Ollama
- Roo Code: set API provider to Ollama and base URL `http://localhost:11434`

## Cursor

Cursor docs clearly support MCP for connecting external/local tools and services.

Practical local-model pattern in Cursor:
1. Run a local OpenAI-compatible model server (Ollama API or llama-server).
2. Expose tooling via MCP (stdio or HTTP transport).
3. Let Cursor call MCP tools that forward prompts to your local model endpoint.

This gives a robust path for local inference in Cursor workflows even when your main chat model is cloud-hosted.

## Quantization and sizing heuristics

Use this as a planning rule of thumb:

- Required memory ~= model weights + KV cache + runtime overhead
- Runtime overhead is often significant (roughly 15% to 40% depending on engine, backend, and features)
- Higher context length can multiply KV cache costs

General guidance:
- Q4 class: best default for many local setups
- Q5/Q6: better quality, more memory
- Q8/F16: highest quality, large memory cost

From current Qwen3-Coder-Next GGUF examples:
- Q4_K_M: ~48.4 GB
- Q5_K_M: ~56.7 GB
- Q6_K: ~65.5 GB
- Q8_0: ~84.8 GB
- F16: ~159 GB

This one data point is useful because it quickly shows why very large models often need either:
- very high unified memory (Apple desktop class), or
- multi-GPU / CPU offload strategies

## What runs where (practical matrix)

## Consumer Apple Silicon (typical 16 GB to 64 GB unified memory)

Good fits:
- Gemma4 E2B / E4B class
- Qwen3.x small-mid variants (for coding/chat) with Q4 or Q5
- Phi4 / Llama 3.x 7B to 14B class quants

Possible with care:
- 20B to 30B-class quants at lower context and tuned settings

Usually not ideal:
- 70B+ dense models at useful speed on lower-memory laptops
- Very long context at high quality quants

## Apple desktop class (Mac Studio or Mac Pro class, high unified memory)

If you have 128 GB to 192 GB unified memory, you can realistically test much larger quants locally, including:
- Qwen3-Coder-Next GGUF at Q4/Q5 class (memory still heavy, speed varies)
- Gemma4 26B A4B / 31B variants with more headroom
- Larger long-context experiments that would fail on laptops

Important:
- You still need to tune context length and batch size aggressively for stability and throughput.

## RTX 4090 systems (24 GB VRAM)

Strong for:
- 7B to 14B class high-throughput local coding/chat
- 20B to 30B class in 4-bit regimes depending on architecture and context

Constraints:
- 24 GB VRAM is excellent but not enough for full offload of many very large GGUF models (for example Qwen3-Coder-Next Q4 at ~48.4 GB model file size)
- You may need CPU offload / partial GPU layer offload

llama.cpp note:
- CUDA + unified memory fallback options can keep runs alive when VRAM is exceeded, but with performance tradeoffs.

## Buying guidance under about $5000

For a coding-first local AI box, there are really three sensible directions.

## Best Mac for local inference

- Mac Studio M3 Ultra starting at $3999
- Main reason to buy it: up to 256 GB unified memory, which is the cleanest path to running much larger local quants without multi-GPU complexity
- Best fit: you mainly want local inference, larger GGUFs, quiet operation, low power draw, and minimal systems friction

What to expect:
- Better capacity than a single consumer Nvidia card for very large local models
- Much weaker choice if you want to do serious local fine-tuning or training experiments today
- Best Mac recommendation: prioritize memory over SSD; if budget allows, favor the highest-memory Mac Studio configuration you can reach before overspending on storage

## Best Nvidia workstation under this budget

- Single-GPU Windows or Linux tower built around an RTX 5090
- RTX 5090 starting point: $1999 with 32 GB GDDR7 and much higher memory bandwidth than RTX 4090
- Typical target total build budget: about $3500 to $5000 depending on CPU, RAM, and storage

Suggested shape:
- RTX 5090
- 96 GB to 192 GB system RAM
- 2 TB to 4 TB NVMe storage
- strong but sensible CPU, good PSU, and cooling

Why this is the default recommendation for most technical users:
- Best local option here for LoRA, QLoRA, toy fine-tuning, and training experiments
- Best compatibility with CUDA-first tooling across PyTorch, vLLM, llama.cpp CUDA, and training stacks like Unsloth
- Still excellent for coding-oriented inference on 7B to 32B-class models and many quantized larger models

Main limitation:
- 32 GB VRAM is still a hard ceiling for many larger models, so this is more flexible for training than it is spacious for giant-model inference

## Best compromise if you want to spend less

- RTX 4090 system
- RTX 4090 starting point: $1599 with 24 GB GDDR6X
- A balanced full build can often land around $2800 to $4000

Who it is for:
- You want a serious local coding box now
- You want to try fine-tuning and training toy models
- You do not want to pay the 5090 premium yet

What you give up versus 5090:
- Less VRAM headroom
- Less memory bandwidth
- Less future margin for newer local training and inference workloads

## Bottom line

- If your priority is running the biggest local models conveniently, buy the highest-memory Mac Studio you can justify
- If your priority includes even occasional fine-tuning, training, or broader ML tooling, buy Nvidia
- For your stated use case, coding first plus possible toy training, a single-GPU Nvidia tower is still the better buy
- If budget is tight, RTX 4090 is still strong
- If budget stretches comfortably to it, RTX 5090 is the cleaner recommendation in 2026

## Current model-family notes (2026 snapshot)

## Qwen

Current signals show active Qwen3.5 family rollout, including:
- large multimodal variants
- 4-bit GPTQ releases (for example Qwen3.5-27B-GPTQ-Int4)
- coding-specialized Qwen3-Coder-Next (80B total, ~3B active) and GGUF distributions

Practical implication:
- Great local coding potential in smaller or quantized variants
- flagship variants still require serious memory planning

## Gemma4

Gemma4 family now includes:
- E2B / E4B on-device oriented models
- 26B A4B MoE model (lower active params)
- 31B dense model

Practical implication:
- E2B/E4B are strong local defaults
- 26B A4B gives a compelling quality/speed middle path when hardware is limited
- 31B is better suited to higher-memory desktops/workstations

## Two additional families worth tracking

- DeepSeek-R1 distilled variants: strong reasoning value per parameter on local systems
- Llama 3.x/4 ecosystem: very broad quant/tooling availability across Ollama + GGUF flows

## Minimal setup recipes

## Recipe A: easiest local stack (Ollama + VS Code)

```bash
# Install Ollama (macOS)
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull gemma4

# Launch VS Code integration
ollama launch vscode
```

## Recipe B: OpenAI-compatible local endpoint for toolchains

Option 1 (Ollama API):
- Use `http://localhost:11434/api` endpoints directly

Option 2 (llama.cpp server):

```bash
llama-server -m /models/your-model.gguf --port 8080
# Chat endpoint: http://localhost:8080/v1/chat/completions
```

Then point local-agent tools or middleware at that endpoint.

## Recipe C: local training and export workflow with Unsloth Studio

Good fit when you want a UI for dataset prep, LoRA-style experimentation, and export back to your normal inference runtime.

Typical flow:
1. Launch Unsloth Studio locally.
2. Load a base model from local files or a supported source.
3. Import PDFs, CSV, JSON, or JSONL training material.
4. Use Data Recipes to reshape the data.
5. Fine-tune on a supported Nvidia setup.
6. Export to GGUF or safetensors.
7. Run the exported model in llama.cpp or Ollama for normal use in VS Code or Cursor.

## Benchmarking before committing to a model

Before adopting any model for real work:
1. Run a short quality suite (your real prompts, not benchmarks only).
2. Run a throughput test at your target context sizes.
3. Verify memory behavior over long sessions (not just one-off prompts).
4. Keep one "safe fallback" model that is smaller and always reliable.

## Source notes (high level)

This guide was built from current upstream docs/pages including:
- Ollama docs and integrations pages
- Ollama model library/search pages
- llama.cpp README/build/quantize documentation
- Unsloth Studio docs
- Hugging Face model cards for current Qwen and Gemma4 releases
- NVIDIA RTX 4090 specs page
- NVIDIA RTX 5090 specs page
- Apple technical specs pages for current Apple Silicon Mac classes

Because model releases move fast, re-check model cards and runtime release notes before buying hardware specifically for one model.
