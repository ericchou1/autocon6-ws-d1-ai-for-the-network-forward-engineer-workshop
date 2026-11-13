# Bonus: RAG — Retrieval-Augmented Generation

**Time:** ~15 min
**Prerequisites:** Lab 2 completed (you'll want to remember `BGP_REFERENCE` from `analyzer.py`).

In Lab 2 (Step 6), we hardcoded a `BGP_REFERENCE` string in the script — six lines of RFC excerpts that the LLM used to ground its answers. That works because the reference fit in the prompt.

What if your reference is 6,000 pages of vendor docs? You can't stuff that into every prompt. **RAG retrieves only the relevant chunks** for each question and injects them as context. The LLM gets exactly the reference it needs, nothing more.

## Concept

```
Lab 2/3 approach:                     RAG approach:
─────────────────                     ─────────────

  question                              question
     │                                     │
     ▼                                     ▼
  ┌─────┐    full BGP_REFERENCE        ┌─────────┐    embed question
  │ LLM │ ◄ ─ ─ (hardcoded in code)    │retriever│ ─ ─ ─ ─ ─ ─ ─►
  └─────┘                              └─────────┘     ┌───────────┐
     │                                     │           │ vector    │
     ▼                                     │  top-k    │ store of  │
  answer                                   ▼           │ doc chunks│
                                       relevant chunks └───────────┘
                                           │
                                           ▼
                                       ┌─────┐
                                       │ LLM │  ◄─── question +
                                       └─────┘       retrieved chunks
                                           │
                                           ▼
                                       answer
```

The shift is: the *reference material* moves out of your source code and into a vector store you can grow indefinitely.

## Step 1: Look at the knowledge base

Three small markdown files in `bonus/rag/kb/`:

- `bgp_states.md` — what each BGP state means and how it transitions
- `bgp_troubleshooting.md` — common BGP problems and their diagnostic patterns
- `lab_topology.md` — specific topology reference for r1/r2/r3

Skim them. In a real deployment this would be vendor docs, runbooks, NOC notes, post-mortems — anything that captures institutional knowledge in plain text.

## Step 2: Build the retrieve-augment-generate pipeline

```bash
pip install faiss-cpu
```

See `rag_demo.py` in this folder. The three phases are clearly separated:

1. **Load and chunk** — split the markdown files into ~400-character chunks.
2. **Embed and store** — convert each chunk to a vector via OpenAI's embedding model, store in an in-memory FAISS index.
3. **Retrieve, augment, generate** — for each question, find the top-3 most similar chunks, stuff them into the prompt, then call the LLM.

Run it:

```bash
cd bonus/rag
python rag_demo.py
```

**Expected:**

- **Q1** ("active state") — retrieves chunks from `bgp_states.md` and `bgp_troubleshooting.md`. The answer is specific, grounded in the reference, and probably mentions "peer-side configuration issue" — which is straight from the KB, not the LLM's general training.
- **Q2** ("which routers should have iBGP") — retrieves from `lab_topology.md`. The answer names r1 and r2 specifically. **The LLM couldn't have known this from training** — this is your topology, not a generic one. RAG is what made it work.
- **Q3** ("TCP vs UDP") — the KB doesn't cover it, and the retriever returns three only-vaguely-related chunks (they mention TCP/179). Watch what the model does with them. With the prompt instruction to say so plainly, the *ideal* response is "the reference doesn't cover this." In practice current models often answer from general knowledge anyway and merely note that the reference only mentions TCP in passing — correct, but not what you asked for. That gap is a prompt-engineering problem (make the instruction stricter, or have the code refuse when the top similarity score is low) and it's exactly the kind of thing Lab 5's judge would catch at scale.

## Step 3: Compare against no-RAG

The script also runs the same Q2 *without* RAG at the bottom, for comparison. The no-RAG answer will be either a generic "depends on your topology" hedge, or a confident-sounding hallucination about routers it knows nothing about. Either way: not useful. That's the gap RAG closes.

## Going Further

### 1. Swap to local embeddings

> 🔶 **GitHub Pro image only:** this pulls an extra embedding model (`nomic-embed-text`, ~275 MB). The base RAG demo above (OpenAI embeddings) runs fine on the default Codespace — this local-embeddings swap is reserved for the **GitHub Pro** image to keep the default lean.

`OpenAIEmbeddings` sends every chunk to OpenAI's API. For data sovereignty (the workshop's recurring theme), swap to a local embedding model via Ollama:

```bash
ollama pull nomic-embed-text
```

```python
from langchain_ollama import OllamaEmbeddings
embeddings = OllamaEmbeddings(model="nomic-embed-text")
```

Now your reference data never leaves the box. The query and answer still go to the LLM, but the embeddings are local.

### 2. Persistent vector store

FAISS in-memory is fine for 100 chunks. For 100,000 chunks, you want persistence. Try [Chroma](https://www.trychroma.com/) or [Qdrant](https://qdrant.tech/) — both have LangChain integrations and can run as local daemons or hosted services.

### 3. Combine RAG with the Lab 3 agent

Make the BGP reference *retrieved*, not hardcoded. Lab 2's `BGP_REFERENCE` becomes a vector store, and the analyzer prompt pulls only the relevant lines for each parse. For a 6-line reference it's overkill. For a 600-page vendor doc, it's the only way.

### 4. Re-ranking

`similarity_search` returns the most embeddings-similar chunks. Embeddings get you to "approximately relevant" — re-rankers refine that to "most relevant." Look at `bge-reranker` or [Cohere's rerank API](https://cohere.com/rerank) for the next level of precision.

### 5. Evals — does your RAG actually retrieve the right thing?

Build a small test set: 10-20 questions with the *correct retrieved doc* labeled. Measure retrieval recall (did we get the right chunk in the top-k?) separately from answer quality. This decouples "retriever is broken" from "LLM is hallucinating" — they're different failure modes with different fixes. You already have the harness: Lab 5's `run_parser_experiment.py` is a template — a dataset of questions with the expected source file, a task that runs `answer_with_rag`, and a code evaluator that checks whether the right chunk was in the top-k.
