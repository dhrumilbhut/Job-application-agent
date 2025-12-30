from fastapi import FastAPI

from .routes.resume import router as resume_router
from .routes.apply import router as apply_router

app = FastAPI(title="Job Apply Agent")

# Phase 1 & 2: Resume upload + automatic parsing
app.include_router(resume_router)

# Phase 3, 4, 5: JD parsing, email generation, sending
app.include_router(apply_router)
