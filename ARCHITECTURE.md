# Architecture Documentation

> This file is structured for AI-assisted diagram generation tools (Eraser.io, Lucidchart AI,
> Mermaid Live, draw.io AI, GitHub Copilot, etc.).
> Each section contains both Mermaid syntax diagrams and plain-text descriptions
> that any copilot tool can use to regenerate or modify diagrams.

---

## 1. System Overview Diagram

```mermaid
graph TD
    User["👤 User<br/>(Browser)"]
    ChatUI["chat.html<br/>Browser Chat UI"]
    API["api.py<br/>FastAPI Web Server<br/>Port 8000"]
    Claude["Claude Sonnet 4.6<br/>Anthropic API"]
    MCP["mcp_server.py<br/>MCP Server<br/>stdio subprocess"]
    DB["database.py<br/>SQLite<br/>data.db"]
    RAG["rag.py<br/>ChromaDB<br/>chroma_db/"]
    DOCS["docs/<br/>txt, md, PDF files"]
    CLI["agent.py<br/>CLI Agent<br/>(alternative)"]

    User -->|HTTP Request| ChatUI
    ChatUI -->|POST /stream SSE| API
    API -->|Anthropic SDK| Claude
    Claude -->|tool_use blocks| API
    API -->|stdio JSON-RPC| MCP
    MCP -->|read/write| DB
    MCP -->|index/search| RAG
    RAG -->|read files| DOCS
    MCP -->|read files| DOCS

    User -.->|terminal input| CLI
    CLI -.->|stdio JSON-RPC| MCP
```

---

## 2. Request Lifecycle — Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant Browser as Browser (chat.html)
    participant API as api.py (FastAPI)
    participant Claude as Claude Sonnet 4.6
    participant MCP as mcp_server.py
    participant ChromaDB as ChromaDB (rag.py)
    participant SQLite as SQLite (database.py)

    User->>Browser: types question
    Browser->>API: POST /stream {message, session_id}
    API->>SQLite: session_get(session_id)
    SQLite-->>API: conversation history
    API->>Claude: messages + 8 tool schemas
    Claude-->>API: tool_use: search_docs(query)
    API->>MCP: call_tool("search_docs", {query})
    MCP->>ChromaDB: search(query, n=4)
    ChromaDB-->>MCP: top 4 relevant chunks
    MCP-->>API: TextContent with chunks
    API->>Claude: tool_result with chunks
    Claude-->>API: final text response (streamed)
    API->>SQLite: session_save(session_id, history)
    API-->>Browser: SSE stream (text chunks)
    Browser-->>User: response renders in real time
```

---

## 3. MCP Tool Architecture

```mermaid
graph LR
    subgraph MCP_Server["mcp_server.py — MCP Server"]
        LT["list_tools()<br/>tool discovery"]
        CT["call_tool()<br/>tool execution"]

        subgraph Tools["8 Tools"]
            T1["get_current_datetime"]
            T2["calculate"]
            T3["get_weather"]
            T4["manage_notes"]
            T5["list_docs"]
            T6["read_doc"]
            T7["index_docs"]
            T8["search_docs"]
        end
    end

    T4 -->|CRUD| SQLite["SQLite<br/>database.py"]
    T7 -->|chunk + embed| ChromaDB["ChromaDB<br/>rag.py"]
    T8 -->|semantic search| ChromaDB
    T5 -->|list files| Docs["docs/ folder"]
    T6 -->|read file| Docs
    T7 -->|read files| Docs
```

---

## 4. Data Persistence Architecture

```mermaid
graph TD
    subgraph SQLite["SQLite — data.db"]
        Notes["notes table<br/>─────────────────<br/>title TEXT PK<br/>content TEXT<br/>created_at TEXT"]
        Sessions["sessions table<br/>─────────────────<br/>session_id TEXT PK<br/>messages TEXT (JSON)<br/>created_at TEXT<br/>updated_at TEXT"]
    end

    subgraph ChromaDB["ChromaDB — chroma_db/"]
        Collection["docs collection<br/>─────────────────<br/>id: filename::chunk::N<br/>document: chunk text<br/>embedding: float[384]<br/>metadata: source, chunk_index"]
    end

    manage_notes -->|read/write| Notes
    api_sessions -->|read/write| Sessions
    index_docs -->|write embeddings| Collection
    search_docs -->|query vectors| Collection
