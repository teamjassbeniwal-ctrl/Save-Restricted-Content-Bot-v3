# Copyright (c) 2026 TeamJB
# Repository: https://github.com/teamjb1/teamjassbeniwal-ctrl
# Licensed under the GNU General Public License v3.0.

import os
from flask import Flask, render_template

app = Flask(__name__)  # Corrected

@app.route("/")
def welcome():
    # Render the welcome page with animated "TeamJB" text
    return render_template("welcome.html")  # Indented properly

if __name__ == "__main__":  # Corrected
    # Default to port 5000 if PORT is not set in the environment
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
