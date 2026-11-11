# Install dependencies first (in a terminal, not in this file):
#   pip install flask mysql-connector-python python-dotenv

from flask import Flask, render_template

from database import get_dashboard_stats

app = Flask(__name__)


@app.route('/')
def dashboard():
    stats = get_dashboard_stats()
    return render_template('dashboard.html', stats=stats)


if __name__ == '__main__':
    app.run(debug=True)
