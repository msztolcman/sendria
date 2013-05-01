from flask import Flask
from logbook import Logger


app = Flask(__name__)
app._logger = Logger(__name__)