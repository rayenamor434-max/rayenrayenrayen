
import json
import asyncio
import os
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from orchestrator import Orchestrator
from config import FILES_DIR, HOST, PORT

app = FastAPI(title="OMEGA", version="4.0.0", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jarvis = Orchestrator()


# ── Schemas ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    context: Optional[dict] = None

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    priority: Optional[str] = "normal"
    project: Optional[str] = "inbox"
    due_date: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    project: Optional[str] = None
    description: Optional[str] = None

class MemoryCreate(BaseModel):
    content: str
    category: Optional[str] = "general"
    importance: Optional[int] = 2

class CodeRequest(BaseModel):
    code: str
    language: Optional[str] = "python"

class FileReadRequest(BaseModel):
    path: str

class FileWriteRequest(BaseModel):
    filename: str
    content: str
    append: Optional[bool] = False

class PlanRequest(BaseModel):
    goal: str
    session_id: Optional[str] = "default"

class ResearchRequest(BaseModel):
    query: str
    depth: Optional[str] = "standard"

class LearnRequest(BaseModel):
    topic: str
    mode: Optional[str] = "standard"
    session_id: Optional[str] = "default"

class ProjectScanRequest(BaseModel):
    folder_path: str

class BrowserRequest(BaseModel):
    url: Optional[str] = None
    query: Optional[str] = None
    engine: Optional[str] = "google"

class VoiceRequest(BaseModel):
    text: str
    lang: Optional[str] = None


# ── Root ────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>OMEGA</h1><p>index.html not found. API running at /api/docs</p>"


# ── Chat ────────────────────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(400, "Empty message")
    result = await asyncio.to_thread(
        jarvis.process, req.message.strip(), req.session_id, req.context
    )
    return result


@app.get("/stream")
async def stream_chat(
    message: str = Query(...),
    session_id: str = "default",
    context: Optional[str] = None,
):
    if not message.strip():
        raise HTTPException(400, "Empty message")

    ctx = {}
    if context:
        try:
            ctx = json.loads(context)
        except Exception:
            pass

    async def event_generator():
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

        def producer() -> None:
            try:
                for chunk in jarvis.stream(message, session_id, ctx):
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, f"\n[error: {exc}]")
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        future = loop.run_in_executor(None, producer)
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    yield "data: [DONE]\n\n"
                    break
                yield f"data: {chunk.replace(chr(10), chr(92)+'n')}\n\n"
        finally:
            await future

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── WebSocket (real-time bidirectional) ────────────────────────────────────────

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "chat")

            if msg_type == "chat":
                message = data.get("message", "").strip()
                context = data.get("context", {})
                if not message:
                    continue

                # Stream response chunks over WS
                loop = asyncio.get_running_loop()
                queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
                full_text = []

                def producer():
                    try:
                        for chunk in jarvis.stream(message, session_id, context):
                            loop.call_soon_threadsafe(queue.put_nowait, chunk)
                    except Exception as e:
                        loop.call_soon_threadsafe(queue.put_nowait, f"\n[error: {e}]")
                    finally:
                        loop.call_soon_threadsafe(queue.put_nowait, None)

                future = loop.run_in_executor(None, producer)
                while True:
                    chunk = await queue.get()
                    if chunk is None:
                        break
                    full_text.append(chunk)
                    await ws.send_json({"type": "chunk", "content": chunk})
                await future
                await ws.send_json({"type": "done", "content": "".join(full_text)})

            elif msg_type == "ping":
                await ws.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ── Voice Synthesis ────────────────────────────────────────────────────────────

@app.post("/voice/speak")
async def speak(req: VoiceRequest):
    """Stream TTS audio (MP3) for the given text. No file stored permanently."""
    from agents.voice import synthesize_stream, is_available
    if not is_available():
        raise HTTPException(503, "edge-tts not installed. Run: pip install edge-tts")

    async def audio_stream():
        async for chunk in synthesize_stream(req.text, req.lang):
            yield chunk

    return StreamingResponse(audio_stream(), media_type="audio/mpeg")


@app.get("/voice/available")
async def voice_available():
    from agents.voice import is_available, list_voices
    return {"available": is_available(), "voices": list_voices()}


# ── Browser Control (Playwright) ───────────────────────────────────────────────

@app.post("/browser/open")
async def browser_open(req: BrowserRequest):
    """Open a URL in the real browser."""
    if not req.url:
        raise HTTPException(400, "url required")
    result = await jarvis.browser.open(req.url)
    return result