```

---

## 5. RAG Pipeline Diagram

```mermaid
flowchart LR
    subgraph Indexing["Indexing Phase (on startup)"]
        direction TB
        Files["docs/*.txt<br/>docs/*.md"] --> Chunker
        Chunker["Text Chunker<br/>500 chars<br/>100 char overlap"] --> Embedder
        Embedder["Sentence Transformer<br/>all-MiniLM-L6-v2<br/>384-dim vectors"] --> VectorDB
        VectorDB["ChromaDB<br/>Persistent Storage"]
    end

    subgraph Query["Query Phase (per question)"]
        direction TB
        Question["User Question"] --> QEmbed
        QEmbed["Embed Question<br/>→ 384-dim vector"] --> Search
        Search["Similarity Search<br/>cosine distance"] --> TopK
        TopK["Top 4 Chunks<br/>with source + score"] --> Claude2
        Claude2["Claude Sonnet 4.6<br/>answers from chunks"]
    end

    VectorDB -.->|stored vectors| Search
```

---

## 6. File Structure Map

```mermaid
graph TD
    Root["MCP Project/"]

    Root --> api["api.py<br/>FastAPI server<br/>routes + SSE + lifespan"]
    Root --> agent["agent.py<br/>CLI agent<br/>terminal interface"]
    Root --> mcp["mcp_server.py<br/>MCP server<br/>8 tool definitions"]
    Root --> db["database.py<br/>SQLite helpers<br/>notes + sessions CRUD"]
    Root --> rag["rag.py<br/>ChromaDB helpers<br/>chunk + embed + search"]
    Root --> conv["convert_pdfs.py<br/>Tesseract OCR<br/>scanned PDF → txt"]
    Root --> inspect["inspect_db.py<br/>DB utility<br/>view SQLite contents"]

    Root --> templates["templates/"]
    templates --> html["chat.html<br/>browser UI<br/>SSE streaming"]

    Root --> docs["docs/"]
    docs --> txt[".txt files"]
    docs --> md[".md files"]
    docs --> pdf[".pdf files"]

    Root --> data["data.db<br/>SQLite database<br/>(gitignored)"]
    Root --> chroma["chroma_db/<br/>ChromaDB vectors<br/>(gitignored)"]
```

---

## 7. Technology Stack Map

```mermaid
graph LR
    subgraph Frontend
        HTML["chat.html<br/>Vanilla JS + CSS<br/>SSE EventSource"]
    end

    subgraph Backend
        FastAPI["FastAPI<br/>Python 3.12<br/>Async ASGI"]
        Uvicorn["Uvicorn<br/>ASGI Server"]
    end

    subgraph AI_Layer
        AnthropicSDK["Anthropic SDK<br/>anthropic[mcp]"]
        Claude["Claude Sonnet 4.6<br/>claude-sonnet-4-6"]
        MCP_Lib["MCP Library<br/>JSON-RPC Protocol"]
    end

    subgraph Storage
        SQLiteDB["SQLite<br/>sqlite3 (built-in)"]
        ChromaDBStore["ChromaDB<br/>Vector Database"]
        Filesystem["Filesystem<br/>docs/ folder"]
    end

    subgraph ML
        SentenceT["sentence-transformers<br/>all-MiniLM-L6-v2<br/>384-dim embeddings"]
    end

    subgraph PDF_Processing
        PyPDF["pypdf<br/>text-based PDFs"]
        PyMuPDF["pymupdf (fitz)<br/>PDF → images"]
        Tesseract["Tesseract OCR<br/>image → text"]
    end

    HTML --> FastAPI
    FastAPI --> AnthropicSDK
    AnthropicSDK --> Claude
    AnthropicSDK --> MCP_Lib
    MCP_Lib --> SQLiteDB
    MCP_Lib --> ChromaDBStore
    MCP_Lib --> Filesystem
    ChromaDBStore --> SentenceT
    Filesystem --> PyPDF
    Filesystem --> PyMuPDF
    PyMuPDF --> Tesseract
