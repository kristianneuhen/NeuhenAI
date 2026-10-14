from __future__ import annotations

from flask import Flask, jsonify, render_template

app = Flask(__name__)

# Deliberately in-memory for this first container exercise. It proves that the
# browser talks to the Python service; it resets whenever the container restarts.
click_count = 0


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/hello")
def hello():
    global click_count
    click_count += 1
    return jsonify(
        {
            "message": "Hello from the Python container!",
            "click_count": click_count,
        }
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