@app.post("/browser/search")
async def browser_search(req: BrowserRequest):
    """Search the web using the real browser."""
    if not req.query:
        raise HTTPException(400, "query required")
    result = await jarvis.browser.search(req.query, req.engine or "google")
    return result


@app.get("/browser/content")
async def browser_content():
    """Get text content of current browser page."""
    content = await jarvis.browser.get_page_content()
    url     = await jarvis.browser.current_url()
    title   = await jarvis.browser.current_title()
    return {"url": url, "title": title, "content": content}


@app.get("/browser/status")
async def browser_status():
    return await jarvis.browser.status()


@app.post("/browser/screenshot")
async def browser_screenshot():
    path = await jarvis.browser.screenshot()
    return {"path": path}


# ── Tasks ────────────────────────────────────────────────────────────────────────

@app.get("/tasks/summary")
async def task_summary():
    summary = await asyncio.to_thread(jarvis.planner.summary)
    stats   = await asyncio.to_thread(jarvis.memory.task_summary)
    return {"text": summary, "stats": stats}


@app.get("/tasks")
async def get_tasks(status: Optional[str] = None, project: Optional[str] = None):
    tasks = await asyncio.to_thread(jarvis.memory.get_tasks, status, project)
    return {"tasks": tasks, "count": len(tasks)}


@app.post("/tasks", status_code=201)
async def create_task(task: TaskCreate):
    result = await asyncio.to_thread(
        jarvis.planner.add,
        task.title, task.description, task.priority, task.project, task.due_date
    )
    return result


@app.patch("/tasks/{task_id}")
async def update_task(task_id: int, update: TaskUpdate):
    kwargs = {k: v for k, v in update.model_dump().items() if v is not None}
    ok = await asyncio.to_thread(jarvis.memory.update_task, task_id, **kwargs)
    if not ok:
        raise HTTPException(404, f"Task {task_id} not found")
    return {"updated": task_id}


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    await asyncio.to_thread(jarvis.memory.delete_task, task_id)
    return {"deleted": task_id}


@app.post("/tasks/{task_id}/complete")
async def complete_task(task_id: int):
    msg = await asyncio.to_thread(jarvis.planner.complete, task_id)
    return {"message": msg}


@app.post("/plan")
async def create_plan(req: PlanRequest):
    result = await asyncio.to_thread(jarvis.generate_plan, req.goal)
    return result


# ── Memory ────────────────────────────────────────────────────────────────────────

@app.get("/memories/search")
async def search_memories(q: str = Query(..., min_length=2)):
    results = await asyncio.to_thread(jarvis.memory.search_memories, q)
    return {"query": q, "results": results, "count": len(results)}


@app.get("/memories")
async def get_memories():
    mems = await asyncio.to_thread(jarvis.memory.get_all_memories)
    return {"memories": mems, "count": len(mems)}


@app.post("/memories", status_code=201)
async def add_memory(mem: MemoryCreate):
    mem_id = await asyncio.to_thread(
        jarvis.memory.add_memory, mem.content, mem.category, None, mem.importance
    )
    return {"id": mem_id, "content": mem.content}


@app.delete("/memories/{memory_id}")
async def delete_memory(memory_id: int):
    await asyncio.to_thread(jarvis.memory.delete_memory, memory_id)
    return {"deleted": memory_id}


# ── Code Execution ────────────────────────────────────────────────────────────────

@app.post("/execute")
async def execute_code(req: CodeRequest):
    result = await asyncio.to_thread(jarvis.coder.execute_raw, req.code)
    return result


# ── Files ─────────────────────────────────────────────────────────────────────────

@app.get("/files")
async def list_files(path: Optional[str] = None):
    result = await asyncio.to_thread(jarvis.files.list_directory, path or FILES_DIR)
    return result


@app.post("/files/read")
async def read_file(req: FileReadRequest):
    result = await asyncio.to_thread(jarvis.files.read_file, req.path)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.post("/files/write")
async def write_file(req: FileWriteRequest):
    mode   = "a" if req.append else "w"
    result = await asyncio.to_thread(jarvis.files.write_file, req.filename, req.content, mode)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ── Research ──────────────────────────────────────────────────────────────────────

@app.get("/research")
async def web_research(q: str = Query(..., min_length=2), type: str = "general"):
    if type == "weather":
        result = await asyncio.to_thread(jarvis.research.weather, q)
        return {"type": "weather", "result": result}
    if type == "wikipedia":
        result = await asyncio.to_thread(jarvis.research.wikipedia, q)
        return {"type": "wikipedia", "result": result}
    data      = await asyncio.to_thread(jarvis.research.search, q)
    formatted = await asyncio.to_thread(jarvis.research.format_search_results, data)
    return {"type": "search", "query": q, "formatted": formatted, "raw": data}


