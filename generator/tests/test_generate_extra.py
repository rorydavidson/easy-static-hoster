import os
import time
import pytest
from watchdog.events import FileModifiedEvent, FileMovedEvent
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

def _handler_with_spy(tmp_path, monkeypatch):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    handler = generate.ContentHandler(content_dir, "Site")
    handler.debounce_seconds = 0.05
    called = []
    monkeypatch.setattr(generate, "render_index", lambda *args: called.append(1))
    return content_dir, handler, called


def test_content_handler_ignores_own_output(tmp_path, monkeypatch):
    content_dir, handler, called = _handler_with_spy(tmp_path, monkeypatch)
    handler.on_any_event(FileModifiedEvent(str(content_dir / "index.html")))
    handler.on_any_event(FileMovedEvent(str(content_dir / ".index.html.tmp"),
                                        str(content_dir / "index.html")))
    time.sleep(0.2)
    assert not called


def test_content_handler_burst_rebuilds_once_after_last_event(tmp_path, monkeypatch):
    content_dir, handler, called = _handler_with_spy(tmp_path, monkeypatch)
    event = FileModifiedEvent(str(content_dir / "cat" / "other.html"))
    handler.on_any_event(event)
    handler.on_any_event(event)
    # Nothing yet: the rebuild waits for the burst to settle
    assert not called
    time.sleep(0.2)
    assert len(called) == 1


def test_content_handler_does_not_drop_later_changes(tmp_path, monkeypatch):
    """A change soon after a rebuild must still trigger another rebuild."""
    content_dir, handler, called = _handler_with_spy(tmp_path, monkeypatch)
    event = FileModifiedEvent(str(content_dir / "cat" / "a.html"))
    handler.on_any_event(event)
    time.sleep(0.2)
    handler.on_any_event(event)
    time.sleep(0.2)
    assert len(called) == 2


def test_content_handler_reacts_to_pages_named_index(tmp_path, monkeypatch):
    content_dir, handler, called = _handler_with_spy(tmp_path, monkeypatch)
    handler.on_any_event(FileModifiedEvent(str(content_dir / "cat" / "index.html")))
    time.sleep(0.2)
    assert len(called) == 1


def test_render_index_leaves_no_temp_file(tmp_path):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    generate.render_index(content_dir, "T")
    assert (content_dir / "index.html").exists()
    assert not (content_dir / ".index.html.tmp").exists()


# ── HEADER_COLOR tests ──────────────────────────────────────────────────────

def _make_content_dir(tmp_path):
    """Create a minimal content dir with one category and one page."""
    d = tmp_path / "content"
    d.mkdir()
    cat = d / "cat"
    cat.mkdir()
    (cat / "page.html").write_text("<title>P</title>")
    return d


def test_header_color_default(tmp_path, monkeypatch):
    """When HEADER_COLOR is unset the context should return an empty string."""
    monkeypatch.delenv("HEADER_COLOR", raising=False)
    ctx = generate.build_context(_make_content_dir(tmp_path), "T")
    assert ctx["header_color"] == ""


def test_header_color_custom(tmp_path, monkeypatch):
    """When HEADER_COLOR is set the value passes through to the context."""
    monkeypatch.setenv("HEADER_COLOR", "#2e7d32")
    ctx = generate.build_context(_make_content_dir(tmp_path), "T")
    assert ctx["header_color"] == "#2e7d32"


def test_header_color_whitespace_stripped(tmp_path, monkeypatch):
    """Whitespace around HEADER_COLOR should be stripped."""
    monkeypatch.setenv("HEADER_COLOR", "  darkslateblue  ")
    ctx = generate.build_context(_make_content_dir(tmp_path), "T")
    assert ctx["header_color"] == "darkslateblue"


def test_header_color_in_rendered_html(tmp_path, monkeypatch):
    """The custom colour should appear as --header-bg in the rendered index."""
    monkeypatch.setenv("HEADER_COLOR", "#ff5500")
    monkeypatch.delenv("BASIC_AUTH", raising=False)
    monkeypatch.delenv("OIDC_ISSUER_URL", raising=False)
    content_dir = _make_content_dir(tmp_path)
    generate.render_index(content_dir, "T")
    html = (content_dir / "index.html").read_text()
    assert "--header-bg:   #ff5500;" in html or "--header-bg: #ff5500;" in html


