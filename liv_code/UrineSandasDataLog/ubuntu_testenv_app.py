from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello():
    return "Flask is running on Python 3.12!"