@app.post("/research/deep")
async def deep_research(req: ResearchRequest):
    from tools.web_scraper import multi_source_research
    data      = await asyncio.to_thread(multi_source_research, req.query, 2)
    formatted = await asyncio.to_thread(jarvis.research.format_search_results, data)
    summary   = await asyncio.to_thread(
        jarvis.ai.quick,
        f"Summarize this research on '{req.query}' concisely:\n{formatted[:2000]}",
        "Summarize research findings accurately. No fabrication.",
    )
    jarvis.memory.log_event("deep_research", req.query)
    jarvis.memory.add_memory(f"Researched: {req.query}", category="research", importance=2)
    return {"query": req.query, "summary": summary, "raw": data}


# ── Learning ──────────────────────────────────────────────────────────────────────

@app.get("/learning/roadmap")
async def learning_roadmap(topic: str = Query(..., min_length=2)):
    roadmap   = await asyncio.to_thread(jarvis.learning.get_roadmap, topic)
    formatted = await asyncio.to_thread(jarvis.learning.format_roadmap, topic, roadmap) if roadmap else ""
    return {"topic": topic, "roadmap": roadmap, "formatted": formatted}


@app.post("/learning/start")
async def start_learning(req: LearnRequest):
    roadmap   = await asyncio.to_thread(jarvis.learning.get_roadmap, req.topic)
    study_ctx = await asyncio.to_thread(jarvis.learning.build_study_context, req.topic, req.mode)
    prompt    = f"I want to learn about {req.topic}. Mode: {req.mode}. Give me an introduction."
    result    = await asyncio.to_thread(
        jarvis.ai.chat, prompt, req.session_id, None, "", study_ctx, False, ""
    )
    jarvis.memory.log_event("learning", f"Started: {req.topic} ({req.mode})")
    return {"topic": req.topic, "mode": req.mode, "lesson": result["response"], "roadmap": roadmap}


@app.get("/learning/sessions")
async def learning_sessions():
    sessions = await asyncio.to_thread(jarvis.memory.get_all_learning)
    return {"sessions": sessions, "count": len(sessions)}


# ── Project ───────────────────────────────────────────────────────────────────────

@app.post("/project/scan")
async def scan_project(req: ProjectScanRequest):
    scan = await asyncio.to_thread(jarvis.files.scan_project, req.folder_path)
    if "error" in scan:
        raise HTTPException(400, scan["error"])
    summary = await asyncio.to_thread(
        jarvis.ai.quick,
        f"Describe this project in 2-3 sentences. Type: {scan['project_type']}. "
        f"Files ({scan['total_files']}): {[f['path'] for f in scan['structure'][:12]]}",
        "Describe the project accurately from the file list.",
    )
    return {**scan, "summary": summary}


# ── System ────────────────────────────────────────────────────────────────────────

@app.get("/system")
async def system_stats():
    report    = await asyncio.to_thread(jarvis.sysmon.get_full_report)
    processes = await asyncio.to_thread(jarvis.sysmon.get_top_processes, 8)
    return {"report": report, "top_processes": processes}


@app.get("/status")
async def status():
    stats = await asyncio.to_thread(jarvis.get_stats)
    return {
        **stats,
        "automation" : jarvis.auto.is_ready(),
        "browser"    : {"playwright": jarvis.browser.is_available() if hasattr(jarvis.browser, 'is_available') else False},
        "voice"      : {"available": False},  # checked async separately
        "server_time": datetime.now().isoformat(),
        "version"    : "4.0.0",
    }


@app.get("/events")
async def events(limit: int = 30, type: Optional[str] = None):
    evts = await asyncio.to_thread(jarvis.memory.get_recent_events, limit, type)
    return {"events": evts, "count": len(evts)}


@app.post("/clear")
async def clear_history(session_id: str = "default"):
    await asyncio.to_thread(jarvis.memory.clear_history, session_id)
    return {"status": "cleared", "session_id": session_id}


@app.post("/reset")
async def full_reset():
    await asyncio.to_thread(jarvis.memory.clear_all)
    return {"status": "reset", "timestamp": datetime.now().isoformat()}


# ── Auto-start ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading
    import time

    def _open_browser():
        time.sleep(1.5)
        webbrowser.open(f"http://127.0.0.1:{PORT}")

    threading.Thread(target=_open_browser, daemon=True).start()
    print(f"\nOMEGA starting — http://127.0.0.1:{PORT}\n")
    uvicorn.run(app, host=HOST, port=PORT, reload=False)