"""First thing to run on a machine with Google credentials:  python -m scripts.smoke_vertex

Verifies the Vertex AI wiring (SDK drift, model ID, region, structured output, image input)
that could not be tested in the offline build container. Requires GCP_PROJECT, GCP_LOCATION,
GEMINI_MODEL in the environment and `gcloud auth application-default login`.
"""
import io
import os

from PIL import Image, ImageDraw

from app.agents.vision_process import VisionProcessAgent
from app.config import Settings
from app.llm.vertex import VertexGeminiClient


def main() -> None:
    os.environ.setdefault("LLM_MODE", "vertex")
    s = Settings(env="development", llm_mode="vertex")
    llm = VertexGeminiClient(s.gcp_project, s.gcp_location, s.gemini_model)
    img = Image.new("RGB", (640, 360), "white")
    d = ImageDraw.Draw(img)
    d.rectangle((80, 120, 300, 260), outline="black", width=4)
    d.text((90, 90), "Inspection table with checklist", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    process = VisionProcessAgent(llm).analyze([buf.getvalue()], "Operators inspect parts by hand.")
    print(process.model_dump_json(indent=2))
    print("OK: structured output and image input work")


if __name__ == "__main__":
    main()
