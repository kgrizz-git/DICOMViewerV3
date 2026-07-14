# Local PII / PHI detection model options

**Last updated:** 2026-07-14

> **Status:** research and evaluation reference only. No model described here is
> installed in the application, invoked by the repository hooks, or permitted to
> replace an existing privacy control.

## Purpose

This note records locally runnable candidates for an *optional* defense-in-depth
PII/PHI review. The intended use is to flag possible sensitive text in a
developer-controlled scan before review or export. It is not a claim that a file,
study, image, or output has been de-identified.

The canonical repository rules remain in
[PHI / PII Repository Guardrails](../PHI_PII_REPOSITORY_GUARDRAILS.md). In
particular, the blocking gate already scans tracked text and recursively scans
DICOM metadata, while a human review and OCR where appropriate are still required
for burned-in image text. A text model cannot inspect DICOM pixels or make the
image review unnecessary.

## Non-negotiable operating constraints

- Keep this capability **local, opt-in, and warning-only** until a synthetic-corpus
  evaluation establishes a narrow, documented use case. A model finding must not
  be the only reason an export is classified as safe.
- Use wholly synthetic input for development, automated tests, benchmarks, and
  issue examples. Never send real patient data to a model service, chat, test log,
  CI artifact, or source-control system.
- A finding report must contain the file path, category, score, and a safe
  position/range indicator only. It must not echo the matched value.
- Run optional tools in a dedicated virtual environment. The existing
  [`requirements-phi-tools.txt`](../../requirements-phi-tools.txt) documents why
  `phi-scan` and Presidio must not be installed with the application environment.
- Preserve the existing deterministic DICOM checks, logging protections, hash
  manifest, and visual/OCR review. These models are an additional signal, not a
  replacement or a HIPAA/PS3.15 conformance assertion.

## Candidate matrix

