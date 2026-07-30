from fastapi import FastAPI
from endpoints.equipment_router import router as endpoints_router
from endpoints.maintenance_router import router as maintenance_router
from endpoints.issue_router import router as issue_router
from endpoints.parts_router import router as part_router

app = FastAPI()


# 3. Attach your endpoints to the main app app safely
app.include_router(endpoints_router, prefix="/api/v1")
app.include_router(maintenance_router, prefix="/api/v1")
app.include_router(issue_router, prefix="/api/v1")
app.include_router(part_router, prefix="/api/v1")   


@app.get("/")
def read_root():
    return {"Hello": "World"}