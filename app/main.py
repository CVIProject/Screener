from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.screener import router as screener_router
from app.api.routes.regime import router as regime_router
from app.core.config import settings
app=FastAPI(title=settings.APP_TITLE,version=settings.APP_VERSION)
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
app.include_router(screener_router); app.include_router(regime_router)
@app.get('/')
def root(): return {'service':settings.APP_TITLE,'status':'running','docs':'/docs'}
@app.get('/health')
def health(): return {'status':'healthy'}
