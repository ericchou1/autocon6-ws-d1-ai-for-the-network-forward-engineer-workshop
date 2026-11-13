"""rag_demo.py — minimal RAG over a small network reference KB."""
from pathlib import Path
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

load_dotenv()

KB_DIR = Path(__file__).parent / "kb"

# ---- 1. Load and chunk ----
docs = []
for md_path in sorted(KB_DIR.glob("*.md")):
    docs.extend(TextLoader(str(md_path)).load())

splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=50)
chunks = splitter.split_documents(docs)
print(f"Loaded {len(docs)} files; split into {len(chunks)} chunks.\n")

# ---- 2. Embed and store ----
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = FAISS.from_documents(chunks, embeddings)

# ---- 3. Retrieve, augment, generate ----
llm = ChatOpenAI(model="gpt-6-luna", reasoning_effort="none")


def answer_with_rag(question: str) -> None:
    # Retrieve: top-3 most similar chunks
    relevant = vectorstore.similarity_search(question, k=3)

    # Augment: stuff them into the prompt
    context = "\n\n---\n\n".join(d.page_content for d in relevant)
    augmented_prompt = (
        "Use the following reference material to answer the question. "
        "If the reference doesn't cover it, say so plainly.\n\n"
        f"Reference:\n{context}\n\n"
        f"Question: {question}"
    )

    # Generate
    response = llm.invoke(augmented_prompt)

    print(f"Q: {question}")
    print(f"\nRetrieved {len(relevant)} chunks:")
    for i, doc in enumerate(relevant, 1):
        src = Path(doc.metadata["source"]).name
        preview = doc.page_content[:70].replace("\n", " ")
        print(f"  {i}. {src}: {preview}...")
    print(f"\nAnswer:\n{response.content}\n{'=' * 70}\n")


def answer_without_rag(question: str) -> None:
    response = llm.invoke(question)
    print(f"Q: {question}")
    print(f"\nAnswer (no RAG):\n{response.content}\n{'=' * 70}\n")


if __name__ == "__main__":
    answer_with_rag(
        "What does it mean when a BGP session is in the 'active' state?"
    )
    answer_with_rag(
        "Which routers in the lab topology should have iBGP sessions?"
    )
    answer_with_rag(
        "What's the difference between TCP and UDP?"  # Not in the KB
    )

    print("\n### Without RAG, for comparison ###\n")
    answer_without_rag(
        "Which routers in the lab topology should have iBGP sessions?"
    )
