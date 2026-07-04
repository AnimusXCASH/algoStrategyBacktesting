import pytz
from datetime import datetime, time, timezone

def is_ny_trading_hours():
    ny_tz = pytz.timezone('America/New_York')
    utc_now = datetime.now(timezone.utc)
    ny_now = utc_now.astimezone(ny_tz)
    start_time = ny_tz.localize(datetime.combine(ny_now.date(), time(7, 00)))
    end_time = ny_tz.localize(datetime.combine(ny_now.date(), time(11, 0)))
    print(f"Current New York Time: {ny_now.strftime('%Y-%m-%d %H:%M:%S')}")
    if start_time <= ny_now <= end_time:
        return True
    return False

