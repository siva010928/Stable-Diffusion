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
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
            <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
            <style>
                .container {
                    max-width: 600px;
                    margin: 40px auto;
                    text-align: center;
                }

                .form-group {
                    margin-bottom: 20px;
                }

                .help-text {
                    font-size: 12px;
                    color: #888;
                    margin-top: 5px;
                }

                .job-id,
                .status {
                    font-family: Arial, sans-serif;
                    font-size: 24px;
                    font-weight: bold;
                }
                
                .progress-container {
                    width: 100%;
                    height: 20px;
                    background-color: #f5f5f5;
                    border-radius: 5px;
                    overflow: hidden;
                }
                
                .progress-bar {
                    height: 100%;
                    background-color: #007bff;
                    transition: width 0.5s;
                }
                
                .progress-text {
                    font-family: Arial, sans-serif;
                    font-size: 16px;
                    font-weight: bold;
                    margin-top: 5px;
                    text-align: center;
                }

                .audio-player {
                    margin-top: 20px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
            </style>
            <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
            <script>
                function submitPrompt() {
                    const prompt = $("#prompt").val();
                    const textTemp = parseFloat($("#text_temp").val()) || 0.7;
                    const waveformTemp = parseFloat($("#waveform_temp").val()) || 0.7;
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
                            trackJobStatus(data.job_id);
                        },
                        error: function() {
                            alert("An error occurred while submitting the prompt.");
                        }
                    });
                }

                function trackJobStatus(jobId) {
                    const progressBar = $("#loading_percentage");
                    const progressText = $("#loading_percentage_text");
                
                    let currentPercentage = 0;
                    progressText.text(currentPercentage + "%");
                
                    const intervalId = setInterval(function() {
                        $.get("/audio/" + jobId, function(data) {
                            $("#status").text(data.status);
                
                            if (data.status === "completed") {
                                clearInterval(intervalId);
                                progressBar.animate({ width: "100%" }, 500, function() {
                                    progressText.text("100%");
                                    showAudioPlayer(data.audio_url);
                                });
                            } else {
                                currentPercentage += 2;
                                currentPercentage = Math.min(currentPercentage, 100);
                                progressBar.animate({ width: currentPercentage + "%" }, 500);
                                progressText.text(currentPercentage + "%");
                            }
                        });
                    }, 5000);
                }


                function showAudioPlayer(audioUrl) {
                    const audioPlayer = `<audio controls><source src="${audioUrl}" type="audio/wav"></audio>`;
                    $("#audio_player").html(audioPlayer);
                }
            </script>
        </head>
        <body>
            <div class="container">
                <h1 class="mb-4">FastAPI with UI</h1>
                <div class="form-group">
                    <label for="prompt">Prompt:</label>
                    <textarea id="prompt" class="form-control" rows="5"></textarea>
                </div>
                <div class="form-group">
                    <label for="text_temp">Text Temperature:</label>
                    <input type="number" id="text_temp" step="0.1" class="form-control" placeholder="0.7">
                    <p class="help-text">Generation temperature (1.0 more diverse, 0.0 more conservative)</p>
                </div>
                <div class="form-group">
                    <label for="waveform_temp">Waveform Temperature:</label>
                    <input type="number" id="waveform_temp" step="0.1" class="form-control" placeholder="0.7">
                    <p class="help-text">Generation temperature (1.0 more diverse, 0.0 more conservative)</p>
                </div>
                <div class="form-check">
                    <input type="checkbox" id="output_full" class="form-check-input">
                    <label for="output_full" class="form-check-label">Output Full:</label>
                    <p class="help-text">Return full generation as a .npz file to be used as a history prompt</p>
                </div>
                <button onclick="submitPrompt()" class="btn btn-primary mt-4">Submit</button>
                <div class="mt-5">
                    <h3 class="job-id">Job ID: <span id="job_id"></span></h3>
                    <h3 class="status">Status: <span id="status"></span></h3>
                    <div class="progress-container">
                        <div id="loading_percentage" class="progress-bar" role="progressbar"></div>
                        <div id="loading_percentage_text" class="progress-text"></div>
                    </div>
                    <div id="audio_player" class="audio-player"></div>
                </div>
            </div>
        </body>
    </html>
    """)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
