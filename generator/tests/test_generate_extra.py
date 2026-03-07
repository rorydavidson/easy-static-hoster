import pytest
from watchdog.events import FileModifiedEvent
import generate

def test_load_shortlinks_invalid(tmp_path):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "shortlinks.json").write_text("{invalid")
    assert generate.load_shortlinks(content_dir) == {}

def test_build_context_meta_invalid(tmp_path):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    cat1 = content_dir / "cat1"
    cat1.mkdir()
    (cat1 / "meta.json").write_text("{invalid")
    (cat1 / "p.html").write_text("ok")
    context = generate.build_context(content_dir, "Test")
    assert context["categories"][0]["title"] == "Cat1"

def test_content_handler_debounce(tmp_path, monkeypatch):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    handler = generate.ContentHandler(content_dir, "Site")
    
    called = []
    monkeypatch.setattr(generate, "render_index", lambda *args: called.append(1))
    
    event = FileModifiedEvent(str(content_dir / "index.html"))
    handler.on_any_event(event)
    assert not called
    
    event = FileModifiedEvent(str(content_dir / "other.html"))
    handler.on_any_event(event)
    assert len(called) == 1
    
    handler.on_any_event(event)
    assert len(called) == 1
