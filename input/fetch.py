import arrow
from copy import deepcopy
from settings import settings
from main.functions import logger, get_outputs
from input import bluesky, mastodon
from main.db import database


def get_posts():
    # Fetching an initial list of posts
    if settings.input_source == "bluesky":
        posts = bluesky.get_posts()
    elif settings.input_source == "mastodon":
        posts = mastodon.get_posts()
    else:
        logger.error(f"Unknown input source: {settings.input_source}")
    # Getting queues for all active outputs
    queues = {}
    for output in get_outputs():
        queues[output] = []
    # Further parsing the posts to get an actual list of posts to send.
    for post_id in posts:
        # Checking if a maximum amount of posts per hour is set, and if so if it has been reached.
        if settings.max_per_hour != 0 and len(database.cache) >= settings.max_per_hour:
            logger.info("Max posts per hour reached.")
            break
        source_post = posts[post_id]
        # Checking what services this specific post should be sent to
        outputs = []
        for service in get_outputs():
            # If the lang toggles or privacy settings are set to not crosspost this specific post to this service, 
            # it is set to skipped in the database and then skipped.
            if not source_post.post_toggle(service):
                database.skip(post_id, service)
                continue
            elif not database.posted(post_id, [service]):
                logger.info(f"{post_id} has not been posted to {service}")
                # Adding service either as post or repost, depending on if it has been posted before or not. 
                # This allows users to repost a post that has not previously been crossposted, and have it be posted as a new post.
                outputs.append({"name": service, "type": "post"})
            elif (source_post.info["repost"] and not database.not_posted(post_id, [service])):
                logger.info(f"{post_id} has been posted to {service}, adding as a repost.")
                outputs.append({"name": service, "type": "repost"})
        # If no services found to post to, skipping to the next post
        if not outputs:
            logger.info(f"Post {post_id} is not set to be posted to any service. Skipping to next post.")
            continue
        post_data = {
            "id": post_id,
            "type": "post", #post, reply, repost, quote
            "post": posts[post_id]
        }
        # If it is a reply, getting the IDs of the posts to reply to from the database.
        # If post is not found in database, the thread can't continue on mastodon and twitter,
        # and so is skipped.
        if source_post.info["reply_id"] and source_post.info["reply_id"] in database.post_list:
            post_data["type"] = "reply"
        elif source_post.info["reply_id"] and source_post.info["reply_id"] not in database.post_list:
            logger.info(f"Post {post_id} was a reply to a post that is not in the database.")
            continue
        # If post is a quote post, getting the IDs of the posts to quote from the database.
        # If the posts are not found in the database, checking if the quote_post setting is true or false in settings.
        # If true, adding the URL of the bluesky post to the text of the post, if false, skipping the post.
        if source_post.info["quote_id"] and source_post.info["quote_id"] in database.post_list:
            post_data["type"] = "quote"
        elif source_post.info["quote_id"] and source_post.info["quote_id"]  not in database.post_list:
            # Adding url to quoted post to text of post if quote post is set to true in the settings
            if not source_post.quote_link():
                logger.info(f"Post {post_id} was a quote of a post that is not in the database.")
                continue
        # Checking if the post has media and if it should be sent anywhere for the first time, in which case media is downloaded
        if source_post.info["media"] and next((item for item in outputs if item["type"] == "post"), False):
            source_post.get_media()
        # If a repost is found within the last hour, checking the cache to see if it has already been reposted
        repost_timelimit = arrow.utcnow().shift(hours = -1)
        if post_id in database.cache:
            repost_timelimit = database.cache[post_id]
        for output in outputs:
            # Making separate copies of the post-data for the different services
            post = deepcopy(post_data)
            # Adding repost if post is before the repost time limit, otherwise skipping
            if output["type"] == "repost" and source_post.info["created_at"] > repost_timelimit:
                post["type"] = "repost"
            elif output["type"] == "repost" and source_post.info["created_at"] < repost_timelimit:
                continue
            queues[output["name"]].append(post)
    return queues