from settings import settings
from main.functions import twitter_running, twitter_finished
from output import twitter, mastodon, bluesky
from main.db import database

# Function for processing post queue
def send_posts(queues):
    # Running through and posting to each included service
    for service in queues:
        if service == "bluesky" and queues[service]:
            bluesky.output(queues[service])
        if service == "mastodon" and queues[service]:
            mastodon.output(queues[service])
        if service == "twitter" and queues[service]:
            # Sometimes the crossposter will be stuck waiting for twitters rate limit 
            # longer than the wait time between runs. This makes sure that it is not queueing up
            # multiple concurrent runs.
            if twitter_running():
                continue
            twitter.output(queues[service])
            twitter_finished()
    # Running through and deleting deleted posts for each included service.
    for id in database.deleted:
        if settings.outputs["twitter"] and settings.input_source != "twitter" and database.get_id(id, "twitter"):
            twitter.delete_post(id)
        if settings.outputs["mastodon"] and settings.input_source != "mastodon" and database.get_id(id, "mastodon"):
            mastodon.delete_post(id)
        if settings.outputs["bluesky"] and settings.input_source != "bluesky" and database.get_id(id, "bluesky"):
            bluesky.delete_post(id)
        database.remove(id)


