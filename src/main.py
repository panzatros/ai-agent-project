from datetime import datetime
from agents.simple_agent import SimpleAgent
from typing import Dict, Callable, List
from flask import Flask, request, jsonify

app = Flask(__name__)

from routes.routes import routes  # Ensure routes are registered

app.register_blueprint(routes)


if __name__ == "__main__":
    print("Starting Flask server with Simple AI Agent...")
    app.run(host='0.0.0.0', port=5000, debug=True)