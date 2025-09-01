from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import io

from core.extract import process_url
from core.docx_builder import build_docx  # we’ll split DOCX helpers into this file

app = FastAPI(title="Content Rec Template API")

# Allow cross-origin (so a React/Figma-style frontend can call it later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Content Rec Template API is running 🚀"}

@app.post("/extract")
def extract_content(
    url: str = Form(...),
    agency: str = Form(""),
    client_name: str = Form(""),
    annotate_links: bool = Form(False),
    remove_before_h1: bool = Form(False),
    include_img_src: bool = Form(False),
):
    meta, lines = process_url(
        url,
        exclude_selectors=[],
        annotate_links=annotate_links,
        remove_before_h1=remove_before_h1,
        include_img_src=include_img_src,
    )
    meta["agency"] = agency
    meta["client_name"] = client_name
    return JSONResponse({"meta": meta, "content": lines})

@app.post("/generate-docx")
def generate_docx(
    url: str = Form(...),
    agency: str = Form(""),
    client_name: str = Form(""),
    template: UploadFile | None = None,
    annotate_links: bool = Form(False),
    remove_before_h1: bool = Form(False),
    include_img_src: bool = Form(False),
):
    meta, lines = process_url(
        url,
        exclude_selectors=[],
        annotate_links=annotate_links,
        remove_before_h1=remove_before_h1,
        include_img_src=include_img_src,
    )

    template_bytes = template.file.read() if template else Path("assets/blank_template.docx").read_bytes()
    docx_bytes = build_docx(template_bytes, meta, lines)

    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=content_template.docx"},
    )