| Candidate | Type and local integration | Download / footprint | Appropriate role | Important limits |
|---|---|---:|---|---|
| [`nvidia/gliner-PII`](https://huggingface.co/nvidia/gliner-PII) | GLiNER span detector, loaded through the Python `gliner` package | 570M parameters; 1.79 GB repository download (1.78 GB checkpoint) | Primary specialized PII/PHI text-detector candidate | Text only; NVIDIA documents Linux/NVIDIA/CPU environments, not an Apple Silicon support guarantee. Use an MPS/CPU proof of concept before relying on Mac performance. |
| [OpenAI Privacy Filter](https://openai.com/index/introducing-openai-privacy-filter/) | Open-weight bidirectional token-classification model with its own local CLI/runtime | 1.5B total parameters, 50M active; up to 128,000 tokens | Primary specialized PII text-detector candidate and direct comparison with NVIDIA GLiNER | Fixed eight-category taxonomy; it omits many medical-specific categories, so it cannot stand in for DICOM tag rules or a PHI-specific evaluation. |
| [`gretelai/gretel-gliner-bi-small-v1.0`](https://huggingface.co/gretelai/gretel-gliner-bi-small-v1.0) | Smaller GLiNER PII/PHI fine-tune, loaded through `gliner` | 768 MB repository download (757 MB checkpoint) | Lower-footprint comparison or fallback | Same broad GLiNER approach; useful for a size/quality comparison, not a sufficiently independent safety control by itself. |
| [`obi/deid_roberta_i2b2`](https://huggingface.co/obi/deid_roberta_i2b2) | Token-classification model, loaded through Hugging Face Transformers | 0.4B parameters; 1.42 GB `safetensors` checkpoint | Independent clinical-note PHI review candidate | Trained for 11 PHI categories in medical notes; it is not a general DICOM-metadata or image scanner. |
| [Microsoft Presidio](https://microsoft.github.io/presidio/) | Analyzer/anonymizer framework, recognizer registry, regex rules, NLP engines, and adapters | Dependency and model dependent | Composition layer for rules plus one or more models | It is not a PHI model and does not parse DICOM pixels or metadata natively. OCR is separately required for image redaction. |
| [`openai/gpt-oss-20b`](https://developers.openai.com/api/docs/models/gpt-oss-20b) | General-purpose, open-weight reasoning model; run through a supported local runtime such as LM Studio | 21B parameters, 3.6B active; OpenAI states a 16 GB memory target | Experimental, schema-constrained second-pass reviewer | Not a trained PII/PHI detector; its generated result has no stable span-detection semantics and must never be a sole gate or an automatic redactor. |
| [`openai/gpt-oss-120b`](https://openai.com/open-models/) | Larger open-weight general-purpose model | Materially larger than `gpt-oss-20b` | Future quality/latency comparison only | Not a specialized detector. Do not evaluate first just because 128 GB unified memory may make loading feasible. |

`phi-scan` remains an existing optional-tool candidate from
[`requirements-phi-tools.txt`](../../requirements-phi-tools.txt). It should be
evaluated as a rule-based/heuristic complement, not described as a substitute for
any of the models above.

### NVIDIA GLiNER PII

NVIDIA describes GLiNER PII as a non-generative model that returns annotated
text spans with labels and confidence scores across 55+ PII/PHI categories. Its
model card reports 570M parameters and recommends domain-specific validation and
human review. It is the best first model to spike because it is specialized for
the task, much smaller than a general LLM, and its requested labels can be
restricted to the categories relevant to a scan.

The upstream checkpoint is a PyTorch `pytorch_model.bin`, not a GGUF or MLX
model. It therefore cannot be loaded directly into LM Studio. Use an isolated
Python environment and `GLiNER.from_pretrained(...)`; expose it through a local
CLI or an internal loopback-only service only if the spike justifies that extra
surface.

Sources: [NVIDIA model card](https://build.nvidia.com/nvidia/gliner-pii/modelcard)
and [Hugging Face files](https://huggingface.co/nvidia/gliner-PII/tree/main).

### OpenAI Privacy Filter

OpenAI released Privacy Filter in April 2026 as an Apache-2.0 open-weight model
for local detection and masking of PII in text. It is a non-generative,
bidirectional token-classification model with constrained span decoding—not a
chat model. The released model has 1.5B total parameters with 50M active
parameters, supports inputs up to 128,000 tokens, and is intended for
high-throughput local workflows.

Its fixed label taxonomy is `private_person`, `private_address`,
`private_email`, `private_phone`, `private_url`, `private_date`,
`account_number`, and `secret`. That makes it a strong candidate for text,
source, logging, and secret review, but it does not explicitly cover many
medical/DICOM concepts such as a medical-record number, accession number, health
plan number, or clinical free-text semantics. Test it directly against the
chosen local PHI policy rather than treating its name as a de-identification
guarantee.

OpenAI supplies its own local `opf` CLI, evaluation tooling, and fine-tuning
path. It is not a GGUF/MLX LM Studio chat model, so run it in its documented
Python environment. If it is composed with Presidio, use a custom recognizer
adapter unless a supported direct interoperation path is documented; preserve
the model's span boundaries and score without logging the matched text.

Sources: [OpenAI's announcement](https://openai.com/index/introducing-openai-privacy-filter/),
[model card](https://cdn.openai.com/pdf/c66281ed-b638-456a-8ce1-97e9f5264a90/OpenAI-Privacy-Filter-Model-Card.pdf),
[local runtime and CLI repository](https://github.com/openai/privacy-filter), and
[model weights](https://huggingface.co/openai/privacy-filter).

### Gretel GLiNER PII/PHI variants

The Gretel small, base, and large models are GLiNER PII/PHI fine-tunes. The
small model is the sensible low-footprint comparison; the published repository
download is 768 MB and its license is Apache-2.0. The model card reports results
on its synthetic-data evaluation, so do not transfer its reported score directly
to clinical notes, DICOM tags, application logs, or this repository's fixtures.

The small, base, and large options use the same package interface. If this family
is evaluated, keep the exact model ID, revision, label set, threshold, and test
corpus version in the result record.

Sources: [small model card](https://huggingface.co/gretelai/gretel-gliner-bi-small-v1.0),
[small files](https://huggingface.co/gretelai/gretel-gliner-bi-small-v1.0/tree/main),
and [base model card](https://huggingface.co/gretelai/gretel-gliner-bi-base-v1.0).

### Clinical-note de-identification model

`obi/deid_roberta_i2b2` is a RoBERTa token-classification model fine-tuned for
medical-note de-identification. Its card identifies 11 PHI categories and the
i2b2 2014 training set. It is worth testing because its architecture, training
data, and fixed label taxonomy differ from GLiNER's prompted-label approach.

Prefer the published `model.safetensors` file over its legacy pickle-style
checkpoint. Do not use this model outside its clinical-note scope without a
measured synthetic evaluation.

Sources: [model card](https://huggingface.co/obi/deid_roberta_i2b2) and
[safe-tensors file listing](https://huggingface.co/obi/deid_roberta_i2b2/tree/main).

## Presidio: wrapper and composition layer

Yes: Presidio can provide a common analyzer/redaction pipeline around some of
these models, but it does **not** automatically wrap every Hugging Face or
GLiNER checkpoint.

- Presidio combines its recognizer registry with regex/context recognizers and an
  NLP engine. It supports spaCy, Stanza, and Transformers-backed NLP engines, and
  documents that multiple NER models can be combined.
- `obi/deid_roberta_i2b2` is a conventional token-classification candidate for a
  Transformers-backed Presidio configuration, provided its labels are explicitly
  mapped to the project's chosen entity taxonomy.
- GLiNER predicts spans from labels supplied at inference time rather than
  exposing the usual fixed token-classification pipeline. Integrate it as a
  custom Presidio `EntityRecognizer` adapter that calls GLiNER, maps its labels
  to Presidio entity names, preserves the score, and applies a deterministic
  overlap policy. Do not assume that merely selecting
  `TransformersNlpEngine` makes GLiNER work.
- Privacy Filter has a fixed span taxonomy but its own local inference and
  decoding implementation. Treat it like GLiNER for integration purposes: plan
  a custom recognizer adapter unless a maintained Presidio integration becomes
  available, and map only its eight documented categories.
- Presidio's image redactor is a different path: it needs local OCR and an NLP
  engine. It may help review rasterized screenshots or exports, but it does not
  understand native DICOM pixel data and must remain separate from the DICOM
  metadata gate.

Sources: [Presidio analyzer architecture](https://github.com/microsoft/presidio/blob/main/docs/analyzer/index.md),
[NLP model/language configuration](https://microsoft.github.io/presidio/tutorial/05_languages/),
and [installation and Transformer requirements](https://microsoft.github.io/presidio/installation/).

## OpenAI and LM Studio option

OpenAI's `gpt-oss-20b` is the relevant local OpenAI candidate. It is an Apache-2.0
open-weight, general-purpose reasoning model, not a PII/PHI NER model. Its
possible role is a carefully prompted *second-pass review*: given text that a
deterministic rule or specialized model already flagged, return a fixed JSON
classification such as `review`, `likely_sensitive`, or `not_confirmed`.

This is deliberately a weaker and more expensive primary detector than GLiNER:
generative answers can vary, spans need extra validation, and a negative answer
cannot demonstrate absence of PHI. A local-only deployment avoids transmitting
the input to a hosted API, but it does not change that reliability limitation.

LM Studio can serve compatible local LLMs over localhost, but it currently lists
GGUF and MLX model formats for loaded LLMs/embeddings. Use it for a compatible
`gpt-oss` build only after confirming the installed LM Studio version and model
format support. Continue to run GLiNER and token-classification models through
their Python runtimes.

Sources: [OpenAI `gpt-oss-20b` model page](https://developers.openai.com/api/docs/models/gpt-oss-20b),
[OpenAI's local-memory announcement](https://openai.com/index/introducing-gpt-oss/),
[OpenAI open-weight overview](https://help.openai.com/en/articles/11870455), and
[LM Studio model API/format documentation](https://lmstudio.ai/docs/developer/rest/list).

## Proposed evaluation sequence

1. Build a small **wholly synthetic** corpus that includes clean text and known
   PII/PHI-like spans representative of source documentation, log messages, and
   DICOM tag values. Keep the corpus out of image assets and ensure it passes the
   repository PHI gate.
2. Establish the deterministic baseline: existing repository checks, selected
   regular expressions/Presidio recognizers, and any approved DICOM tag rules.
3. Run NVIDIA GLiNER and OpenAI Privacy Filter with documented labels/taxonomy
   and thresholds. Record only aggregate precision/recall, per-category false
   positives/negatives, latency, peak memory, and each model revision. Compare
   the fixed Privacy Filter taxonomy with the policy-required medical categories.
4. Run `obi/deid_roberta_i2b2` as the independent clinical-text comparison. Add
   the Gretel small model only if its size/quality trade-off might change the
   decision.
5. If an LLM review has a concrete workflow value, test `gpt-oss-20b` through
   LM Studio with deterministic temperature/settings and schema validation. Treat
   its output as a reviewer cue, not as an entity detector.
6. Only after the above, decide whether custom Presidio recognizers for GLiNER
   and/or Privacy Filter are worth maintaining. Keep the feature disabled by
   default and preserve a non-model fallback.

## Acceptance criteria for a future implementation

- Isolated environment and pinned model revision; no additions to
  `requirements.txt` without a dependency and packaging review.
- Default-off command/configuration with explicit scope selection and no network
  call after models are cached.
- Synthetic automated tests covering label mapping, thresholds, overlap handling,
  safe reporting, and an unavailable-model path.
- Findings never reveal candidate PHI in UI, console, logs, CI output, or test
  assertion failures.
- A manual review/OCR path remains mandatory for image assets and a deterministic
  DICOM metadata path remains mandatory for DICOM inputs.
