# Azure AI Process Documentation Creation

An intelligent process documentation system that captures business processes through live speech interviews or markdown transcripts and automatically generates comprehensive, structured documentation using Azure AI services.

## Overview

This solution leverages Azure Cognitive Services Speech-to-Text and Azure OpenAI to transform conversational interviews about business processes into professionally structured documentation following organizational process definition templates. It supports both real-time speech capture and processing of pre-recorded interview transcripts.

## Features

### Core Capabilities
- **Real-time Speech-to-Text**: Capture process knowledge through live interviews using Azure Speech Services
- **Markdown Transcript Processing**: Process pre-recorded interviews from markdown files
- **Intelligent Q&A Classification**: Automatically distinguish between interviewer questions and subject matter expert answers
- **Structured Knowledge Extraction**: Extract process information following comprehensive organizational templates
- **Multi-format Output**: Generate documentation in Markdown, DOCX, BPMN 2.0 XML, and PNG diagram formats
- **Incremental Processing**: Process content in manageable chunks with intelligent overlap for context preservation

### Process Documentation Template

The solution extracts and documents:

#### Mandatory Attributes
1. Process Name
2. Description (non-expert friendly)
3. Owner
4. Start Event (trigger)
5. End Event (outcome)
6. Actors (key units/roles with responsibilities)
7. Tools Used (applications, dashboards, AI models, etc.)
8. Data Points (CRUD operations with classifications)
9. Duration
10. Main Flow (detailed process steps)

#### Process Characteristics
11. Variations
12. Harmonized Status
13. Automation Level
14. AI Enablement
15. Modelling Status
16. Model Priority

#### Governance & Control
17. Risks
18. Control Points
19. Control Findings
20. Recommendations
21. Guidelines
22. Constraints
23. Legacy Constraints
24. Pain Points

#### Supporting Information
25. Alternate Paths
26. Exceptions & Error Handling
27. Glossary

## Prerequisites

### Azure Services
- **Azure Speech Services** (for speech-to-text functionality)
  - Speech API key
  - Service region
- **Azure OpenAI** (for content extraction and document generation)
  - API key
  - Endpoint URL
  - Deployed GPT-4 or GPT-4o model

### Software Requirements
- Python 3.8 or higher
- pip (Python package manager)

### Optional Dependencies
- Graphviz (for PNG diagram generation)
- BPMN visualization tools (for BPMN diagram rendering)

## Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd azureai-process-doc-creation
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

The `requirements.txt` includes:
- `azure-cognitiveservices-speech` - Azure Speech-to-Text
- `openai` - Azure OpenAI integration
- `python-docx` - DOCX document generation
- `diagrams` - PNG diagram generation (optional)
- `bpmn-python` - BPMN visualization (optional)

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Azure Speech Services
AZURE_SPEECH_KEY=your_speech_key_here
AZURE_SPEECH_REGION=your_region_here

# Azure OpenAI
AZURE_OPENAI_KEY=your_openai_key_here
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_MODEL=gpt-4o

# Optional: Recognition Language (default: en-US)
RECO_LANG=en-US

# Optional: Interview Mode (default: true)
ENABLE_INTERVIEW_MODE=true

# Optional: Role Classification (default: heuristic)
ROLE_CLASSIFIER_MODE=heuristic

# Optional: Output Generation (default: false)
ENABLE_BPMN_GENERATION=false
ENABLE_PNG_GENERATION=false
```

### 4. Install Optional Dependencies for Diagrams

For PNG diagram generation:
```bash
# macOS
brew install graphviz

# Ubuntu/Debian
sudo apt-get install graphviz

