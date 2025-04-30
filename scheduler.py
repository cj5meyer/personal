import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from googleapiclient.errors import HttpError

EASTERN = ZoneInfo("America/New_York")

# Set up logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

def priority_to_offset_days(priority):
    if priority >= 10:
        return 0
    elif priority >= 8:
        return 0.5
    elif priority >= 6:
        return 1
    elif priority >= 4:
        return 1.5
    elif priority >= 2:
        return 2
    else:
        return 3

def calculate_total_time(minutes):
    hours = minutes / 60
    breaks = int(hours) * 15
    return minutes + breaks

def check_event_conflict(calendar_service, schedule_time, task_duration_minutes):
    schedule_time_utc = schedule_time.astimezone(ZoneInfo("UTC"))
    end_time_utc = schedule_time_utc + timedelta(minutes=task_duration_minutes)

    events_result = calendar_service.events().list(
        calendarId='primary',
        timeMin=schedule_time_utc.isoformat(),
        timeMax=end_time_utc.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    return bool(events)

def schedule_event(calendar_service, task, schedule_time, minutes):
    event = {
        'summary': task.title,
        'description': getattr(task, 'description', ''),
        'start': {
            'dateTime': schedule_time.isoformat(),
            'timeZone': 'America/New_York',
        },
        'end': {
            'dateTime': (schedule_time + timedelta(minutes=minutes)).isoformat(),
            'timeZone': 'America/New_York',
        },
        'colorId': '4',
    }

    try:
        created_event = calendar_service.events().insert(calendarId='primary', body=event).execute()
        logging.debug(f"Event created: {created_event.get('htmlLink')}")
        return created_event
    except Exception as e:
        logging.error(f"An error occurred while scheduling the event: {e}")
        return None

def split_task_blocks(task, current_time, due_date):
    total_time = calculate_total_time(task.estimated_time)
    days_remaining = (due_date.date() - current_time.date()).days + 1
    blocks = []

    if task.priority >= 10:
        blocks = [(current_time.date(), total_time)]
    elif task.priority >= 8:
        if days_remaining <= 1:
            blocks = [(current_time.date(), total_time)]
        else:
            half = max(30, total_time // 2)
            remaining = total_time - half
            blocks = [
                (current_time.date(), half),
                ((current_time + timedelta(days=1)).date(), remaining)
            ]
    elif task.priority >= 4:
        parts = min(4, days_remaining)
        per_part = max(30, total_time // parts)
        for i in range(parts):
            date = (due_date - timedelta(days=(parts - 1 - i))).date()
            blocks.append((date, per_part))
    else:
        parts = min(5, days_remaining)
        per_part = max(30, total_time // parts)
        for i in range(parts):
            date = (due_date - timedelta(days=(parts - 1 - i))).date()
            blocks.append((date, per_part))

    return blocks

def schedule_task(calendar_service, task_manager, avoid_days):
    scheduled_tasks = []
    current_time = datetime.now(tz=EASTERN)

    tasks = sorted(
        task_manager.get_sorted_tasks(),
        key=lambda task: (task.due_date, -task.priority)
    )

    for task in tasks:
        if getattr(task, 'scheduled', False):
            continue

        task_due_date = task.due_date.replace(hour=23, minute=59, second=0, microsecond=0, tzinfo=EASTERN)

        if task.priority >= 10:
            minutes_left = calculate_total_time(task.estimated_time)
            block_num = 1
            current_day = current_time.date()

            while current_day <= task_due_date.date() and minutes_left > 0:
                if current_day.strftime("%A") in avoid_days:
                    current_day += timedelta(days=1)
                    continue

                time_cursor = datetime.combine(current_day, datetime.min.time(), tzinfo=EASTERN).replace(hour=9)
                if current_day == current_time.date():
                    min_cursor = current_time + timedelta(minutes=30)
                    if time_cursor < min_cursor:
                        time_cursor = min_cursor

                while time_cursor.hour < 22 and minutes_left > 0:
                    if check_event_conflict(calendar_service, time_cursor, 30):
                        time_cursor += timedelta(minutes=30)
                        continue

                    chunk = min(60, minutes_left)
                    if chunk < 30:
                        break

                    if not check_event_conflict(calendar_service, time_cursor, chunk):
                        chunk_title = f"{task.title} (Part {block_num})"
                        fake_task = type('Task', (object,), {
                            'title': chunk_title,
                            'description': getattr(task, 'description', ''),
                            'estimated_time': chunk
                        })()
                        event = schedule_event(calendar_service, fake_task, time_cursor, chunk)
                        if event:
                            start_time = datetime.fromisoformat(event['start']['dateTime']).strftime('%Y-%m-%d %H:%M:%S')
                            end_time = datetime.fromisoformat(event['end']['dateTime']).strftime('%Y-%m-%d %H:%M:%S')
                            scheduled_tasks.append((chunk_title, start_time, end_time))
                            logging.info(f"[PRIO 10] Scheduled '{chunk_title}' at {start_time}")
                        minutes_left -= chunk
                        block_num += 1
                        time_cursor += timedelta(minutes=chunk + 15)
                    else:
                        time_cursor += timedelta(minutes=30)

                current_day += timedelta(days=1)

            task.scheduled = True
            continue

        blocks = split_task_blocks(task, current_time, task_due_date)

        for date, minutes in blocks:
            schedule_time = datetime.combine(date, datetime.min.time(), tzinfo=EASTERN).replace(hour=9, minute=0)
            min_start_time = current_time + timedelta(minutes=30)
            schedule_time = max(schedule_time, min_start_time)
            preferred_end = datetime.combine(date, datetime.max.time(), tzinfo=EASTERN)

            while schedule_time <= preferred_end:
                if schedule_time.hour < 7 or schedule_time.hour >= 22:
                    break

                day_name = schedule_time.strftime("%A")
                if day_name in avoid_days:
                    break

                if check_event_conflict(calendar_service, schedule_time, minutes):
                    schedule_time += timedelta(minutes=30)
                    continue

                try:
                    task_with_description = type('Task', (object,), {
                    'title': task.title,
                    'description': getattr(task, 'description', ''),
                    'estimated_time': task.estimated_time
                    })()

                    event = schedule_event(calendar_service, task, schedule_time, minutes)

                    start_time = datetime.fromisoformat(event['start']['dateTime']).strftime('%Y-%m-%d %H:%M:%S')
                    end_time = datetime.fromisoformat(event['end']['dateTime']).strftime('%Y-%m-%d %H:%M:%S')
                    logging.info(f"Task '{task.title}' scheduled from {start_time} to {end_time}.")

                    scheduled_tasks.append((task.title, start_time, end_time))
                    break

                except Exception as e:
                    logging.error(f"Error scheduling task {task.title}: {e}")
                    break

        task.scheduled = True

    return scheduled_tasks
