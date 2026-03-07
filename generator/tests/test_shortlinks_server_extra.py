import pytest
import os
import base64
from pathlib import Path
import shortlinks_server
from shortlinks_server import app

@pytest.fixture
def client(tmp_path):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    app.config['TESTING'] = True
    shortlinks_server.CONTENT_DIR = content_dir
    shortlinks_server._UPLOAD_ENABLED = True
    shortlinks_server._OIDC_MODE = False
    os.environ["BASIC_AUTH"] = "admin:secret"
    with app.test_client() as client:
        yield client

def test_load_shortlinks_parse_error(client, tmp_path):
    content_dir = tmp_path / "content"
    links_file = content_dir / "shortlinks.json"
    links_file.write_text("{invalid json]")
    response = client.get('/s/nonexistent')
    assert response.status_code == 404

def test_oidc_auth(client, monkeypatch):
    monkeypatch.setattr(shortlinks_server, '_OIDC_MODE', True)
    response = client.post('/api/mkdir', headers={"X-Folder": "new", "X-Forwarded-User": "testuser"})
    assert response.status_code == 200

def test_basic_auth_invalid_base64(client):
    response = client.post('/api/mkdir', headers={"Authorization": "Basic INVALID_BASE64!@#", "X-Folder": "new"})
    assert response.status_code == 401

def test_handle_shortlink_invalid_json(client):
    response = client.post('/api/shortlinks', data="not-json", content_type="application/json")
    assert response.status_code == 400
    assert b"invalid JSON" in response.data

def test_handle_shortlink_missing_path(client):
    response = client.post('/api/shortlinks', json={"code": "mycode"})
    assert response.status_code == 400
    assert b"path is required" in response.data

def test_handle_shortlink_save_error(client, monkeypatch):
    def mock_save(*args, **kwargs):
        raise Exception("Disk full")
    monkeypatch.setattr(shortlinks_server, 'save_shortlinks', mock_save)
    response = client.post('/api/shortlinks', json={"path": "page.html", "code": "mycode"})
    assert response.status_code == 500
    assert b"failed to save" in response.data

def get_auth():
    return "Basic " + base64.b64encode(b"admin:secret").decode("utf-8")

def test_handle_upload_disabled(client, monkeypatch):
    monkeypatch.setattr(shortlinks_server, '_UPLOAD_ENABLED', False)
    response = client.post('/api/upload', headers={"Authorization": get_auth()})
    assert response.status_code == 403

def test_handle_upload_invalid_credentials(client):
    response = client.post('/api/upload', headers={"Authorization": "Basic " + base64.b64encode(b"admin:wrong").decode("utf-8")})
    assert response.status_code == 401

def test_handle_upload_invalid_folder_name(client):
    response = client.post('/api/upload', headers={"Authorization": get_auth(), "X-Folder": "../hacked"})
    assert response.status_code == 400

def test_handle_upload_folder_not_found(client):
    response = client.post('/api/upload', headers={"Authorization": get_auth(), "X-Folder": "missing"})
    assert response.status_code == 400

def test_handle_upload_invalid_filename(client):
    response = client.post('/api/upload', headers={"Authorization": get_auth(), "X-Folder": "missing", "X-Filename": ".hidden"})
    assert response.status_code == 400

def test_handle_upload_empty_file(client, tmp_path):
    (tmp_path / "content" / "myfolder").mkdir()
    response = client.post('/api/upload', data=b"", headers={"Authorization": get_auth(), "X-Folder": "myfolder", "X-Filename": "test.html"})
    assert response.status_code == 400

def test_handle_upload_file_too_large(client, tmp_path, monkeypatch):
    (tmp_path / "content" / "myfolder").mkdir()
    monkeypatch.setattr(shortlinks_server, 'UPLOAD_MAX_BYTES', 5)
    response = client.post('/api/upload', data=b"123456", headers={"Authorization": get_auth(), "X-Folder": "myfolder", "X-Filename": "test.html"})
    assert response.status_code == 400

def test_handle_upload_write_failed(client, tmp_path, monkeypatch):
    (tmp_path / "content" / "myfolder").mkdir()
    def mock_write(*args, **kwargs):
        raise Exception("Disk full")
    monkeypatch.setattr(Path, 'write_bytes', mock_write)
    response = client.post('/api/upload', data=b"hello", headers={"Authorization": get_auth(), "X-Folder": "myfolder", "X-Filename": "test.html"})
    assert response.status_code == 500

def test_handle_mkdir_disabled(client, monkeypatch):
    monkeypatch.setattr(shortlinks_server, '_UPLOAD_ENABLED', False)
    response = client.post('/api/mkdir', headers={"Authorization": get_auth()})
    assert response.status_code == 403

def test_handle_mkdir_invalid_category_len(client):
    response = client.post('/api/mkdir', headers={"Authorization": get_auth(), "X-Folder": "a"*101})
    assert response.status_code == 400

def test_handle_mkdir_already_exists(client, tmp_path):
    (tmp_path / "content" / "myfolder").mkdir()
    response = client.post('/api/mkdir', headers={"Authorization": get_auth(), "X-Folder": "myfolder"})
    assert response.status_code == 409

def test_handle_mkdir_failed(client, monkeypatch):
    def mock_mkdir(*args, **kwargs):
        raise Exception("Permission denied")
    monkeypatch.setattr(Path, 'mkdir', mock_mkdir)
    response = client.post('/api/mkdir', headers={"Authorization": get_auth(), "X-Folder": "newfolder"})
    assert response.status_code == 500
