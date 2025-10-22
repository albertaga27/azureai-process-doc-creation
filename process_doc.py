# process_capturer_bpmn.py
import os
import json
import time
import asyncio
import argparse
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Deque
from collections import deque

import azure.cognitiveservices.speech as speechsdk
from openai import AzureOpenAI

# Import utility functions
from process_doc_utils import (
    generate_bpmn_xml, 
    render_diagrams_png, 
    render_markdown_document, 
    render_docx_from_markdownish,
    ENABLE_BPMN_GENERATION,
    ENABLE_PNG_GENERATION,
    Document  # Import Document from utils
)

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# =========================================================
# Configuration
# =========================================================
SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "<YOUR_SPEECH_KEY>")
SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "<YOUR_REGION>")
OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY", "<YOUR_OPENAI_KEY>")
OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "<YOUR_OPENAI_ENDPOINT>")
OPENAI_MODEL = os.getenv("GPT_MODEL") or os.getenv("AZURE_OPENAI_MODEL", "gpt-4o")

RECO_LANG = os.getenv("RECO_LANG", "en-US")

# Interview/Q&A mode
ENABLE_INTERVIEW_MODE = os.getenv("ENABLE_INTERVIEW_MODE", "true").lower() == "true"
ROLE_CLASSIFIER_MODE = os.getenv("ROLE_CLASSIFIER_MODE", "heuristic")  # heuristic|llm

# Chunking
CHUNK_TOKEN_TARGET = 800
CHUNK_TOKEN_MAX = 1100
CHUNK_OVERLAP = 120
IDLE_FLUSH_SECONDS = 20

# Final outputs
TIMESTAMP = time.strftime("%Y%m%d_%H%M%S")
OUTPUT_MD = f"process_document_{TIMESTAMP}.md"
OUTPUT_DOCX = f"process_document_{TIMESTAMP}.docx"
OUTPUT_BPMN = f"process_{TIMESTAMP}.bpmn"
OUTPUT_DIAGRAM_PNG = f"process_{TIMESTAMP}.png"

# =========================================================
# Azure OpenAI Client
# =========================================================
client = AzureOpenAI(
    api_key=OPENAI_KEY,
    api_version="2024-02-15-preview",
    azure_endpoint=OPENAI_ENDPOINT
)

# =========================================================
# Utilities
# =========================================================
def approx_token_count(text: str) -> int:
    words = text.strip().split()
    return int(len(words) * 0.75)

def now_ts() -> float:
    return time.time()

def slug(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in s)[:40]

# =========================================================
# Global Process Memory Schema
# =========================================================
def empty_process_memory() -> Dict[str, Any]:
    return {
        "title": None,
        "overview": "",
        "actors": [],
        "inputs": [],
        "outputs": [],
        "preconditions": [],
        "postconditions": [],
        "main_flow": [],
        "alternate_paths": [],
        "exceptions": [],
        "business_rules": [],
        "tools_systems": [],
        "metrics_slas": [],
        "risks_controls": [],
        "glossary": [],
        "open_questions": [],
        "assumptions": []
    }

