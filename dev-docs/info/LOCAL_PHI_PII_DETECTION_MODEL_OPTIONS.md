# Local PII / PHI detection options

**Last updated:** 2026-07-14

> **Status:** research and evaluation reference only. No model or external tool
> described here is installed in the application, invoked by the repository
> hooks, or permitted to replace an existing privacy control.

## Purpose

This note records locally runnable models and scanner candidates for an
*optional* defense-in-depth PII/PHI review. The intended use is to flag possible
sensitive text, code flow, metadata, or image annotations in a
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
- Treat a vendor's local-processing or HIPAA-related statement as an evaluation
  input, not a compliance result. Before installing a proprietary binary or
  enabling a hosted integration, record the version and licence, review its
  declared data handling, and verify the no-upload/local-only configuration with
  a synthetic scan.
- Preserve the existing deterministic DICOM checks, logging protections, hash
  manifest, and visual/OCR review. These candidates are an additional signal, not
  a replacement or a HIPAA/PS3.15 conformance assertion.

## Candidate matrix

| Candidate | Type and local integration | Download / footprint | Appropriate role | Important limits |
|---|---|---:|---|---|
| [`nvidia/gliner-PII`](https://huggingface.co/nvidia/gliner-PII) | GLiNER span detector, loaded through the Python `gliner` package | 570M parameters; 1.79 GB repository download (1.78 GB checkpoint) | Primary specialized PII/PHI text-detector candidate | Text only; NVIDIA documents Linux/NVIDIA/CPU environments, not an Apple Silicon support guarantee. Use an MPS/CPU proof of concept before relying on Mac performance. |
| [`fastino/gliner2-privacy-filter-PII-multi`](https://huggingface.co/fastino/gliner2-privacy-filter-PII-multi) | GLiNER2 prompted-label span detector; use `gliner2` (or test its documented `gliner` compatibility) | GLiNER2 base: 205M parameters; 1.24 GB repository download (1.23 GB `safetensors`) | Primary multilingual PII comparison, with a large fine-grained label set | Training data is fully synthetic; the model card reports low precision on its one benchmark, so calibrate per label and do not use unreviewed output for automatic redaction. |
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

## Adjacent scanner candidates

These tools complement the text models rather than compete with them directly.
They are deliberately split by input type: source-code data flow, structured
text/data, DICOM metadata, and DICOM pixels need different checks.

| Candidate | Input and role | Local fit | Decision / main caution |
|---|---|---|---|
| [`elijahrockers/dicom-phi-scan`](https://github.com/elijahrockers/dicom-phi-scan) | DICOM header scan plus EasyOCR-based burned-in-text screening | Closest external candidate to the DICOM-specific problem | Evaluate only against temporary, wholly synthetic DICOM; it is a small, unreleased project and its conservative "all OCR text is PHI" policy needs a code/dependency and false-positive review. |
| [`phiscanhq/phi-scan`](https://github.com/phiscanhq/phi-scan) | Local source, config, and structured-data scanner; combines regex, Presidio NLP, FHIR, and HL7 layers | It is the existing `phi-scan` optional-package path | Strong rule-based baseline for source/structured text, but not a native DICOM-pixel scanner. Confirm its exact package/repository revision and safe-output behavior before a real scan. |
| [`certifieddata/pii-scan`](https://github.com/certifieddata/pii-scan) | Regex heuristic scanner for CSV/JSON datasets | Small local Node CLI; possible export/dataset check | Not relevant to DICOM pixels or application data flow. Its example output includes masked samples, which still conflicts with this repository's no-value reporting rule unless suppressed or excluded. |
| [HoundDog.ai Privacy Code Scanner](https://hounddog.ai/hipaa-compliance-code-scanning/) | Static code/data-flow scanner for PII/PHI paths into logs, files, APIs, third parties, and AI integrations | High-value source-code complement; free tier lists Python support | **Prioritize an isolated local trial**, but it is proprietary. Do not connect a repository, upload results, or make it a gate before licence, supply-chain, data-handling, and output reviews. It does not scan DICOM contents or prove HIPAA compliance. |

### HoundDog.ai: high-priority source-code candidate

HoundDog is a privacy-focused static data-flow scanner, not a PII entity model.
It traces declared sensitive data types through assignments and transformations
to sinks such as logs, files, local storage, APIs, SDKs, and AI integrations. That
is valuable for this application because it can examine whether a DICOM tag or
other sensitive value could reach diagnostic logging or an external integration;
it does not inspect a DICOM file's metadata or pixels at runtime.

HoundDog states that its free tier supports Python, JavaScript, and TypeScript,
and that scans run in the user's environment without sending code externally. It
also states that the scanner is free to use but not open source; Enterprise cloud
deployments aggregate findings and data-flow insights, while an on-premises option
exists. Treat those as vendor claims to verify in a constrained trial, not as a
substitute for the project's PHI gate, security review, or legal/compliance
assessment.

The first trial should use an isolated working copy and only the source/config
scope, avoid account/repository/CI integration, keep every output local, and
inspect the generated report using synthetic findings only. Establish whether it
offers a reliable no-upload mode, what diagnostic data it records, whether it
supports the project's Python version, and whether the licence/EULA is acceptable
before considering a non-blocking local developer command. Do not scan DICOM or
other real PHI assets with it during evaluation.

Sources: [HoundDog overview](https://docs.hounddog.ai/),
[current pricing, language, local-processing, and licence statements](https://hounddog.ai/pricing/),
and [EULA](https://hounddog.ai/end-user-license-agreement/).

### DICOM PHI Scanner: useful reference and synthetic-only spike

`dicom-phi-scan` implements a two-layer scan: pydicom-based checks of roughly 50
header tags and a pixel path that extracts an image, runs EasyOCR, and flags all
detected text as potential PHI. It triggers that pixel path when
`BurnedInAnnotation` is `YES` or absent, and emits JSON/JSONL reports with risk
levels and remediation recommendations. Its decision to flag all OCR text is
appropriately conservative for review, but it will create many false positives
for annotations that are not patient information.

It is the most directly relevant of the new external tools because it addresses
the two DICOM surfaces that a text model cannot: metadata and burned-in pixels.
It must nevertheless be treated as an untrusted third-party reference until its
code, EasyOCR model downloads, report contents, tag coverage, and behaviour when
`BurnedInAnnotation` is incorrectly `NO` have been reviewed. The public project
currently shows no releases, so pin a reviewed commit rather than adopting an
unversioned dependency. Do not run it on repository assets or real studies during
the spike; use a temporary wholly synthetic DICOM object outside the repository.

Sources: [project README and architecture](https://github.com/elijahrockers/dicom-phi-scan)
and [repository releases](https://github.com/elijahrockers/dicom-phi-scan/releases).

### PhiScan and `pii-scan`: structured-data complements

The `phiscanhq/phi-scan` project describes a local-first scanner for source code,
configuration, and structured data, with four layers: HIPAA Safe Harbor regexes,
optional Presidio/spaCy NER, FHIR R4 field scanning, and HL7 v2 parsing. It
supports baseline mode and machine-readable outputs, and states that its SQLite
audit trail retains hashes rather than raw PHI. That makes it the strongest
open-source rule-based companion for the existing source/text safeguards and a
natural Presidio connection, but it remains outside the native DICOM-pixel path.
Its reports and audit database must be inspected with synthetic inputs to ensure
they meet the repository rule of never revealing matched values.

`@certifieddata/pii-scan` is much narrower: a local Node utility using regex
heuristics to scan CSV and JSON datasets. It explicitly disclaims compliance
coverage and its default presentation includes masked example values. Consider it
only if a concrete CSV/JSON export or dataset workflow needs a lightweight extra
check; it should not be installed for the DICOM viewer's general PHI workflow.

Sources: [PhiScan package documentation](https://pypi.org/project/phi-scan/)
and [`pii-scan` README](https://github.com/certifieddata/pii-scan).

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

### Fastino GLiNER2 multilingual privacy filter

`fastino/gliner2-privacy-filter-PII-multi` is a GLiNER2 fine-tune for PII
extraction and masking across 42 entity types and seven European languages:
English, French, Spanish, German, Italian, Portuguese, and Dutch. Its supported
labels cover names, contact/address information, government and tax IDs, payment
information, digital identities, credentials, and sensitive dates. It can be
called with only the policy-relevant subset of those labels.

The model card describes a 205M-parameter GLiNER2 base and a 1.23 GB
`safetensors` checkpoint. That is comfortably small for the target Mac. It also
reports the best exact span-level F1 among four named systems on the SPY
benchmark, including NVIDIA GLiNER PII and OpenAI Privacy Filter. Treat that as
an upstream, single-benchmark claim—not as an in-domain result for this project.
The card discloses important limits: fully synthetic, non-human-annotated training
data; unmeasured performance outside those locales/scripts; and a tendency to
over-predict names (reported precision 0.35–0.37 on SPY).

This model is materially worth adding to the first comparison because it combines
multilingual support, a 42-label schema, and the smallest base architecture among
the specialized detector candidates. It is still a text-only detector. Its schema
does not explicitly include all DICOM/medical identifiers, so retain the existing
tag rules and test policy-specific aliases such as `account_number` rather than
assuming they cover a medical-record or accession number.

It is not a direct LM Studio model. Run it locally through `gliner2` in an
isolated Python environment; the model card also documents compatibility with the
existing `gliner` package. Like NVIDIA GLiNER, a future Presidio integration
should be a custom `EntityRecognizer` adapter that preserves label, span, and
confidence.

Sources: [model card and usage](https://huggingface.co/fastino/gliner2-privacy-filter-PII-multi),
[safe-tensors file listing](https://huggingface.co/fastino/gliner2-privacy-filter-PII-multi/tree/main),
and the linked [GLiNER2-PII technical report](https://arxiv.org/abs/2605.09973).

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
- GLiNER2 likewise conditions on labels supplied at inference time. Treat its
  adapter design, mapping, score preservation, and overlap policy the same as
  NVIDIA GLiNER; its 42-label taxonomy does not remove the need for a project
  policy map.
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
2. Establish separate deterministic baselines: the existing repository checks
   and `phi-scan`/Presidio for source, configuration, and structured text; and
   the existing DICOM metadata and manual/OCR review path for images. Verify that
   each trial report contains no matched values.
3. Run HoundDog only as a source/configuration data-flow trial after its local
   data handling, licence, binary provenance, and safe report output have been
   reviewed. Keep it non-blocking and disconnected from hosted, repository, and
   CI integrations.
4. Review and, if justified, run `dicom-phi-scan` only against a temporary
   wholly synthetic DICOM object. Measure tag and pixel findings separately; a
   `NO` burned-in-annotation tag must not be accepted as proof that a pixel review
   is unnecessary.
5. Run NVIDIA GLiNER, Fastino GLiNER2 Privacy Filter, and OpenAI Privacy Filter
   with documented labels/taxonomy and thresholds. Record only aggregate
   precision/recall, per-category false positives/negatives, latency, peak
   memory, and each model revision. Compare every taxonomy with the
   policy-required medical categories.
6. Run `obi/deid_roberta_i2b2` as the independent clinical-text comparison. Add
   the Gretel small model only if its size/quality trade-off might change the
   decision.
7. If an LLM review has a concrete workflow value, test `gpt-oss-20b` through
   LM Studio with deterministic temperature/settings and schema validation. Treat
   its output as a reviewer cue, not as an entity detector.
8. Only after the above, decide whether custom Presidio recognizers for GLiNER,
   GLiNER2, and/or Privacy Filter are worth maintaining. Keep the feature
   disabled by default and preserve a non-model fallback.

## Acceptance criteria for a future implementation

- Isolated environment and pinned model revision; no additions to
  `requirements.txt` without a dependency and packaging review.
- A third-party scanner has a pinned version/digest and reviewed licence; no
  account, cloud upload, repository integration, or CI gate is enabled until its
  local data handling and report contents have been verified with synthetic input.
- Default-off command/configuration with explicit scope selection and no network
  call after models are cached.
- Synthetic automated tests covering label mapping, thresholds, overlap handling,
  safe reporting, and an unavailable-model path.
- Findings never reveal candidate PHI in UI, console, logs, CI output, or test
  assertion failures.
- A manual review/OCR path remains mandatory for image assets and a deterministic
  DICOM metadata path remains mandatory for DICOM inputs.
