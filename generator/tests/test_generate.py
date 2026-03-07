import os
from pathlib import Path
import pytest
from generate import humanize, extract_title, build_context

def test_humanize():
    assert humanize("my-report_2025") == "My Report 2025"
    assert humanize("some_file-name") == "Some File Name"
    assert humanize("word") == "Word"
    assert humanize("") == ""

def test_extract_title(tmp_path):
    test_file = tmp_path / "test.html"
    
    # Test valid title extraction
    test_file.write_text("<html><head><title>My Test Title</title></head><body></body></html>", encoding="utf-8")
    assert extract_title(test_file) == "My Test Title"
    
    # Test title with extra whitespace
    test_file.write_text("<html><head><title>  My Spaced Title  </title></head><body></body></html>", encoding="utf-8")
    assert extract_title(test_file) == "My Spaced Title"
    
    # Test missing title fallback returns None
    test_file.write_text("<html><head></head><body>No title here</body></html>", encoding="utf-8")
    assert extract_title(test_file) is None
    
    # Test unparseable file
    test_file.write_bytes(b"\x80\x81\x82")  # Invalid utf-8
    assert extract_title(test_file) is None

def test_build_context(tmp_path):
    # Setup mock content structure
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    
    # Create shortlinks
    shortlinks = '{"test-link": "cat1/page1.html"}'
    (content_dir / "shortlinks.json").write_text(shortlinks)
    
    # Category 1: Standard pages and meta.json
    cat1 = content_dir / "cat1"
    cat1.mkdir()
    (cat1 / "meta.json").write_text('{"title": "Category One", "order": 1}')
    (cat1 / "page1.html").write_text("<title>Page One</title>")
    (cat1 / "page2.html").write_text("No Title Here")
    
    # Category 2: Hidden category
    cat2 = content_dir / "cat2"
    cat2.mkdir()
    (cat2 / "meta.json").write_text('{"title": "Hidden Cat", "hidden": true}')
    (cat2 / "secret.html").write_text("<title>Secret</title>")
    
    # Category 3: Fallback humanize title and example page
    cat3 = content_dir / "cat3"
    cat3.mkdir()
    (cat3 / "my_report-2023.html").write_text("No Title")
    (cat3 / "_example.html").write_text("<title>Example</title>") # Should be ignored because real page exists
    
    # Category 4: Only example page
    cat4 = content_dir / "cat4"
    cat4.mkdir()
    (cat4 / "_example.html").write_text("<title>Example Only</title>") # Should be shown because no real pages

    os.environ["BASIC_AUTH"] = "admin:pass"

    context = build_context(content_dir, "Test Site")
    
    assert context["site_title"] == "Test Site"
    assert context["total_pages"] == 4  # 2 in cat1 + 1 in cat3 + 1 example in cat4
    assert context["upload_enabled"] is True
    assert context["auth_mode"] == "basic"
    
    cats = context["categories"]
    assert len(cats) == 3  # cat1, cat3, cat4 (cat2 is hidden)
    
    # Verify cat1
    assert cats[0]["title"] == "Category One"
    assert cats[0]["order"] == 1
    assert len(cats[0]["pages"]) == 2
    assert cats[0]["pages"][0]["title"] == "Page One"
    assert cats[0]["pages"][0]["shortlink"] == "test-link"
    assert cats[0]["pages"][1]["title"] == "Page2"  # Humanized from filename 'page2'
    assert cats[0]["pages"][1]["shortlink"] is None

    # Verify cat3
    assert cats[1]["title"] == "Cat3" # humanized folder name
    assert len(cats[1]["pages"]) == 1
    assert cats[1]["pages"][0]["title"] == "My Report 2023" # Humanized
    
    # Verify cat4 (Example page shown because it's the only one)
    assert cats[2]["title"] == "Cat4"
    assert len(cats[2]["pages"]) == 1
    assert cats[2]["pages"][0]["title"] == "Example Only"
