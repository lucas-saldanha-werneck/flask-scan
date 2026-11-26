"""EXAMPLE ONLY: an invented Flask app used to demo and test flask-scan. Not real code from anyone."""
from flask import Flask, Blueprint, request, jsonify, abort, g, session, render_template

app = Flask(__name__)
api = Blueprint("api", __name__, url_prefix="/api/v1")


@app.before_request
def load_user():
    g.user = session.get("user")


@app.route("/health")
def health():
    return jsonify(status="ok")


@api.get("/runs")
def list_runs():
    status = request.args.get("status")
    return jsonify(runs=[], status=status)


@api.route("/runs", methods=["POST"])
def create_run():
    payload = request.get_json()
    if not payload:
        abort(400)
    return jsonify(payload), 201


@api.route("/runs/<int:run_id>", methods=["GET", "DELETE"])
def run_detail(run_id):
    return jsonify(id=run_id)


@api.post("/runs/<int:run_id>/upload")
def upload(run_id):
    f = request.files["file"]
    return jsonify(name=f.filename)


@api.get("/runs/<int:run_id>/owner")
def owner(run_id):
    return jsonify(user=g.user)


@app.route("/files/<path:name>")
def files(name):
    return render_template("file.html", name=name)


app.register_blueprint(api)
