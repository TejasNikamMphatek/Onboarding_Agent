from fastapi import FastAPI, BackgroundTasks, Request
import uvicorn
from agent import crew # Aapka existing crew object

app = FastAPI()
answers = {} # Global dict to store HR responses

@app.post("/start")
async def start_onboarding(background_tasks: BackgroundTasks):
    background_tasks.add_task(crew.kickoff)
    return {"status": "Agent Started"}

@app.post("/submit-answer")
async def receive_answer(request: Request):
    data = await request.json()
    answers[data['cache_key']] = data['answer']
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5002)