# flask-scan

Lists the routes in a Flask codebase and says how much work each one is to move to FastAPI.

Independent demo, not affiliated with CI&T. I built it after applying for a Senior Backend Engineer (Python) role whose description mentions a Flask to FastAPI migration. The only code it reads is the Python you point it at, and it never runs that code.

## What it does

`flask-scan` parses Python files with the standard `ast` module and finds routes declared with `@app.route`, `@bp.get`, `@bp.post` and so on, including blueprint `url_prefix` values. For each route it reports:

- the methods and the path, rewritten in FastAPI syntax (`/runs/<int:run_id>` becomes `/runs/{run_id}`, with `run_id: int`);
- which Flask features the function body uses (`request`, `g`, `session`, `abort`, `render_template`, ...);
- an effort label: `easy` (a plain return value), `review` (the request or error handling changes shape), or `manual` (`g`, `session`, templates, `current_app` and similar need a design decision);
- hints, such as "declare a Pydantic model instead of `request.get_json()`".

It also lists app-level hooks (`before_request`, `errorhandler`, ...) because they have no route-level equivalent in FastAPI.

With `--format stubs` it prints a FastAPI `APIRouter` skeleton with typed path parameters and `NotImplementedError` bodies.

## Run it

Python 3.9 or newer, no dependencies.

```
pip install -e .
flask-scan examples/sample_app.py
flask-scan examples/sample_app.py --format json
flask-scan examples/sample_app.py --format stubs
```

Without installing: `PYTHONPATH=src python3 -m flask_scan.cli examples/sample_app.py`.

`examples/sample_app.py` is an invented app. Output for it:

```
7 routes: 2 easy, 3 review, 2 manual

- @before_request load_user: port as middleware, a dependency, or an exception handler
```

The two `manual` routes read `g.user` (set by a `before_request` hook) and call `render_template`. Those are the ones a plain search-and-replace would get wrong.

## Tests

```
pip install pytest
python -m pytest -q
```

The 13 tests run offline and finish in well under a second. CI runs them on Python 3.10 and 3.12.

## What was tested

- Path conversion: typed converters, plain names, the `path` converter.
- Blueprint prefixes, the `.get/.post` shortcuts, default `GET`, method sorting.
- Decorators on objects that are not Flask apps or blueprints are ignored.
- Async views are found.
- Effort labels and hints on the invented sample app.
- A file with a syntax error is skipped without stopping the scan.
- The generated stubs compile as Python.
- The CLI's JSON output.

## What was not tested

- No real-world Flask project. The only input is the sample app in this repo, so the effort labels are my own judgment, not measured against an actual migration.
- Blueprints created in one file and registered with a prefix in another (`register_blueprint(bp, url_prefix=...)`) are not resolved. The route is reported with the prefix from `Blueprint(...)` only.
- Class-based views, `add_url_rule`, Flask-RESTful and Flask-Smorest resources are not detected.
- Routes whose path is not a string literal are skipped.
- The generated stubs are not run with FastAPI, and the tool does not infer request or response models.
- Only the Python versions in the CI matrix were tried (3.10 and 3.12, plus 3.15 locally).
