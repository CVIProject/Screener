from fastapi import FastAPI
from fastapi import UploadFile
from fastapi import File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware


from services.screening_service import process_excel

import os
import uuid

app = FastAPI(
    title="Stock Screening API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)


@app.post("/screen")

async def screen_excel(
    file: UploadFile = File(...)
):

    request_id = str(uuid.uuid4())

    input_file = (
        f"{UPLOAD_DIR}/{request_id}.xlsx"
    )

    output_file = (
        f"{OUTPUT_DIR}/{request_id}_output.xlsx"
    )

    with open(input_file, "wb") as buffer:

        buffer.write(
            await file.read()
        )

    process_excel(
        input_file,
        output_file
    )

    return FileResponse(
        path=output_file,
        filename="filtered_output.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )