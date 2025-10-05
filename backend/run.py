import uvicorn, pathlib
uvicorn.run(
    "app.main:app",
    port=8000,
    reload=True,
    reload_dirs=[str(pathlib.Path(__file__).parent / "app")],
)

