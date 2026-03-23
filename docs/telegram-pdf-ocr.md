# Telegram PDF -> Markdown feasibility

## Current state

- `nanobot` already downloads Telegram documents to the instance media directory.
- The Telegram channel forwards downloaded media paths into the agent loop as message media.
- The active Nanobot instance stores runtime data next to `/home/jose/.nanobot-study/config.json`, so incoming Telegram PDFs will land under `/home/jose/.nanobot-study/media/telegram/`.
- The current local LLM host at `192.168.3.25` runs `llama-server` with `qwen2.5-3b-instruct-q4_k_m.gguf` on port `8080`.

## Viability assessment

Implementing the workflow is viable in general, but **not with the current `local-llm` OCR stack as-is**.

### What already works

1. A Telegram user can send a `.pdf` file to the bot.
2. `nanobot` downloads the file locally.
3. The bot can detect that the message contains a PDF and pass the local file path to a tool or script.
4. The study app can consume generated `.md` files once they are placed in `data/content/`.

### What does not exist yet

1. No OCR-capable model is running on `192.168.3.25`.
2. The current model advertises only `completion` capability and is text-only.
3. There is no PDF parsing or OCR toolchain installed on either server (`pdftotext`, `tesseract`, `ocrmypdf`, `pymupdf`, etc.).
4. There is no Nanobot command yet that converts an incoming PDF into study Markdown.

## Why GLM-OCR is not currently available

The local host is serving:

```text
/home/local-llm/llama.cpp/build/bin/llama-server.real \
  --model /home/local-llm/models/qwen2.5-3b-instruct-q4_k_m.gguf \
  --host 0.0.0.0 --port 8080
```

That model is not multimodal and cannot perform OCR on PDF page images.

So the answer is:

- **Telegram PDF ingestion:** yes, viable now.
- **Direct GLM-OCR via the current local LLM:** no, not viable now.

## Recommended architecture

### Option A — Best practical route

Use a dedicated PDF ingestion worker with two stages:

1. **Text extraction fallback**
   - Use `pdftotext` or `pymupdf` for PDFs that already contain selectable text.
2. **OCR fallback**
   - Use an OCR-capable engine for scanned PDFs:
     - `tesseract`
     - `ocrmypdf`
     - a multimodal OCR model hosted separately

Then normalize the output to Markdown and drop it into:

```text
/home/jose/exam-study-app/data/content/inbox/
```

After that, the existing automation can generate cards and quiz content.

### Option B — True GLM-OCR style pipeline

Deploy a second OCR-capable service on `192.168.3.25` or another host, for example:

- a multimodal model with image/PDF page understanding
- an OCR-specific HTTP service

Then the flow becomes:

```text
Telegram PDF -> nanobot media download -> OCR service -> cleaned Markdown -> study app inbox -> NotebookLM generation
```

## Security and stability notes

- Restrict Telegram access with `allowFrom`, which is already configured.
- Do not let Nanobot execute arbitrary OCR commands from user text.
- Route PDF ingestion through one fixed script with a controlled output directory.
- Keep the OCR worker isolated from the main study app web service.
- Enforce size/page limits on incoming PDFs before OCR.

## Recommended implementation order

1. Add a dedicated inbox directory for PDF-derived Markdown.
2. Add a controlled import script or CLI command.
3. Install `pdftotext` and `tesseract` first as a baseline.
4. Only after that, decide whether a true GLM-OCR service is worth adding.
5. Wire Nanobot reminders/notifications around ingestion success or failure.

## Conclusion

This feature is feasible end-to-end, but the blocker is the OCR backend, not Telegram or Nanobot.

With the current infrastructure, the best next step is **not** GLM-OCR directly. It is:

1. build a deterministic PDF ingestion path,
2. add classic OCR/text extraction,
3. optionally replace the OCR backend later with a multimodal model.