# =========================================================
# Prompts
# =========================================================
CHUNK_EXTRACT_SYSTEM = """\
You are a senior process analyst. Extract structured process knowledge from the user's transcript segment following the organizational process definition template.
Return STRICT JSON following this schema (no extra keys, no commentary):

{
  "process_name": null or string,
  "description": string,
  "owner": null or string,
  "start_event": null or string,
  "end_event": null or string,
  "actors": [{"name": string, "role": string, "responsibilities": string}],
  "tools_used": [{"name": string, "type": string, "specific_tasks": [string]}],
  "data_points": [{"name": string, "operation": string, "description": string}],
  "data_classification": null or string,
  "duration": null or string,
  "variations": [string],
  "harmonized": null or string,
  "automated": null or string,
  "ai_enabled": null or string,
  "modelled": null or string,
  "model_priority": null or string,
  "main_flow": [
    {
      "id": string,
      "actor": string,
      "action": string,
      "tools": [string],
      "data_points": [string],
      "duration": null or string,
      "notes": string
    }
  ],
  "alternate_paths": [{"name": string, "condition": string, "steps": [string]}],
  "exceptions": [{"name": string, "condition": string, "steps": [string]}],
  "risks": [{"name": string, "impact": string, "likelihood": string, "description": string}],
  "control_points": [{"name": string, "description": string, "frequency": string}],
  "control_findings": [string],
  "recommendations": [string],
  "guidelines": [string],
  "constraints": [{"type": string, "description": string, "source": string}],
  "legacy_constraints": [{"type": string, "description": string, "source": string, "status": string}],
  "pain_points": [string],
  "glossary": [{"term": string, "definition": string}],
  "open_questions": [string],
  "assumptions": [string]
}
If fields aren't present in the segment, keep them as empty list, empty string, or null as per schema.

Field Guidance:
- harmonized: "yes", "no - not applicable", "no - should be"
- automated: "yes", "partially and sufficient", "partially and insufficient", "no - not applicable", "no - should be"
- ai_enabled: "yes", "partially and sufficient", "partially and insufficient", "no - not applicable", "no - should be"
- modelled: "yes - maintained", "yes - not maintained", "no - needed", "no - not needed"
- model_priority: "1" (most urgent), "2", "3" (least urgent)
- data_classification: highest classification among all data points
- data_points operation: "create", "read", "update", "delete"

Critical:
- The provided 'Recent interviewer questions' are context ONLY. Do NOT extract them as steps.
- Extract solely from the subject matter expert's ANSWERS segment.
"""

CHUNK_EXTRACT_USER_TEMPLATE = """\
Recent interviewer questions (context, not content to extract):
- {recent_questions}

Subject matter expert ANSWERS segment to extract from:
---
{segment}
---
Guidance for extraction following process definition template:
- Process Name: Extract concise name following organizational naming conventions
- Description: Look for succinct descriptions that non-expert staff can understand
- Owner: Identify the process owner (name/position) accountable for execution
- Start/End Events: Identify triggers and outcomes of the process
- Actors: Extract key units/roles and their specific responsibilities
- Tools Used: Identify applications, dashboards, AI models, BDC, EUC, SharePoint with specific tasks
- Data Points: Extract data created/read/updated/deleted (CRUD operations)
- Duration: Look for timing information from start to end
- Variations: Note any location-based or other variations
- Harmonization/Automation/AI Status: Extract current state and recommendations
- Risks & Controls: Identify key risks, control points, findings, and recommendations
- Constraints: Separate current constraints from legacy constraints
- Pain Points: Extract challenges and things that don't work well
- Keep step IDs stable and descriptive (e.g., "S1", "S2.1")
- Use crisp action verbs and clear conditions
"""

MERGE_SYSTEM = """\
You merge two JSON process models into a single, coherent model. Deduplicate, reconcile conflicts, and preserve detail.
Rules:
- Prefer explicit facts over vague statements.
- Normalize actor names (e.g., "CSR" vs "Customer Support Rep").
- Merge business rules, metrics, glossary without duplicates.
- Aggregate open questions and assumptions.
Return STRICT JSON with the same schema as input.
"""

FINAL_DOC_SYSTEM = """\
You are a process documentation writer. Using the provided consolidated JSON process model, write a polished document following the organizational process definition template:

## MANDATORY ATTRIBUTES
1) Process Name
2) Description
3) Owner
4) Start Event
5) End Event
6) Actors (key units or roles with responsibilities)
7) Tools Used (applications, dashboards, AI models, etc. with specific tasks)
8) Data Points (data created, read, updated, deleted with classifications)
9) Duration
10) Main Flow (detailed process steps)

## PROCESS CHARACTERISTICS
11) Variations
12) Harmonized Status
13) Automation Level
14) AI Enablement
15) Modelling Status
16) Model Priority

## GOVERNANCE & CONTROL
17) Risks
18) Control Points
19) Control Findings
20) Recommendations
21) Guidelines
22) Constraints
23) Legacy Constraints
24) Pain Points

## SUPPORTING INFORMATION
25) Alternate Paths
26) Exceptions & Error Handling
27) Glossary

Structure the document with clear sections and professional formatting. Include specific details where available.
At the end, include:
- A Mermaid flowchart (main flow only)
- A note that a BPMN 2.0 XML file accompanies this document
Output as Markdown ONLY.
"""

