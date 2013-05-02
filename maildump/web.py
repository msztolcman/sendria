from flask import Flask, render_template
from logbook import Logger


app = Flask(__name__)
app._logger = Logger(__name__)


@app.route('/')
def home():
    return render_template('index.html')