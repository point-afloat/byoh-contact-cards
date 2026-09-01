from fastapi import FastAPI

app = FastAPI(title="Contact Card API")


@app.get("/")
def read_root():
    return {"status": "ok", "message": "Contact card API is running"}
