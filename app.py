pip install flask mysql-connector-python

from flask import Flask, render_template, request, redirect
import mysql.connector
app = Flask(__name__)
def get_db():
return mysql.connector.connect(
host='localhost', user='root',
password='YOUR_PASSWORD', database='job_tracker'
)
@app.route('/')
def dashboard():
conn = get_db()
cursor = conn.cursor(dictionary=True)
cursor.execute('SELECT COUNT(*) as count FROM applications')
stats = cursor.fetchone()
conn.close()
return render_template('dashboard.html', stats=stats)
if __name__ == '__main__':
app.run(debug=True)