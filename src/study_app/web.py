from __future__ import annotations

from datetime import date
from pathlib import Path

import markdown as md
from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from study_app.service import (
    build_dashboard_data,
    find_topic,
    get_root,
    mark_session_item_complete,
    next_card,
    next_question,
    progress_summary,
    update_exam_date,
)
from study_app.study_store import record_card_review, record_question_attempt

ROOT = get_root()
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(title="Exam Study App")
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "static")),
    name="static",
)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, day: str | None = Query(default=None)):
    plan_date = date.fromisoformat(day) if day else date.today()
    data = build_dashboard_data(ROOT, plan_date)
    return TEMPLATES.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "page_title": "Plan de hoy",
            "data": data,
        },
    )


@app.post("/settings/exam-date")
def set_exam_date(exam_date: str = Form(...)):
    new_date = date.fromisoformat(exam_date)
    update_exam_date(ROOT, new_date)
    return RedirectResponse(url="/", status_code=303)


@app.get("/topics", response_class=HTMLResponse)
def topics(request: Request):
    data = build_dashboard_data(ROOT, date.today())
    return TEMPLATES.TemplateResponse(
        request,
        "topics.html",
        {
            "request": request,
            "page_title": "Temas",
            "data": data,
        },
    )


@app.get("/topics/{topic_id}", response_class=HTMLResponse)
def topic_detail(topic_id: str, request: Request):
    payload = find_topic(topic_id, ROOT)
    if not payload:
        raise HTTPException(status_code=404, detail="Topic not found")
    topic = payload["topic"]
    progress = payload["progress"]
    html = md.markdown(topic.body, extensions=["extra", "sane_lists"])
    return TEMPLATES.TemplateResponse(
        request,
        "topic_detail.html",
        {
            "request": request,
            "page_title": topic.title,
            "topic": topic,
            "progress": progress,
            "rendered_markdown": html,
            "cards": payload["cards"],
            "questions": payload["questions"],
        },
    )


@app.get("/study/session", response_class=HTMLResponse)
def study_session(request: Request):
    data = build_dashboard_data(ROOT, date.today())
    return TEMPLATES.TemplateResponse(
        request,
        "session.html",
        {
            "request": request,
            "page_title": "Sesión diaria",
            "data": data,
        },
    )


@app.get("/study/cards", response_class=HTMLResponse)
def study_cards(request: Request, topic: str | None = Query(default=None)):
    card = next_card(ROOT, topic)
    data = build_dashboard_data(ROOT, date.today())
    return TEMPLATES.TemplateResponse(
        request,
        "cards.html",
        {
            "request": request,
            "page_title": "Tarjetas",
            "card": card,
            "data": data,
        },
    )


@app.post("/study/cards/{card_id}/review")
def review_card(card_id: str, rating: str = Form(...)):
    record_card_review(ROOT / "data" / "state", card_id, rating)
    mark_session_item_complete(ROOT, "card", card_id)
    return RedirectResponse(url="/study/cards", status_code=303)


@app.get("/study/quiz", response_class=HTMLResponse)
def study_quiz(
    request: Request,
    topic: str | None = Query(default=None),
    answered: str | None = None,
):
    question = next_question(ROOT, topic)
    feedback = None
    if answered:
        payload = build_dashboard_data(ROOT, date.today())
        for item in payload["today_questions"]:
            if item["id"] == answered:
                feedback = item
                break
    return TEMPLATES.TemplateResponse(
        request,
        "quiz.html",
        {
            "request": request,
            "page_title": "Test",
            "question": question,
            "feedback": feedback,
            "data": build_dashboard_data(ROOT, date.today()),
        },
    )


@app.post("/study/quiz/{question_id}/answer", response_class=HTMLResponse)
def answer_quiz(question_id: str, request: Request, option_id: str = Form(...)):
    data = build_dashboard_data(ROOT, date.today())
    selected_question = None
    for question in data["today_questions"]:
        if question["id"] == question_id:
            selected_question = question
            break
    if not selected_question:
        raise HTTPException(status_code=404, detail="Question not found")

    correct_option = next(
        (option for option in selected_question["options"] if option["is_correct"]),
        None,
    )
    is_correct = bool(correct_option and correct_option["id"] == option_id)
    record_question_attempt(ROOT / "data" / "state", question_id, option_id, is_correct)
    mark_session_item_complete(ROOT, "question", question_id)
    return TEMPLATES.TemplateResponse(
        request,
        "quiz.html",
        {
            "request": request,
            "page_title": "Test",
            "question": next_question(ROOT, None),
            "feedback": {
                "question": selected_question,
                "selected_option": option_id,
                "correct_option": correct_option,
                "is_correct": is_correct,
            },
            "data": build_dashboard_data(ROOT, date.today()),
        },
    )


@app.get("/progress", response_class=HTMLResponse)
def progress(request: Request):
    return TEMPLATES.TemplateResponse(
        request,
        "progress.html",
        {
            "request": request,
            "page_title": "Progreso",
            "data": progress_summary(ROOT),
        },
    )


@app.get("/api/plan")
def api_plan(day: str | None = Query(default=None)):
    plan_date = date.fromisoformat(day) if day else date.today()
    return build_dashboard_data(ROOT, plan_date)


@app.get("/api/topics")
def api_topics():
    data = build_dashboard_data(ROOT, date.today())
    return {"topics": data["topics"], "topic_count": data["topic_count"]}


@app.get("/api/automation")
def api_automation():
    return progress_summary(ROOT)["automation_report"]
