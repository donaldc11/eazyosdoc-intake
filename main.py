"""Minimal HTTP API around the document intake pipeline, for a public demo
deployment (Cloud Run). Stateless: no ledger, no persisted output — each
request builds one record for the uploaded file and returns it.

Run locally:
    uvicorn main:app --reload --port 8080
"""

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from intake import extract, pipeline

app = FastAPI(title="EazyOS Document Intake")


@app.get("/")
def root():
    return {
        "service": "eazyos-doc-intake",
        "status": "ok",
        "usage": "POST a file to /process (multipart form field 'file'); optional ?engine=regex|gemini (default regex)",
    }


@app.post("/process")
async def process(file: UploadFile = File(...), engine: str = Query("regex")):
    if engine not in ("regex", "gemini"):
        raise HTTPException(400, "engine must be 'regex' or 'gemini'")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in extract.SUPPORTED_EXTENSIONS:
        raise HTTPException(400, f"unsupported file type: {suffix or '(none)'}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / (file.filename or f"upload{suffix}")
        tmp_path.write_bytes(await file.read())

        doc_id = pipeline.hash_file(tmp_path)
        try:
            if engine == "gemini":
                record, _ = pipeline.build_record_with_gemini(tmp_path, doc_id)
            else:
                record, _ = pipeline.build_record(tmp_path, doc_id)
        except RuntimeError as exc:
            # e.g. GEMINI_API_KEY not configured for this deployment
            raise HTTPException(503, str(exc))

    # Nothing is persisted for a stateless request — these two paths only
    # make sense for the local batch CLI, so null them out rather than
    # leaking an ephemeral container path.
    record["source_path"] = file.filename
    record["raw_text_path"] = None
    return record
