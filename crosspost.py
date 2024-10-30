import traceback
from settings.auth import *
from settings.paths import *
from local.functions import cleanup, post_cache_read, post_cache_write, get_post_time_limit, check_rate_limit, logger
from local.db import db_read, db_backup, save_db
from input.bluesky import get_posts
from output.post import post, delete

def run():
    if check_rate_limit():
        exit()
    database = db_read()
    post_cache = post_cache_read()
    # Putting all of the recently posted posts in a list and removing them as they are found in the timeline.
    # Any posts not found in the timeline are posts that have been deleted.
    deleted = list(post_cache.keys())
    timelimit = get_post_time_limit(post_cache)
    posts, deleted = get_posts(timelimit, deleted)
    logger.debug(post_cache)
    if deleted: 
        database, post_cache = delete(deleted, post_cache, database)
        updates = True
    logger.debug(post_cache)
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
