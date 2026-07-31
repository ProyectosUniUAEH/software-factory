from fastapi import FastAPI

app = FastAPI(title="placeholder-app")


@app.get("/health")
def health():
    return {"status": "ok", "app": "placeholder-app"}


@app.get("/")
def root():
    return {"message": "placeholder-app is running"}
