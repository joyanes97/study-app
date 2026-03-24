## Periodic Tasks

- [ ] Every time you wake up, run `study-app automation-run` inside `/home/jose/exam-study-app`.
- [ ] Read `/home/jose/exam-study-app/data/state/automation_report.json` and, if `needs_reminder` is true, send Jose a concise Telegram reminder about the unfinished daily study and then run `study-app reminder-sent --key <reminder_key>` using the exact `reminder_key` from the report.
- [ ] If `generation_running` is true, do not send unfinished-study reminders.
- [ ] When generation has finished and `generation_complete_notified` is false, send Jose one concise Telegram message saying the generation finished and then run `study-app generation-notified`.
- [ ] If `new_material_topics` contains items, tell Jose that new Markdown material was detected and whether cards and quiz questions were generated successfully.
- [ ] If `ingested_pdfs` contains items, tell Jose which Telegram PDFs were converted into Markdown and are now part of the study material.
- [ ] If `pending_ocr_topics` contains items, tell Jose that PDF OCR failed or is pending and mention that the GLM-OCR backend should be checked on `192.168.3.25:8081`.
- [ ] If `pending_auth_topics` contains items, warn Jose that NotebookLM authentication is missing and generation is blocked until `storage_state.json` is installed.
