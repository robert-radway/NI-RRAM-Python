import datetime

def timestamp(format="%Y_%m_%d_%H_%M_%S"):
    """Return detailed timestamp string"""
    return datetime.datetime.now(datetime.timezone.utc).strftime(format)

def timestamp_date(format="%Y_%m_%d"):
    """Return coarse date timestamp string"""
    return datetime.datetime.now(datetime.timezone.utc).strftime(format)