from flask import Flask, render_template, request, redirect, url_for
from task_manager import TaskManager, Task
from calendar_auth import authenticate_google_calendar
from scheduler import schedule_task
from datetime import datetime

app = Flask(__name__)
task_manager = TaskManager()
calendar_service = authenticate_google_calendar()

@app.route('/')
def index():
    return render_template('index.html', tasks=task_manager.get_sorted_tasks())

@app.route("/add_task", methods=["POST"])
def add_task():
    title = request.form["title"]
    description = request.form.get("description", "")
    due_date = request.form["due_date"]
    estimated_time = int(request.form["estimated_minutes"])
    priority = int(request.form["priority"])

    due_dt = datetime.fromisoformat(due_date)
    task = Task(title, description, due_dt, estimated_time, priority)
    task_manager.add_task(task)

    return redirect(url_for("index"))

@app.route("/schedule", methods=["POST"])
def schedule():
    avoid_days = request.form.getlist("avoid_days")
    scheduled = schedule_task(calendar_service, task_manager, avoid_days)
    return render_template("scheduled.html", scheduled=scheduled)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
