from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from app.core.config import settings
from app.services.screener.screening_service import process_excel
router=APIRouter(prefix='/api/screener',tags=['Stock Screener'])
@router.post('/filter')
async def filter_stocks(stock_file:UploadFile=File(...),biblical_file:UploadFile=File(...)):
    for f,n in ((stock_file,'stock_file'),(biblical_file,'biblical_file')):
        if not f.filename or Path(f.filename).suffix.lower() not in {'.xlsx','.xlsm'}:
            raise HTTPException(400,f'{n} must be .xlsx or .xlsm')
    try:
        with TemporaryDirectory() as td:
            p=Path(td); s=p/'stock.xlsx'; b=p/'biblical.xlsx'; o=p/'result.xlsx'
            s.write_bytes(await stock_file.read()); b.write_bytes(await biblical_file.read())
            process_excel(str(s),str(b),str(o))
            name=f"filtered_file_{datetime.now():%Y%m%d_%H%M%S}.xlsx"; dest=settings.OUTPUT_DIR/name; dest.write_bytes(o.read_bytes())
        return FileResponse(dest,filename=name,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except HTTPException: raise
    except Exception as e: raise HTTPException(500,f'Screening failed: {e}') from e
