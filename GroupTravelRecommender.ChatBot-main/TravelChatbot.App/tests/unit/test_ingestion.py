import io
from types import SimpleNamespace as NS
from unittest.mock import Mock
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from config import Settings
from services.ingestion import document_chunks, ingest


def pdf_fixture():
    """Create a real two-page PDF with test text, not a fake extraction result."""
    writer = PdfWriter()
    for text in ("Fixture page one describes a history discussion.", "Fixture page two describes a food discussion."):
        page = writer.add_blank_page(width=600, height=800)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                 NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


TOUR = {"tourId": "fixture", "place": "Huế", "heritageGuide": "guides/fixture.pdf"}


def test_real_pdf_pages_and_metadata():
    _, _, chunks = document_chunks(TOUR, pdf_fixture(), Settings(demo_mode=True))
    assert [c["metadata"]["page"] for c in chunks] == [1, 2]
    assert all(c["metadata"]["place"] == "hue" for c in chunks)
    assert all("section" not in c["metadata"] for c in chunks)
    assert all(c["metadata"]["source_key"] == "guides/fixture.pdf" for c in chunks)


def test_ingestion_batches_skip_and_manifest():
    settings = Settings(demo_mode=True, embedding_batch_size=2)
    docs, embeddings, vectors = Mock(), Mock(), Mock()
    docs.read.return_value = pdf_fixture()
    embeddings.embed.side_effect = lambda texts: [[1, 0] for _ in texts]
    vectors.fetch.return_value = {}
    report = ingest([TOUR], docs, embeddings, vectors, settings)
    assert report["documents_processed"] == 1 and report["failed"] == 0
    assert report["chunks_created"] == 2 and report["embeddings_generated"] == 2
    assert embeddings.embed.call_count == 1
    marker = vectors.upsert.call_args.args[0][0]
    assert marker["metadata"]["type"] == "ingestion_manifest"
    vectors.fetch.return_value = {marker["id"]: NS(metadata=marker["metadata"])}
    assert ingest([TOUR], docs, embeddings, vectors, settings)["skipped"] == 1


def test_ingestion_failure_never_publishes_manifest():
    docs, embeddings, vectors = Mock(), Mock(), Mock()
    docs.read.return_value = pdf_fixture()
    vectors.fetch.return_value = {}
    embeddings.embed.side_effect = TimeoutError()
    report = ingest([TOUR], docs, embeddings, vectors, Settings(demo_mode=True))
    assert report["failed"] == 1
    vectors.upsert.assert_not_called()
