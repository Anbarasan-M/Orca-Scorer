from fastapi import FastAPI

app = FastAPI(title="Orca Scorer API")


@app.get("/")
def root():
    return {"message": "Welcome to Orca Scorer"}