# Windows
# Download from https://graphviz.org/download/
```

## Usage

### Mode 1: Real-time Speech Capture

Capture process knowledge through live interview:

```bash
python process_doc.py
```

**What happens:**
1. System starts listening through your default microphone
2. Speak naturally - the interviewer asks questions, SME provides answers
3. System automatically classifies questions vs. answers
4. Processes answers in chunks, building process knowledge incrementally
5. Press Ctrl+C to stop and generate final documents
6. Documents are saved with timestamp in filename

**Tips for Live Capture:**
- Speak clearly and at a moderate pace
- Natural pauses help the system chunk content appropriately
- Follow the interview guide in `INTERVIEW_GUIDE.md`
- Review `SAMPLE_INTERVIEW_TEMPLATE.md` for example format

### Mode 2: Markdown Transcript Processing

Process pre-recorded interview from markdown file:

```bash
python process_doc.py --transcript_md AML_Interview_Transcript.md
```

**What happens:**
1. System reads the markdown file
2. Processes each paragraph
3. Classifies content as questions or answers (if interview mode enabled)
4. Extracts process knowledge following the template
5. Generates comprehensive documentation

**Markdown Transcript Format:**
- Each paragraph should represent one complete thought
- Separate paragraphs with blank lines
- No special formatting required
- See `AML_Interview_Transcript.md` for example

## Output Files

Each run generates timestamped files:

### Always Generated
1. **`process_document_YYYYMMDD_HHMMSS.md`** - Structured Markdown documentation
2. **`process_document_YYYYMMDD_HHMMSS.docx`** - Microsoft Word document (if python-docx installed)

### Optionally Generated (based on configuration)
3. **`process_YYYYMMDD_HHMMSS.bpmn`** - BPMN 2.0 XML file (if ENABLE_BPMN_GENERATION=true)
4. **`process_YYYYMMDD_HHMMSS.png`** - Process flow diagram (if ENABLE_PNG_GENERATION=true)


### Chunking Parameters (Advanced)

Edit in `process_doc.py`:
```python
CHUNK_TOKEN_TARGET = 800      # Target tokens per chunk
CHUNK_TOKEN_MAX = 1100         # Maximum tokens before force flush
CHUNK_OVERLAP = 120            # Token overlap between chunks
IDLE_FLUSH_SECONDS = 20        # Seconds of silence before flush
```

## Architecture

### System Components

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Speech Input   │────▶│  Azure Speech    │────▶│  Text Stream    │
│  (Microphone)   │     │  Services        │     │                 │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                            │
┌─────────────────┐                                        │
│  Markdown File  │────────────────────────────────────────┘
└─────────────────┘                                        │
                                                            ▼
                                                  ┌─────────────────┐
                                                  │ Q&A Classifier  │
                                                  │  (Heuristic/    │
                                                  │   LLM-based)    │
                                                  └────────┬────────┘
                                                           │
                        ┌──────────────────────────────────┴──────────┐
                        │                                              │
                        ▼                                              ▼
              ┌──────────────────┐                         ┌──────────────────┐
              │   Questions      │                         │    Answers       │
              │  (Discarded/     │                         │  (Processed)     │
              │   Context Only)  │                         └────────┬─────────┘
              └──────────────────┘                                  │
                                                                     ▼
                                                          ┌─────────────────────┐
                                                          │  Chunk Buffer       │
                                                          │  (Smart Overlap)    │
                                                          └──────────┬──────────┘
                                                                     │
                                                                     ▼
                                                          ┌─────────────────────┐
                                                          │  Azure OpenAI       │
                                                          │  Knowledge Extract  │
                                                          └──────────┬──────────┘
                                                                     │
                                                                     ▼
                                                          ┌─────────────────────┐
                                                          │  Process Memory     │
                                                          │  (JSON Model)       │
                                                          │  + Merge Logic      │
                                                          └──────────┬──────────┘
                                                                     │
                                                                     ▼
                                                          ┌─────────────────────┐
                                                          │  Azure OpenAI       │
                                                          │  Document Generator │
                                                          └──────────┬──────────┘
                                                                     │
                        ┌────────────────────────────────────────────┼────────────────────┐
                        │                                            │                    │
                        ▼                                            ▼                    ▼
              ┌──────────────────┐                        ┌──────────────────┐  ┌─────────────────┐
              │  Markdown (.md)  │                        │  DOCX Document   │  │  BPMN XML       │
              └──────────────────┘                        └──────────────────┘  │  PNG Diagram    │
                                                                                 └─────────────────┘
```

### Processing Flow

1. **Input Stage**: Speech or markdown text
2. **Classification Stage**: Identify questions vs. answers
3. **Chunking Stage**: Buffer answers into processable segments
4. **Extraction Stage**: Extract structured knowledge using Azure OpenAI
5. **Merging Stage**: Incrementally build comprehensive process model
6. **Generation Stage**: Create final documents in multiple formats

## Key Design Patterns

### Intelligent Chunking
- **Overlapping chunks**: Maintains context across boundaries
- **Token-aware**: Respects model input limits
- **Idle detection**: Automatically processes after periods of silence

### Q&A Separation
- **Interview Mode**: Distinguishes interviewer questions from SME answers
- **Context Preservation**: Recent questions provide context for answer extraction
- **Flexible Classification**: Heuristic (fast) or LLM-based (accurate)

### Incremental Knowledge Building
- **Chunk-by-chunk extraction**: Processes content in manageable pieces
- **Smart merging**: Deduplicates and reconciles information
- **Memory persistence**: Maintains growing process model throughout session

## Workflow Guide

### 1. Prepare for Interview

