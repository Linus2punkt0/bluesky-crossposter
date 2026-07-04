import  os, sys, json, arrow
from loguru import logger
from collections import Counter
from settings.paths import *
from settings import settings

# Setting up logging
logger.remove()
log_format = "<yellow>{time:YYYY-MM-DD HH:mm:ss}</yellow> <lvl>[{level}]: {message}</lvl> <yellow>({function} {file}:{line})</yellow>"
logger.add(sys.stdout, format=log_format, level=settings.log_level)
logger.add("%s/crossposter_{time:YYMMDD}.log" % log_path,
        level=settings.log_level,
        format=log_format, 
        rotation="00:00", retention="1 week")

# Setting up log summary
counts = Counter()
def count_sink(message):
    counts[message.record["level"].name] += 1

logger.add(count_sink)

def summary():
    logger.debug(f"Run summary: Warnings:{counts["WARNING"]}, Errors:{counts["ERROR"]}")
    status_file = f"{log_path}status.csv"
    status_history = []
    if os.path.isfile(status_file):
        with open(status_file, 'r') as file:
            try:
                status_history = json.loads(file)
            except:
                logger.warning("Unable to read status history.")
    status_history = [
        item for item in status_history
        if arrow.get(item["datetime"]) >= arrow.utcnow().shift(hours = -24)
    ]
    status = {
        "datetime": arrow.utcnow().timestamp(),
        "warnings": counts["WARNING"],
        "errors": counts["ERROR"],
    }
    status_history.append(status)
    with open(status_file, "w") as f:
        json.dump(status_history, f, indent=4)