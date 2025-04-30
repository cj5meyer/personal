import heapq
from datetime import datetime

class Task:
    def __init__(self, title, description, due_date, estimated_time, priority):
        self.title = title
        self.description = description
        self.due_date = due_date  # datetime object
        self.estimated_time = estimated_time
        self.priority = priority  # smaller = more important

    def __lt__(self, other):
        return self.priority < other.priority

    def __repr__(self):
        return f"{self.title} (Due: {self.due_date}, Priority: {self.priority}, Description: {self.description})"
class TaskManager:
    def __init__(self):
        self.task_heap = []  # This will hold tasks in a priority queue

    def add_task(self, task: Task):
        heapq.heappush(self.task_heap, task)

    def pop_task(self):
        if self.task_heap:
            return heapq.heappop(self.task_heap)
        return None

    def peek_next_task(self):
        return self.task_heap[0] if self.task_heap else None

    def list_tasks(self):
        # Convert heap to a sorted list (by priority and due date)
        return sorted(self.task_heap)

    def is_empty(self):
        return len(self.task_heap) == 0

    def get_sorted_tasks(self):
        # Sort by priority (lowest number = higher priority), then due date
        return sorted(self.task_heap, key=lambda task: (task.priority, task.due_date))

    def get_all_tasks(self):
        # Return the tasks in heap order (not sorted)
        return self.task_heap
