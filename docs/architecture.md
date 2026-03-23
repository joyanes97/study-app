# Architecture

## Source of truth

- Markdown files in `data/content/`
- One file per topic or subtopic
- One global `exam_date`

## Planning flow

1. Load Markdown topics and metadata.
2. Compute `days_left` from the global exam date.
3. Score each topic using:
   - topic weight
   - priority
   - weakness
   - freshness / forgetting risk
4. Build a daily plan with:
   - review queue
   - weak topics
   - new topics
   - mixed quiz block
5. Export actions for NotebookLM and Nanobot.

## Phases

- Build: far from exam, more coverage and generation.
- Consolidate: balance between new material and reviews.
- Final: heavy review and mixed quizzes, almost no new content.

## NotebookLM usage

NotebookLM should be used as a generation layer, not as the source of truth.
The app keeps local copies of generated flashcards and quizzes as JSON.

## Nanobot usage

Nanobot should orchestrate the daily cycle:
- run planning every morning
- request new generation when a topic lacks cards
- surface today's plan to the user
- trigger reminders and progress summaries
