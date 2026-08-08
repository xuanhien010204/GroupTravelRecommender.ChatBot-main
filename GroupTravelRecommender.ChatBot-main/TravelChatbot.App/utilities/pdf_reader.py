
import io
from PyPDF2 import PdfReader
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using PyPDF2."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n".join(pages)
    except Exception as e:
        raise


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> List[str]:
    """Chunk text into pieces of chunk_size characters with overlap using LangChain's RecursiveCharacterTextSplitter."""
    if not text:
        return []
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len,
        is_separator_regex=False
    )
    
    return text_splitter.split_text(text)

