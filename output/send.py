from settings import settings
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
            twitter.output(queues[service])
    # Running through and deleting deleted posts for each included service.
    for id in database.deleted:
        if settings.outputs["twitter"] and settings.input_source != "twitter" and database.get_id(id, "twitter"):
            twitter.delete_post(id)
        if settings.outputs["mastodon"] and settings.input_source != "mastodon" and database.get_id(id, "mastodon"):
            mastodon.delete_post(id)
        if settings.outputs["bluesky"] and settings.input_source != "bluesky" and database.get_id(id, "bluesky"):
            bluesky.delete_post(id)
        database.remove(id)


