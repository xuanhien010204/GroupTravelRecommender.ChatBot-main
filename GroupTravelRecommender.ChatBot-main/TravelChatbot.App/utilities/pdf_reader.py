import io
import re
import unicodedata
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter


def extract_pages(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return [{"page": index, "text": unicodedata.normalize("NFC", page.extract_text() or "")}
            for index, page in enumerate(reader.pages, 1)]


def extract_text_from_pdf_bytes(pdf_bytes):
    return "\n".join(page["text"] for page in extract_pages(pdf_bytes))


def chunk_text(text, chunk_size=1800, overlap=200):
    if not 0 <= overlap < chunk_size:
        raise ValueError("Invalid chunk size/overlap")
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return []
    return RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap,
                                         length_function=len).split_text(text)
