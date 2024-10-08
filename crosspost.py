import traceback, sys
from loguru import logger
from settings.auth import *
from settings.paths import *
from local.functions import cleanup, post_cache_read, post_cache_write, get_post_time_limit, check_rate_limit
from local.db import db_read, db_backup, save_db
from input.bluesky import get_posts
from output.post import post
from settings import settings

def select_single(posts):
    id = list(posts)[-1]
    post = posts[id]
    posts = {}
    posts[id] = post
    return posts

def run():
    logger.add("%s/{time:YYMMDD}.log" % log_path,
        format="{time:YYYY-MM-DD HH:mm:ss} [{level}]: {message} ({function} {file}:{line})", 
        rotation="00:00", retention="1 week", level=settings.log_level)
    if check_rate_limit():
        exit()
    database = db_read()
    post_cache = post_cache_read()
    timelimit = get_post_time_limit(post_cache)
    posts = get_posts(timelimit)
    updates, database, post_cache = post(posts, database, post_cache)
    post_cache_write(post_cache)
    if updates:
        save_db(database)
        cleanup()
    db_backup()
    if not posts:
        logger.info("No new posts found.")

# Here the whole thing is run
if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        logger.error(traceback.format_exc())