CLASSIFY_SYSTEM = """\
Classify the following utterance as either a QUESTION (interviewer asking about the process)
or an ANSWER (subject matter expert describing the process).
Return JSON: {"role": "QUESTION" or "ANSWER"}.
Only use the text content; avoid guessing from context.
"""

# =========================================================
# LLM helpers
# =========================================================
async def llm_json_completion(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    content = resp.choices[0].message.content or "{}"
    text = content.strip()
    if text.startswith("```"):
        text = "\n".join([line for line in text.splitlines() if not line.strip().startswith("```")])
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except Exception:
                pass
    return {}

async def llm_markdown_completion(system_prompt: str, user_prompt: str) -> str:
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return resp.choices[0].message.content or ""

# =========================================================
# Q/A classification
# =========================================================
def heuristic_role_classify(text: str) -> str:
    t = text.strip().lower()
    if not t:
        return "ANSWER"
    if t.endswith("?"):
        return "QUESTION"
    q_starts = ("how ", "what ", "when ", "where ", "why ", "who ", "which ", "can ", "could ", "would ", "do ", "does ", "did ", "please explain", "walk me through")
    if t.startswith(q_starts):
        return "QUESTION"
    if t.startswith(("describe ", "outline ", "explain ", "detail ", "tell me ")):
        return "QUESTION"
    return "ANSWER"

async def classify_role(text: str) -> str:
    if ROLE_CLASSIFIER_MODE == "heuristic":
        return heuristic_role_classify(text)
    res = await llm_json_completion(CLASSIFY_SYSTEM, text)
    role = (res.get("role") or "ANSWER").upper()
    return "QUESTION" if role == "QUESTION" else "ANSWER"

# =========================================================
# Chunker (answers only)
# =========================================================
@dataclass
class ChunkBuffer:
    overlap_tokens: int = CHUNK_OVERLAP
    token_target: int = CHUNK_TOKEN_TARGET
    token_max: int = CHUNK_TOKEN_MAX
    last_activity_ts: float = field(default_factory=now_ts)
    buffer: List[str] = field(default_factory=list)

    def add(self, text: str) -> Optional[str]:
        self.buffer.append(text.strip())
        self.last_activity_ts = now_ts()
        tokens = approx_token_count(" ".join(self.buffer))
        if tokens >= self.token_target:
            return self.flush_chunk()
        if tokens >= self.token_max:
            return self.force_flush_chunk()
        return None

    def flush_if_idle(self, idle_seconds: int) -> Optional[str]:
        if now_ts() - self.last_activity_ts > idle_seconds and self.buffer:
            return self.flush_chunk()
        return None

    def flush_chunk(self) -> Optional[str]:
        if not self.buffer:
            return None
        full_text = " ".join(self.buffer).strip()
        words = full_text.split()
        if len(words) <= self.overlap_tokens:
            chunk_text = full_text
            self.buffer = []
        else:
            boundary = max(0, len(words) - self.overlap_tokens)
            chunk_text = " ".join(words[:boundary]).strip()
            overlap_text = " ".join(words[boundary:]).strip()
            self.buffer = [overlap_text] if overlap_text else []
        return chunk_text

    def force_flush_chunk(self) -> Optional[str]:
        if not self.buffer:
            return None
        full_text = " ".join(self.buffer).strip()
        self.buffer = []
        return full_text

# =========================================================
# Merge models
# =========================================================
async def merge_models(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    user_prompt = f"Model A:\n{json.dumps(a, ensure_ascii=False, indent=2)}\n\nModel B:\n{json.dumps(b, ensure_ascii=False, indent=2)}"
    merged = await llm_json_completion(MERGE_SYSTEM, user_prompt)
    base = empty_process_memory()
    base.update({k: merged.get(k, v) for k, v in base.items()})
    return base

# =========================================================
# Orchestrator
# =========================================================
class ProcessOrchestrator:
    def __init__(self):
        self.memory = empty_process_memory()
        self.answer_chunker = ChunkBuffer()
        self.lock = asyncio.Lock()
        self.recent_questions: Deque[str] = deque(maxlen=6)

    async def process_utterance(self, text: str, role: str):
        """Process a single utterance based on role (QUESTION/ANSWER)"""
        if role == "QUESTION":
            self.recent_questions.append(text.strip())
            print(f"[Q] {text}")
        elif role == "ANSWER":
            print(f"[A] {text}")
            chunk = self.answer_chunker.add(text)
            if chunk:
                await self.process_chunk(chunk)

    async def idle_check(self):
        chunk = self.answer_chunker.flush_if_idle(IDLE_FLUSH_SECONDS)
        if chunk:
            await self.process_chunk(chunk)

    async def force_flush(self):
        chunk = self.answer_chunker.force_flush_chunk()
        if chunk:
            await self.process_chunk(chunk)

    async def process_chunk(self, segment: str):
        recent_q_text = "; ".join(list(self.recent_questions)[-3:]) if self.recent_questions else "No recent questions"
        user_prompt = CHUNK_EXTRACT_USER_TEMPLATE.format(
            recent_questions=recent_q_text,
            segment=segment
        )
        
        print(f"\n[Processing chunk] {len(segment)} chars...")
        extracted = await llm_json_completion(CHUNK_EXTRACT_SYSTEM, user_prompt)
        
        async with self.lock:
            self.memory = await merge_models(self.memory, extracted)
        print("\\n[Chunk processed] Memory updated.\\n")

    async def finalize_documents(self) -> Tuple[str, Optional[str], Optional[str], str]:
        # Compose final Markdown content first
        md = await llm_markdown_completion(
            FINAL_DOC_SYSTEM,
            json.dumps(self.memory, ensure_ascii=False, indent=2)
        )

        # Render basic outputs (MD and DOCX)
        render_markdown_document(md, OUTPUT_MD)
        render_docx_from_markdownish(md, OUTPUT_DOCX)
        print(f"[MD]   Saved {OUTPUT_MD}")
        print(f"[DOCX] Saved {OUTPUT_DOCX}")

        # Initialize optional outputs
        png_path = None
        bpmn_path = None

        # Generate BPMN only if enabled
        if ENABLE_BPMN_GENERATION:
            bpmn_xml = generate_bpmn_xml(self.memory)
            if bpmn_xml:  # Only save if content was generated
                with open(OUTPUT_BPMN, "w", encoding="utf-8") as f:
                    f.write(bpmn_xml)
                bpmn_path = OUTPUT_BPMN
                print(f"[BPMN] Saved {OUTPUT_BPMN}")
            else:
                print("[BPMN] Skipped (generation disabled)")
        else:
            print("[BPMN] Skipped (ENABLE_BPMN_GENERATION=false)")

        # Generate PNG only if enabled
        if ENABLE_PNG_GENERATION:
            png_path = render_diagrams_png(self.memory, OUTPUT_DIAGRAM_PNG)
            if png_path:
                print(f"[PNG]  Saved {png_path}")
            else:
                print("[PNG]  Skipped (Diagrams/lib missing or no steps)")
        else:
            print("[PNG]  Skipped (ENABLE_PNG_GENERATION=false)")

        # Append artifact references to Markdown
        md_footer = "\\n\\n---\\n### Artifacts\\n"
        if bpmn_path:
            md_footer += f"- **BPMN 2.0 XML**: `{OUTPUT_BPMN}`\\n"
        if png_path:
            md_footer += f"- **Process PNG (Diagrams)**: `{png_path}`\\n"
            md_footer += f"\\n![Process Diagram]({os.path.basename(png_path)})\\n"
        
        # Update the markdown file with artifacts section
        if bpmn_path or png_path:
            md += md_footer
            render_markdown_document(md, OUTPUT_MD)
            render_docx_from_markdownish(md, OUTPUT_DOCX)

        return OUTPUT_MD, png_path, bpmn_path, OUTPUT_DOCX

# =========================================================
# Speech pipeline
# =========================================================
async def run_capture():
    speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
    speech_config.speech_recognition_language = RECO_LANG
    speech_config.set_property(
        speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs, "800"
    )
    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    recognizer = speechsdk.SpeechRecognizer(speech_config, audio_config)

    orchestrator = ProcessOrchestrator()

    async def handle_final_text(text: str):
        if not ENABLE_INTERVIEW_MODE:
            await orchestrator.process_utterance(text, "ANSWER")
            return
        role = await classify_role(text)
        await orchestrator.process_utterance(text, role)

    def recognizing(evt):
        partial = evt.result.text
        if partial:
            print(f"[Partial]: {partial}")

    def recognized(evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            final_text = evt.result.text
            print(f"[Final]: {final_text}")
            asyncio.create_task(handle_final_text(final_text))
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            print("[No speech recognized]")

    def session_stopped(evt):
        print("[Session stopped]")

    recognizer.recognizing.connect(recognizing)
    recognizer.recognized.connect(recognized)
    recognizer.session_stopped.connect(session_stopped)

    print("Starting continuous recognition... Press Ctrl+C to stop.")
    recognizer.start_continuous_recognition()

    try:
        while True:
            await asyncio.sleep(5)
            await orchestrator.idle_check()
    except KeyboardInterrupt:
        print("\\nStopping...")

    recognizer.stop_continuous_recognition()
    await orchestrator.force_flush()

    print("Finalizing documents...")
    md_path, png_path, bpmn_path, docx_path = await orchestrator.finalize_documents()
    print(f"Saved Markdown: {md_path}")
    if png_path:
        print(f"Saved PNG:     {png_path}")
    if bpmn_path:
        print(f"Saved BPMN:    {bpmn_path}")
    if Document is not None:
        print(f"Saved DOCX:    {docx_path}")
    else:
        print("DOCX skipped (python-docx not installed).")

async def process_markdown_transcript(md_path: str):
    """Process a markdown transcript file"""
    orchestrator = ProcessOrchestrator()
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    paragraphs = [p.strip() for p in content.split('\\n\\n') if p.strip()]
    
    print(f"Processing {len(paragraphs)} paragraphs from markdown transcript...")
    
    for i, paragraph in enumerate(paragraphs):
        if not paragraph:
            continue
            
        print(f"Processing paragraph {i+1}/{len(paragraphs)}: {paragraph[:100]}...")
        
        if not ENABLE_INTERVIEW_MODE:
            await orchestrator.process_utterance(paragraph, "ANSWER")
        else:
            role = await classify_role(paragraph)
            print(f"Classified as: {role}")
            await orchestrator.process_utterance(paragraph, role)
    
    print("Force flushing any remaining chunks...")
    await orchestrator.force_flush()
    
    print("Finalizing documents...")
    md_path, png_path, bpmn_path, docx_path = await orchestrator.finalize_documents()
    print(f"Saved Markdown: {md_path}")
    if png_path:
        print(f"Saved PNG:     {png_path}")
    if bpmn_path:
        print(f"Saved BPMN:    {bpmn_path}")
    if Document is not None:
        print(f"Saved DOCX:    {docx_path}")
    else:
        print("DOCX skipped (python-docx not installed).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process interview via speech or markdown transcript.")
    parser.add_argument("--transcript_md", type=str, default=None, help="Path to a markdown file containing the interview transcript. If provided, bypasses speech-to-text.")
    args = parser.parse_args()
    if args.transcript_md:
        asyncio.run(process_markdown_transcript(args.transcript_md))
    else:
        asyncio.run(run_capture())