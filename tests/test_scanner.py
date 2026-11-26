from pathlib import Path

from flask_scan import scan_hooks, scan_source, scan_path, to_markdown, to_stubs
from flask_scan.cli import main
from flask_scan.scanner import convert_path

SAMPLE = Path(__file__).parent.parent / "examples" / "sample_app.py"


def test_convert_path_typed_and_plain():
    assert convert_path("/u/<int:id>/x/<name>") == ("/u/{id}/x/{name}", {"id": "int", "name": "str"})


def test_convert_path_path_converter():
    assert convert_path("/f/<path:p>")[0] == "/f/{p:path}"


def test_blueprint_prefix_and_shortcut():
    src = "from flask import Blueprint\nb = Blueprint('b', __name__, url_prefix='/api')\n@b.get('/x')\ndef x(): return 1\n"
    (r,) = scan_source(src)
    assert r.fastapi_path == "/api/x" and r.methods == ["GET"] and r.effort == "easy"


def test_route_methods_sorted_and_default_get():
    src = "from flask import Flask\napp = Flask(__name__)\n@app.route('/a', methods=['POST','get'])\ndef a(): pass\n@app.route('/b')\ndef b(): pass\n"
    a, b = scan_source(src)
    assert a.methods == ["GET", "POST"] and b.methods == ["GET"]


def test_ignores_decorators_from_non_flask_objects():
    src = "import other\nr = other.Router()\n@r.get('/x')\ndef x(): pass\n"
    assert scan_source(src) == []


def test_async_view_is_found():
    src = "from flask import Flask\napp = Flask(__name__)\n@app.get('/a')\nasync def a(): pass\n"
    (r,) = scan_source(src)
    assert "already async" in r.hints


def test_sample_effort_levels():
    by = {r.function: r for r in scan_path(SAMPLE)}
    assert len(by) == 7
    assert by["health"].effort == "easy"            # jsonify only
    assert by["create_run"].effort == "review"      # request.get_json + abort
    assert by["owner"].effort == "manual"           # g
    assert by["files"].effort == "manual"           # render_template
    assert by["run_detail"].methods == ["DELETE", "GET"]
    assert by["run_detail"].fastapi_path == "/api/v1/runs/{run_id}"
    assert by["run_detail"].params == {"run_id": "int"}


def test_sample_hints_mention_pydantic_and_uploadfile():
    by = {r.function: r for r in scan_path(SAMPLE)}
    assert any("Pydantic" in h for h in by["create_run"].hints)
    assert any("UploadFile" in h for h in by["upload"].hints)


def test_syntax_error_file_is_skipped(tmp_path):
    (tmp_path / "bad.py").write_text("def (:\n")
    (tmp_path / "ok.py").write_text("from flask import Flask\napp=Flask(__name__)\n@app.get('/')\ndef i(): pass\n")
    assert [r.function for r in scan_path(tmp_path)] == ["i"]


def test_markdown_and_stubs_compile():
    routes = scan_path(SAMPLE)
    md = to_markdown(routes)
    assert "7 routes: 2 easy, 3 review, 2 manual" in md and "| manual |" in md
    stubs = to_stubs(routes)
    compile(stubs, "stubs.py", "exec")  # generated skeleton must be valid Python
    assert '@router.delete("/api/v1/runs/{run_id}")' in stubs


def test_cli_json(capsys):
    assert main([str(SAMPLE), "--format", "json"]) == 0
    assert '"function": "owner"' in capsys.readouterr().out


def test_hooks_found():
    hooks = scan_hooks(SAMPLE)
    assert [(h.kind, h.function) for h in hooks] == [("before_request", "load_user")]


def test_markdown_lists_hooks():
    md = to_markdown(scan_path(SAMPLE), scan_hooks(SAMPLE))
    assert "@before_request" in md and "load_user" in md
