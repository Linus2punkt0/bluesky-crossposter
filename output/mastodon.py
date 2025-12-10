import traceback
from main.functions import logger, limit_gif_size
from main.connections import mastodon_connect
from settings.auth import MASTODON_HANDLE, MASTODON_INSTANCE
from settings import settings
from main.db import database


# Function for processing output queue
def output(queue):
    logger.info("Posting queue to Mastodon.")
    for item in queue:
        try:
            if item["type"] == "repost":
                repost(item)
            else:
                post(item)
        except Exception as e:
            database.failed_post(item["id"], "mastodon")
            logger.error(f"Failed to post {item['id']}: {e}")
            logger.debug(traceback.format_exc())

# Function for reposting posts.
def repost(item):
    mastodon_client = mastodon_connect()
    post_id = database.get_id(item["id"], "mastodon")
    a = mastodon_client.status_reblog(post_id)
    database.update(item["id"], "mastodon")
    logger.info(f"Reposted post on Mastodon: {post_id}")
    logger.debug(a)

# Function for sending posts
def post(item):
    mastodon_client = mastodon_connect()
    text_content = item["post"].text_content("mastodon")
    reply_to_post = database.get_id(item["post"].info["reply_id"], "mastodon")
    # Checking to see if post is a reply to a post that has not been crossposted
    if item["post"].info["reply_id"] and not reply_to_post:
        logger.info(f"Can't continue thread since {item['post'].info['reply_id']} has not been crossposted")
        return
    # Since mastodon does not have a quote repost function, quote posts are turned into replies. If the post is both
    # a reply and a quote post, the quote is replaced with a url to the post quoted.
    if item["type"] == "quote" and item["post"].info["reply_id"]:
        post_url = MASTODON_INSTANCE + "@" + MASTODON_HANDLE + "/" + str(item["post"].info["quote_id"])
        reply_to_post = database.get_id(item["post"].info["reply_id"], "mastodon")
        text_content = item["post"].text_content("mastodon", f"\n{post_url}")
    elif item["type"] == "quote":
        reply_to_post = database.get_id(item["post"].info["quote_id"], "mastodon")
        if not reply_to_post:
            logger.info(f"Can't post quote since {item['post'].info['quote_id']} has not been crossposted")
            return
    # Doing a second check to see if post is a reply or quote of a post that has been skipped or failed to br crossposted.
    if reply_to_post in ["skipped", "FailedToPost", "duplicate"]:
        logger.info(f"Post is a reply to or qoute post of a post that has not been crossposted.")
        return
    visibility = set_visibility(item["post"])
    # If language is not used to toggle what posts to send, it is used simply as the language of the post.
    # Mastodon only takes one language per post, so the first one in the list is used.
    language = None
    if not settings.lang_toggle["mastodon"]:
        language = item["post"].get_main_language()
    media_ids = []
    # If post includes images, images are uploaded so that they can be included in the toot
    if item["post"].media:
        for media_item in item["post"].media:
            # If alt text was added to the image on bluesky, it's also added to the image on mastodon,
            # otherwise it will be uploaded without alt text.
            alt = media_item["alt"]
            # Abiding by alt character limit
            if len(alt) > 1500:
                alt = alt[:1496] + "..."
            filename = media_item['filename']
            if media_item["type"] == "GIF":
                filename = limit_gif_size(filename, 16000000)
            logger.info(f"Uploading media {filename} with alt: {alt} to mastodon")
            res = mastodon_client.media_post(filename, description=media_item["alt"], synchronous=True)
            media_ids.append(res.id)
    for text_post in text_content:
        logger.info(f"Posting \"{text_post}\" to Mastodon")
        # API won't handle leading spaces. Tricking it by replacing the first leading space with a no-break space.
        if text_post.startswith(" "):
            text_post = text_post.replace(" ", "\u00A0", 1)
        logger.debug(f"mastodon_client.status_post({text_post}, in_reply_to_id={reply_to_post}, media_ids={media_ids}, visibility={visibility}, language={language}), sensitive={item["post"].info["sensitive"]}")
        a = mastodon_client.status_post(text_post, in_reply_to_id=reply_to_post, media_ids=media_ids, visibility=visibility, language=language, sensitive=item["post"].info["sensitive"])
        logger.debug(a)
        reply_to_post = a["id"]
        # setting media ids to empty to not end up posting the media in every post in the thread
        media_ids = []
        database.update(item["id"], "mastodon", a["id"])
    logger.info("Posted to mastodon")

# Function for deleting post. Takes ID of post from origin (Bluesky)
def delete_post(origin_id):
    mastodon_client = mastodon_connect()
    post_id = database.get_id(origin_id, "mastodon")
    logger.info("deleting toot " + str(post_id))
    try:
        a = mastodon_client.status_delete(post_id)
        logger.debug(a)
    except Exception as e:
        logger.debug(e)
        if "Record not found" in str(e):
            logger.info(f"Toot with id {post_id} does not exist")

# Function for translating visibility settings to Mastodon specifics. More information about this in readme.
def set_visibility(post):
    if settings.mastodon_visibility == "inherit":
        return settings.privacy[post.info["privacy"]]["mastodon"]
    elif settings.mastodon_visibility == "unlisted":
        return "unlisted"
    elif settings.mastodon_visibility == "public":
        return "public"
    elif settings.mastodon_visibility == "hybrid" and (post.info["reply_id"] or post.info["quote_id"]):
        return "unlisted"
    elif settings.mastodon_visibility == "hybrid":
        return "public"
    