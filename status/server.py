from flask import Flask
from pathlib import Path

app = Flask(__name__)

@app.route("/")
def logs():
    path = Path("status.json")
    if not path.exists():
        return "No logs yet."

    return f"<html>{path.read_text()}</html>"

app.run(host="0.0.0.0", port=8080)