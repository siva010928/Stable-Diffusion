import random
import string
from typing import Optional

from fastapi.middleware.cors import CORSMiddleware
from bark import SAMPLE_RATE, generate_audio
from IPython.display import Audio
import uvicorn
import numpy as np
from pydantic import BaseModel
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
from pydub import AudioSegment
import os
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Mount the static directory
app.mount("/audio_files", StaticFiles(directory="audio_files"), name="audio_files")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PromptRequest(BaseModel):
    prompt: str


class JobStatus(BaseModel):
    job_id: Optional[str]
    status: str
    track_your_job: str


class AudioStatus(BaseModel):
    job_id: Optional[str]
    status: str
    audio_url: Optional[str] = None


def generate_job_id():

    characters = string.ascii_letters + string.digits
    job_id = ''.join(random.choices(characters, k=30))
    return job_id


job_statuses = {}


def generate_audio_async(prompt: str, job_id: str):
    audio_array = generate_audio(prompt)
    audio_data = Audio(audio_array, rate=SAMPLE_RATE)

    audio_array = np.frombuffer(audio_data.data, dtype=np.int16)

    if audio_array.ndim > 1:
        audio_array = np.mean(audio_array, axis=1)

    audio_filename = job_id + ".wav"
    audio_filepath = os.path.join("audio_files", audio_filename)

    audio_segment = AudioSegment(audio_array.tobytes(), frame_rate=SAMPLE_RATE, sample_width=2, channels=1)

    audio_segment.export(audio_filepath, format="wav")

    job_statuses[job_id] = "completed"


@app.post("/audio", response_model=JobStatus)
async def process_prompt(request: PromptRequest, background_tasks: BackgroundTasks):
    job_id = generate_job_id()
    job_statuses[job_id] = "pending"

    background_tasks.add_task(generate_audio_async, request.prompt, job_id)
    job_status_url = f"/audio/{job_id}"

    return {"status": "pending", "job_id": job_id, "track_your_job": job_status_url}


@app.get("/audio/{job_id}", response_model=AudioStatus)
async def get_audio_status(job_id: str):
    if job_id not in job_statuses:
        return JSONResponse(status_code=404, content={"message": "Job ID not found"})

    status = job_statuses.get(job_id)
    if status == "pending":
        return {"job_id": job_id, "status": "pending", "audio_url": None}
    elif status == "completed":
        audio_filename = job_id + ".wav"
        audio_url = os.path.join("/audio_files", audio_filename)
        return {"job_id": job_id, "status": "completed", "audio_url": audio_url}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
