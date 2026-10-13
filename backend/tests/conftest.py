"""Shared pytest fixtures/bootstrap for the PRISM backend test suite.

The application eagerly imports a few heavy, native dependencies at module load
time — notably ``sentence_transformers`` (which pulls in torch) and ``fitz``
(PyMuPDF). The acceptance tests mock the behaviour that uses them
(``get_embeddings``, the chunking worker), so we stub the *imports* here when the
real packages are not installed. This keeps the suite runnable in a lightweight
environment (and in CI) without downloading a multi-GB model.

If the real packages are present, they are used unchanged.
"""
import sys
import types


def _install_sentence_transformers_stub():
    try:
        import sentence_transformers  # noqa: F401
        return
    except Exception:
        pass

    module = types.ModuleType("sentence_transformers")

    class _StubModel:
        def __init__(self, *args, **kwargs):
            pass

        def encode(self, texts, *args, **kwargs):
            import numpy as np

            if isinstance(texts, str):
                texts = [texts]
            # Deterministic, non-zero 384-d vectors (matches all-MiniLM-L6-v2
            # dimensionality) so anything that does reach .tolist() is well-formed.
            return np.full((len(texts), 384), 0.1, dtype="float32")

    module.SentenceTransformer = _StubModel
    sys.modules["sentence_transformers"] = module


def _install_fitz_stub():
    try:
        import fitz  # noqa: F401
        return
    except Exception:
        pass

    module = types.ModuleType("fitz")

    def _open(*args, **kwargs):  # pragma: no cover - only hit if a test opens a PDF
        raise RuntimeError("fitz (PyMuPDF) is stubbed; install it to exercise PDF parsing")

    module.open = _open
    sys.modules["fitz"] = module


_install_sentence_transformers_stub()
_install_fitz_stub()
