import random
import string
from typing import Optional

from fastapi.middleware.cors import CORSMiddleware
from bark import SAMPLE_RATE, generate_audio
from IPython.display import Audio
import uvicorn
import numpy as np
from pydantic import BaseModel
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
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
    text_temp: float = 0.7
    waveform_temp: float = 0.7
    output_full: bool = False


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


@app.get("/")
async def homepage(request: Request):
    return HTMLResponse("""
    <html>
        <head>
            <title>FastAPI with UI</title>
            <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
            <script>
                function submitPrompt() {
                    const prompt = $("#prompt").val();
                    const textTemp = parseFloat($("#text_temp").val());
                    const waveformTemp = parseFloat($("#waveform_temp").val());
                    const outputFull = $("#output_full").is(":checked");

                    const data = {
                        prompt: prompt,
                        text_temp: textTemp,
                        waveform_temp: waveformTemp,
                        output_full: outputFull
                    };

                    $.ajax({
                        type: "POST",
                        url: "/audio",
                        contentType: "application/json",
                        data: JSON.stringify(data),
                        success: function(data) {
                            $("#job_id").text(data.job_id);
                            $("#status").text(data.status);
                            $("#audio_url").text(data.audio_url);
                            trackJobStatus(data.job_id);
                        },
                        error: function() {
                            alert("An error occurred while submitting the prompt.");
                        }
                    });
                }

                function trackJobStatus(jobId) {
                    const intervalId = setInterval(function() {
                        $.get("/audio/" + jobId, function(data) {
                            $("#status").text(data.status);
                            $("#loading_percentage").text(data.loading_percentage);

                            if (data.status === "completed") {
                                clearInterval(intervalId);
                                $("#audio_url").html(`<audio controls><source src="${data.audio_url}" type="audio/wav"></audio>`);
                            }
                        });
                    }, 2000);
                }
            </script>
        </head>
        <body>
            <h1>FastAPI with UI</h1>
            <div>
                <label for="prompt">Prompt:</label>
                <textarea id="prompt" rows="5" cols="50"></textarea>
            </div>
            <div>
                <label for="text_temp">Text Temperature:</label>
                <input type="number" id="text_temp" step="0.1" value="0.7">
            </div>
            <div>
                <label for="waveform_temp">Waveform Temperature:</label>
                <input type="number" id="waveform_temp" step="0.1" value="0.7">
            </div>
            <div>
                <label for="output_full">Output Full:</label>
                <input type="checkbox" id="output_full">
            </div>
            <div>
                <button onclick="submitPrompt()">Submit</button>
            </div>
            <div>
                <h3>Job ID: <span id="job_id"></span></h3>
                <h3>Status: <span id="status"></span></h3>
                <h3>Audio: <span id="audio_url"></span></h3>
            </div>
        </body>
    </html>
    """)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