def test_header_color_default_in_rendered_html(tmp_path, monkeypatch):
    """When no colour is set the default navy should appear in the rendered index."""
    monkeypatch.delenv("HEADER_COLOR", raising=False)
    monkeypatch.delenv("BASIC_AUTH", raising=False)
    monkeypatch.delenv("OIDC_ISSUER_URL", raising=False)
    content_dir = _make_content_dir(tmp_path)
    generate.render_index(content_dir, "T")
    html = (content_dir / "index.html").read_text()
    assert "#16162a" in html


# ── OPEN_NEW_TAB tests ──────────────────────────────────────────────────────

def test_open_new_tab_default(tmp_path, monkeypatch):
    """Default (unset) should mean open_new_tab is True."""
    monkeypatch.delenv("OPEN_NEW_TAB", raising=False)
    ctx = generate.build_context(_make_content_dir(tmp_path), "T")
    assert ctx["open_new_tab"] is True


def test_open_new_tab_true(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_NEW_TAB", "true")
    ctx = generate.build_context(_make_content_dir(tmp_path), "T")
    assert ctx["open_new_tab"] is True


def test_open_new_tab_false(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_NEW_TAB", "false")
    ctx = generate.build_context(_make_content_dir(tmp_path), "T")
    assert ctx["open_new_tab"] is False


def test_open_new_tab_false_case_insensitive(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_NEW_TAB", "False")
    ctx = generate.build_context(_make_content_dir(tmp_path), "T")
    assert ctx["open_new_tab"] is False


def test_open_new_tab_false_whitespace(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_NEW_TAB", "  false  ")
    ctx = generate.build_context(_make_content_dir(tmp_path), "T")
    assert ctx["open_new_tab"] is False


def test_open_new_tab_rendered_with_target(tmp_path, monkeypatch):
    """When open_new_tab is true, links should have target='_blank'."""
    monkeypatch.delenv("OPEN_NEW_TAB", raising=False)
    monkeypatch.delenv("BASIC_AUTH", raising=False)
    monkeypatch.delenv("OIDC_ISSUER_URL", raising=False)
    content_dir = _make_content_dir(tmp_path)
    generate.render_index(content_dir, "T")
    html = (content_dir / "index.html").read_text()
    assert 'target="_blank"' in html


def test_open_new_tab_rendered_without_target(tmp_path, monkeypatch):
    """When OPEN_NEW_TAB=false, links should NOT have target='_blank'."""
    monkeypatch.setenv("OPEN_NEW_TAB", "false")
    monkeypatch.delenv("BASIC_AUTH", raising=False)
    monkeypatch.delenv("OIDC_ISSUER_URL", raising=False)
    content_dir = _make_content_dir(tmp_path)
    generate.render_index(content_dir, "T")
    html = (content_dir / "index.html").read_text()
    assert 'target="_blank"' not in html


# ── Logo & favicon tests ────────────────────────────────────────────────────

def test_logo_svg_in_rendered_html(tmp_path, monkeypatch):
    """The inline SVG logo should appear in the rendered index."""
    monkeypatch.delenv("BASIC_AUTH", raising=False)
    monkeypatch.delenv("OIDC_ISSUER_URL", raising=False)
    content_dir = _make_content_dir(tmp_path)
    generate.render_index(content_dir, "T")
    html = (content_dir / "index.html").read_text()
    assert 'class="logo"' in html
    assert "<svg" in html


def test_favicon_link_in_rendered_html(tmp_path, monkeypatch):
    """The favicon link tag should appear in the rendered index head."""
    monkeypatch.delenv("BASIC_AUTH", raising=False)
    monkeypatch.delenv("OIDC_ISSUER_URL", raising=False)
    content_dir = _make_content_dir(tmp_path)
    generate.render_index(content_dir, "T")
    html = (content_dir / "index.html").read_text()
    assert 'rel="icon"' in html
    assert "/favicon.ico" in html


# ── Link safety ─────────────────────────────────────────────────────────────

def test_page_links_are_root_relative(tmp_path, monkeypatch):
    """A folder named like a URL scheme must not become a javascript: link."""
    monkeypatch.delenv("BASIC_AUTH", raising=False)
    monkeypatch.delenv("OIDC_ISSUER_URL", raising=False)
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    evil = content_dir / "javascript:alert(1)"
    evil.mkdir()
    (evil / "page.html").write_text("<title>P</title>")
    generate.render_index(content_dir, "T")
    html = (content_dir / "index.html").read_text()
    assert 'href="/javascript:alert(1)/page.html"' in html
    assert 'href="javascript:' not in html
