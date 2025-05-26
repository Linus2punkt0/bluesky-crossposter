from main.functions import logger, cleanup, session_status, terminate_session
from input.fetch import get_posts
from output.send import send_posts
from main.db import database

def run():
    if session_status():
        exit()
    queues = get_posts()
    # If no new or deleted posts are found, we can skip further actions.
    if not new_posts(queues) and not database.deleted:
        logger.info("No new posts or newly deleted posts found.")
        exit()
    logger.debug(f"Found posts {queues}")
    send_posts(queues)
    database.save()
    cleanup()
    terminate_session()

# Checking queues to see if they contain posts
def new_posts(queues):
    for output in queues:
        if queues[output]:
            return True
    return False

if __name__ == "__main__":
    run()