```

---

## Component Descriptions (Plain Text for Copilot Tools)

### api.py
- Type: FastAPI web server
- Port: 8000
- Responsibilities: HTTP routing, SSE streaming, session management, MCP lifecycle
- Key endpoints: GET /, POST /chat, POST /stream, GET /tools, GET /sessions, DELETE /session/{id}
- Connections: Browser (HTTP in), Anthropic API (HTTPS out), mcp_server.py (stdio subprocess)
- On startup: spawns mcp_server.py, initialises SQLite, auto-indexes docs into ChromaDB

### mcp_server.py
- Type: MCP server (stdio transport)
- Protocol: JSON-RPC 2.0 over stdin/stdout
- Responsibilities: tool definitions, tool execution
- Tools: 8 (get_current_datetime, calculate, get_weather, manage_notes, list_docs, read_doc, index_docs, search_docs)
- Connections: api.py or agent.py (parent process via stdio), database.py, rag.py, docs/ filesystem

### database.py
- Type: SQLite abstraction layer
- File: data.db (project root, gitignored)
- Tables: notes (title PK, content, created_at), sessions (session_id PK, messages JSON, created_at, updated_at)
- Used by: mcp_server.py (manage_notes tool), api.py (session persistence)

### rag.py
- Type: RAG (Retrieval Augmented Generation) module
- Vector DB: ChromaDB (persistent, chroma_db/ folder, gitignored)
- Embedding model: sentence-transformers all-MiniLM-L6-v2 (384 dimensions, ~80MB, cached locally)
- Chunk size: 500 chars with 100 char overlap
- Collection name: "docs"
- Used by: mcp_server.py (index_docs and search_docs tools), api.py (auto-index on startup)

### agent.py
- Type: CLI application
- Interface: terminal (input/print)
- Responsibilities: same as api.py but terminal-based, single user, single session
- Used for: learning, debugging, quick testing

### chat.html
- Type: Single-page frontend
- Technology: Vanilla JavaScript, CSS
- Features: SSE streaming, session persistence via localStorage, tool call indicators
- Communication: POST /stream → SSE event stream

---

## Data Flow Descriptions (Plain Text for Copilot Tools)

### Flow 1: User asks a question (web)
1. User types in browser → POST /stream to api.py
2. api.py loads session history from SQLite
3. api.py calls Claude API with history + 8 tool schemas
4. Claude returns tool_use block for search_docs
5. api.py forwards to mcp_server.py via stdio JSON-RPC
6. mcp_server.py calls rag.py → ChromaDB similarity search
7. ChromaDB returns top 4 relevant chunks
8. api.py sends tool_result back to Claude
9. Claude streams final text response
10. api.py streams SSE events to browser
11. api.py saves updated session to SQLite

### Flow 2: Document indexing
1. api.py startup triggers index_all() in rag.py
2. rag.py reads all .txt and .md files from docs/
3. Each file is split into ~500 char chunks with 100 char overlap
4. Each chunk is embedded using all-MiniLM-L6-v2 → 384-dim float vector
5. Vectors stored in ChromaDB with metadata {source, chunk_index}

### Flow 3: PDF conversion (manual step)
1. User drops PDF into docs/ folder
2. User runs convert_pdfs.py
3. pymupdf renders each page at 300 DPI → PNG image
4. pytesseract runs Tesseract OCR on each image → text
5. Text saved as .txt alongside the original PDF
6. Server restart triggers auto-indexing of the new .txt file
