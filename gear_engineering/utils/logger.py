import datetime

def log(subsystem: str, message: str):
    """
    Standardizes subsystem diagnostic traces across the pipeline.
    """
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{subsystem.upper()}] {message}")
