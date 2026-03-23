from __future__ import annotations

from datetime import date
from pathlib import Path

import markdown as md
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from study_app.service import build_dashboard_data, find_topic, get_root

ROOT = get_root()
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / 'templates'))

app = FastAPI(title='Exam Study App')
app.mount('/static', StaticFiles(directory=str(Path(__file__).parent / 'static')), name='static')


@app.get('/', response_class=HTMLResponse)
def dashboard(request: Request, day: str | None = Query(default=None)):
    plan_date = date.fromisoformat(day) if day else date.today()
    data = build_dashboard_data(ROOT, plan_date)
    return TEMPLATES.TemplateResponse(
        request,
        'dashboard.html',
        {
            'request': request,
            'page_title': 'Plan de hoy',
            'data': data,
        },
    )


@app.get('/topics', response_class=HTMLResponse)
def topics(request: Request):
    data = build_dashboard_data(ROOT, date.today())
    return TEMPLATES.TemplateResponse(
        request,
        'topics.html',
        {
            'request': request,
            'page_title': 'Temas',
            'data': data,
        },
    )


@app.get('/topics/{topic_id}', response_class=HTMLResponse)
def topic_detail(topic_id: str, request: Request):
    payload = find_topic(topic_id, ROOT)
    if not payload:
        raise HTTPException(status_code=404, detail='Topic not found')
    topic = payload['topic']
    progress = payload['progress']
    html = md.markdown(topic.body, extensions=['extra', 'sane_lists'])
    return TEMPLATES.TemplateResponse(
        request,
        'topic_detail.html',
        {
            'request': request,
            'page_title': topic.title,
            'topic': topic,
            'progress': progress,
            'rendered_markdown': html,
        },
    )


@app.get('/api/plan')
def api_plan(day: str | None = Query(default=None)):
    plan_date = date.fromisoformat(day) if day else date.today()
    return build_dashboard_data(ROOT, plan_date)


@app.get('/api/topics')
def api_topics():
    data = build_dashboard_data(ROOT, date.today())
    return {'topics': data['topics'], 'topic_count': data['topic_count']}
