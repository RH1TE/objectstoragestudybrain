# Object Storage Study Brain

Small Python tool for turning files in Object Storage into Markdown and a local full text index. It works with providers that expose an S3 compatible API.

I built it because I wanted the original files to stay in object storage, while keeping a plain text copy that is easy to search or feed into other tools.

The easiest way to think about it is as a small wiki/search engine for a document collection. It does the ingestion and retrieval part, but it is deliberately not tied to a particular LLM or notes app.

That also makes it useful as a knowledge layer in front of an AI model. Instead of sending a whole folder of PDFs or notes to an API every time, an application can search the local index first and send only the relevant Markdown chunks. Depending on the application, that can reduce token/API usage and keep more of the document handling local.

The generated Markdown and SQLite index can be used directly, or connected to Ollama, OpenAI, Claude, a web UI, a voice assistant, or another RAG frontend.

Supported inputs at the moment:

* PDF
* DOCX
* PPTX
* text and Markdown
* HTML and RTF
* Jupyter notebooks
* CSV and XLSX
* LaTeX source

PDF output keeps page markers. PowerPoint output keeps slide markers. The generated Markdown also records the source key, ETag, timestamp and SHA 256 hash.

## Install

Python 3.11 or newer is required.

```bash
pip install .
```

Storage credentials are read using boto3's normal credential chain. The project does not store them, and there is no dotenv loader in the project.

Storage settings can also be supplied as environment variables:

```bash
export STUDY_BRAIN_BUCKET="mystudyfiles"
export STUDY_BRAIN_ENDPOINT_URL="https://objectstorage.example.net"
export STUDY_BRAIN_REGION="region1"
export STUDY_BRAIN_PROFILE="study"
export STUDY_BRAIN_SOURCE_PREFIX="notes"
export STUDY_BRAIN_DERIVED_PREFIX="generatedmarkdown"
export STUDY_BRAIN_WORK_DIR="./work"
export STUDY_BRAIN_INTERVAL="60"
export STUDY_BRAIN_WRITE_BACK="false"
```

With those set, a sync can just be:

```bash
studybrain sync
```

Command line options override the matching environment variables. `.env` files are ignored by Git and are not loaded by this package.

## Use

Run a one off sync:

```bash
studybrain sync
```

The bucket, endpoint, region, prefixes and work directory come from the environment settings above.

By default all generated data stays under `./work`. Nothing is written back to Object Storage.

If you want generated Markdown written back, set:

```bash
export STUDY_BRAIN_WRITE_BACK="true"
studybrain sync
```

The watcher uses the same settings and runs repeatedly:

```bash
studybrain watch
```

Search the local index:

```bash
studybrain search "diffraction aperture"
```

The search index is SQLite FTS5. It is intentionally simple so the Markdown can also be indexed somewhere else if needed.

## Where this fits

This repository is the ingestion/search engine rather than the final chat interface.

A simple setup can use it as a local document wiki. A larger setup can put it in front of an LLM or RAG application: search locally first, select a few relevant chunks, then send only those chunks to the model. That avoids repeatedly uploading or sending the full source collection and can reduce API and token usage.

The output is deliberately portable. The Markdown/index can sit behind Ollama, OpenAI, Claude, a web app, a voice assistant, or another search/RAG frontend.

A useful next step is a generic local Q&A interface that works directly against the index and does not require a paid AI API. That can remain optional so the ingestion/search engine is still useful on its own.

## Safety

The sync command does not delete source objects from Object Storage. When a source disappears, only the matching cached source and generated Markdown under the local work directory are removed.

Object Storage write back is off by default. When enabled through STUDY_BRAIN_WRITE_BACK, generated Markdown is uploaded only to the configured derived prefix.

## Tests

```bash
pip install '.[dev]'
pytest
ruff check .
```

The tests generate their own temporary documents.
