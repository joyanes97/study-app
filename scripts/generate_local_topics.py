from pathlib import Path
import traceback

from study_app.automation import mark_generation_running, set_reminder_suppression
from study_app.local_generator import generate_topic_artifacts
from study_app.markdown_loader import load_topics
from study_app.settings import load_settings

root = Path("/home/jose/exam-study-app")
settings = load_settings(root)
topics = load_topics(
    root / "data" / "content", settings.default_priority, settings.default_topic_weight
)
generated_dir = root / "data" / "generated"
generated_dir.mkdir(parents=True, exist_ok=True)

completed = 0
set_reminder_suppression(root, True)
mark_generation_running(root, True, total_topics=len(topics), completed_topics=0)

try:
    for index, topic in enumerate(topics, start=1):
        cards_path = generated_dir / f"{topic.id}-cards.json"
        quiz_path = generated_dir / f"{topic.id}-quiz.json"
        if cards_path.exists() and quiz_path.exists():
            completed += 1
            mark_generation_running(
                root, True, total_topics=len(topics), completed_topics=completed
            )
            print(f"skip {completed}/{len(topics)} {topic.title}", flush=True)
            continue
        try:
            generate_topic_artifacts(root, topic)
            completed += 1
            mark_generation_running(
                root, True, total_topics=len(topics), completed_topics=completed
            )
            print(f"generated {completed}/{len(topics)} {topic.title}", flush=True)
        except Exception as exc:
            print(f"error {topic.title}: {exc}", flush=True)
            traceback.print_exc()
finally:
    mark_generation_running(
        root, False, total_topics=len(topics), completed_topics=completed
    )
    set_reminder_suppression(root, False)