Review the interview guide and template:
- `INTERVIEW_GUIDE.md` - Questions organized by template sections
- `SAMPLE_INTERVIEW_TEMPLATE.md` - Example interview format

### 2. Configure Environment

Set up `.env` file with your Azure credentials.

### 3. Run Capture Session

Choose your input method:
```bash
# Live speech
python process_doc.py

# Pre-recorded transcript
python process_doc.py --transcript_md your_transcript.md
```

### 4. Review Generated Documents

Check the timestamped output files:
- Review the Markdown for completeness
- Open DOCX for sharing/editing
- Validate BPMN diagram (if enabled)

### 5. Iterate if Needed

If documentation is incomplete:
- Conduct follow-up interview
- Process additional transcript
- Manually edit Markdown output

## Troubleshooting

### Speech Recognition Issues

**Problem**: No speech recognized
- Check microphone permissions
- Verify `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION`
- Test with `arecord` (Linux) or system audio settings

**Problem**: Poor recognition accuracy
- Adjust `RECO_LANG` for your language
- Speak more slowly and clearly
- Reduce background noise

### OpenAI Issues

**Problem**: API authentication errors
- Verify `AZURE_OPENAI_KEY` and `AZURE_OPENAI_ENDPOINT`
- Check Azure OpenAI resource access

**Problem**: Model not found
- Confirm model deployment name matches `AZURE_OPENAI_MODEL`
- Ensure model is deployed in your Azure OpenAI resource

### Output Generation Issues

**Problem**: DOCX not generated
- Install python-docx: `pip install python-docx`

**Problem**: PNG diagrams not generated
- Install Graphviz system package
- Set `ENABLE_PNG_GENERATION=true` in `.env`
- Install diagrams: `pip install diagrams`

**Problem**: BPMN file empty or invalid
- Set `ENABLE_BPMN_GENERATION=true` in `.env`
- Ensure process has main flow steps
- Validate XML with BPMN validator

## Example Workflows

### Workflow 1: Quick Process Capture
```bash
# 1. Start live capture
python process_doc.py

# 2. Conduct 15-30 minute interview
# Follow INTERVIEW_GUIDE.md structure

# 3. Press Ctrl+C when complete

# 4. Review generated markdown
cat process_document_*.md
```

### Workflow 2: Transcript Processing
```bash
# 1. Prepare markdown transcript
# See SAMPLE_INTERVIEW_TEMPLATE.md for format

# 2. Process transcript
python process_doc.py --transcript_md my_interview.md

# 3. Review all outputs
ls -l process_*
```

### Workflow 3: Full Documentation with Diagrams
```bash
# 1. Enable all features in .env
# ENABLE_BPMN_GENERATION=true
# ENABLE_PNG_GENERATION=true

# 2. Run capture
python process_doc.py

# 3. Verify all outputs generated
ls -l process_document_*.md
ls -l process_document_*.docx
ls -l process_*.bpmn
ls -l process_*.png
```

## Advanced Usage

### Custom Prompts

Edit prompts in `process_doc.py`:
- `CHUNK_EXTRACT_SYSTEM`: Controls extraction from text chunks
- `MERGE_SYSTEM`: Controls how chunks are merged
- `FINAL_DOC_SYSTEM`: Controls final document generation
- `CLASSIFY_SYSTEM`: Controls Q&A classification

### Extended Schema

Modify `empty_process_memory()` in `process_doc.py` to add custom fields to the process model.

### Custom Output Formats

Extend `process_doc_utils.py` with additional rendering functions.

## Best Practices

### For Interviewers
1. Follow the structured interview guide
2. Ask open-ended questions
3. Allow SME to speak without interruption
4. Probe for specifics on tools, data, and actors
5. Verify understanding before moving to next section

### For Subject Matter Experts
1. Speak clearly and at moderate pace
2. Provide specific examples
3. Mention tool names and data classifications
4. Describe exceptions and alternate paths
5. Highlight pain points and improvement opportunities

### For Optimal Results
1. Conduct 20-45 minute focused interviews
2. Cover all mandatory attributes
3. Use consistent terminology
4. Review generated documentation promptly
5. Iterate with follow-up sessions if needed

## Contributing

Contributions are welcome! Areas for enhancement:
- Additional output format generators
- Improved BPMN layout algorithms
- Multi-language support
- Web-based interview interface
- Process comparison and versioning

## License

See [LICENSE](LICENSE) file for details.

## Support

For issues, questions, or contributions:
1. Check troubleshooting section above
2. Review sample files for format guidance
3. Verify Azure service configuration
4. Open an issue with detailed error messages and logs

---

**Version**: 1.0  
**Last Updated**: October 2025