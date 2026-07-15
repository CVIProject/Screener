from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
from datetime import datetime
import shutil
import os 

from services.screening_service import process_excel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

Path(UPLOAD_DIR).mkdir(exist_ok=True)
Path(OUTPUT_DIR).mkdir(exist_ok=True)


@app.post("/filter")
async def filter_excel(
        stock_file: UploadFile = File(...),
        biblical_file: UploadFile = File(...)
):

    stock_path = os.path.join(
        UPLOAD_DIR,
        stock_file.filename
    )

    biblical_path = os.path.join(
        UPLOAD_DIR,
        biblical_file.filename
    )

    with open(stock_path, "wb") as buffer:
        shutil.copyfileobj(stock_file.file, buffer)

    with open(biblical_path, "wb") as buffer:
        shutil.copyfileobj(biblical_file.file, buffer)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_file = os.path.join(
        OUTPUT_DIR,
        f"filtered_file_{timestamp}.xlsx"
    )

    process_excel(
        stock_path,
        biblical_path,
        output_file
    )

    return FileResponse(
        output_file,
        filename=f"filtered_file_{timestamp}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )