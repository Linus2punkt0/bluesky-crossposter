from settings.auth import *
from settings.paths import *
from local.functions import write_log, cleanup, post_cache_read, post_cache_write, get_post_time_limit
from local.db import db_read, db_backup, save_db
from input.bluesky import get_posts
from output.post import post

# Here the whole thing is run
if __name__ == "__main__":
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
        write_log("No new posts found.")