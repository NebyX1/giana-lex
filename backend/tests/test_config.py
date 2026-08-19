from config import _llm_base_url


def test_ollama_base_url_is_normalized_to_openai_endpoint(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/")
    assert _llm_base_url() == "http://localhost:11434/v1"


def test_explicit_llm_base_url_has_priority(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://provider.example/v1/")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    assert _llm_base_url() == "https://provider.example/v1"
