import json
import os
import pytest
from pathlib import Path

# Need to import app after setting environment variables if relying on them
import shortlinks_server
from shortlinks_server import app

@pytest.fixture
def client(tmp_path):
    # Set up temporary content directory for tests
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    
    # Configure app for testing
    app.config['TESTING'] = True
    shortlinks_server.CONTENT_DIR = content_dir
    shortlinks_server._UPLOAD_ENABLED = True
    shortlinks_server._OIDC_MODE = False
    
    # Set basic auth credentials for testing uploads
    os.environ["BASIC_AUTH"] = "admin:secret"
    
    with app.test_client() as client:
        yield client

def test_redirect_shortlink_not_found(client):
    response = client.get('/s/nonexistent')
    assert response.status_code == 404
    assert b"Short link 'nonexistent' not found" in response.data

def test_redirect_shortlink_xss_protection(client):
    # Test the XSS fix we implemented earlier
    response = client.get('/s/<script>alert(1)</script>')
    assert response.status_code == 404
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in response.data
    assert b"<script>" not in response.data

def test_handle_shortlink_create_and_redirect(client, tmp_path):
    # Create shortlinks.json setup
    content_dir = tmp_path / "content"
    
    # Create shortlink
    response = client.post('/api/shortlinks', 
                          json={"path": "folder/page.html", "code": "my-page"})
    assert response.status_code == 200
    
    # Verify the json was saved
    links_file = content_dir / "shortlinks.json"
    assert links_file.exists()
    links = json.loads(links_file.read_text())
    assert links["my-page"] == "folder/page.html"
    
    # Verify redirect works
    redirect_response = client.get('/s/my-page')
    assert redirect_response.status_code == 302
    assert redirect_response.headers["Location"] == "/folder/page.html"

def test_handle_shortlink_invalid_code(client):
    response = client.post('/api/shortlinks', 
                          json={"path": "page.html", "code": "INVALID CODE!"})
    assert response.status_code == 400
    assert b"must be lowercase letters" in response.data

def test_handle_shortlink_conflict(client):
    # Create first shortlink
    client.post('/api/shortlinks', json={"path": "page1.html", "code": "shared"})
    
    # Try creating second shortlink with same code
    response = client.post('/api/shortlinks', 
                          json={"path": "page2.html", "code": "shared"})
    assert response.status_code == 409
    assert b"already used" in response.data

def test_handle_mkdir(client, tmp_path):
    import base64
    auth_header = "Basic " + base64.b64encode(b"admin:secret").decode("utf-8")
    
    # Create directory
    response = client.post('/api/mkdir', headers={
        "Authorization": auth_header,
        "X-Folder": "new-folder"
    })
    
    assert response.status_code == 200
    assert (tmp_path / "content" / "new-folder").exists()
    assert (tmp_path / "content" / "new-folder").is_dir()

def test_handle_mkdir_unauthorized(client):
    response = client.post('/api/mkdir', headers={
        "X-Folder": "new-folder"
    })
    assert response.status_code == 401

def test_handle_mkdir_path_traversal(client):
    import base64
    auth_header = "Basic " + base64.b64encode(b"admin:secret").decode("utf-8")
    
    response = client.post('/api/mkdir', headers={
        "Authorization": auth_header,
        "X-Folder": "../hacked"
    })
    assert response.status_code == 400
    assert b"invalid category name" in response.data

def test_handle_upload(client, tmp_path):
    import base64
    auth_header = "Basic " + base64.b64encode(b"admin:secret").decode("utf-8")
    
    # Setup target directory
    content_dir = tmp_path / "content"
    target_dir = content_dir / "my-folder"
    target_dir.mkdir()
    
    response = client.post('/api/upload', 
                          data=b"<html>Hello</html>",
                          headers={
                              "Authorization": auth_header,
                              "X-Folder": "my-folder",
                              "X-Filename": "test.html"
                          })
    
    assert response.status_code == 200
    assert (target_dir / "test.html").exists()
    assert (target_dir / "test.html").read_bytes() == b"<html>Hello</html>"

def test_handle_upload_invalid_extension(client, tmp_path):
    import base64
    auth_header = "Basic " + base64.b64encode(b"admin:secret").decode("utf-8")
    content_dir = tmp_path / "content"
    (content_dir / "my-folder").mkdir()
    
    response = client.post('/api/upload', 
                          data=b"print('hack')",
                          headers={
                              "Authorization": auth_header,
                              "X-Folder": "my-folder",
                              "X-Filename": "script.py"
                          })
    
    assert response.status_code == 400
    assert b"only HTML and image files are allowed" in response.data
