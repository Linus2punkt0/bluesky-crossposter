import traceback
from main.functions import logger
from main.connections import twitter_api_connect, twitter_client_connect
from settings.auth import *
from settings import settings
from main.db import database


# Function for processing output queue
def output(queue):
    for item in queue:
        try:
            if item["type"] == "repost" and settings.retweets:
                repost(item)
            else:
                post(item)
        except Exception as e:
            database.failed_post(item["id"], "twitter")
            logger.error(f"Failed to post {item['id']}: {e}")
            logger.debug(traceback.format_exc())

# Function for posting tweets
def post(item):
    twitter_api = twitter_api_connect()
    twitter_client = twitter_client_connect()
    text_content = item["post"].text_content("twitter")
    quote_id = database.get_id(item["post"].info["quote_id"], "twitter")
    reply_id = database.get_id(item["post"].info["reply_id"], "twitter")
    if item["post"].info["reply_id"] and not reply_id:
        logger.info(f"Can't continue thread since {item['post'].info['reply_id']} has not been crossposted")
        return
    if item["post"].info["quote_id"] and not quote_id:
        logger.info(f"Can't create quote post since {item['post'].info['quote_id']} has not been crossposted")
        return
    media_ids = None
    reply_settings = set_reply_settings(item["post"])
    if reply_settings == "everybody":
        reply_settings = None
    # putting media in a new variable so that I can remove it after posting it
    media = item["post"].media
    for text_post in text_content:
        logger.info(f"Posting \"{text_post}\" to Twitter.")
        # If post includes images, images are uploaded so that they can be included in the tweet
        if media:
            media_ids = []
            for media_item in media:
                alt = item["alt"]
                # Abiding by alt character limit
                if len(alt) > 1000:
                    alt = alt[:996] + "..."
                logger.info(f'Uploading media {media_item["filename"]}')
                res = twitter_api.media_upload(media_item["filename"])
                logger.debug(res)
                id = res.media_id
                # If alt text was added to the image on bluesky, it's also added to the image on twitter.
                if alt:
                    logger.info(f"Adding alt-text: {alt}")
                    res = twitter_api.create_media_metadata(id, alt)
                    logger.debug(res)
                media_ids.append(id)
            media = []
        logger.debug(f"text={text_post}, reply_settings={reply_settings}, quote_tweet_id={quote_id}, in_reply_to_tweet_id={reply_id}, media_ids={media_ids}")
        a = twitter_client.create_tweet(text=text_post, reply_settings=reply_settings, quote_tweet_id=quote_id, in_reply_to_tweet_id=reply_id, media_ids=media_ids)
        logger.debug(a)
        # If a quote post gets split, only the first post quotes, and the second becomes just a reply to that post
        quote_id = None
        reply_id = a[0]["id"]
    database.update(item["id"], "twitter", reply_id)

# Function for reposting tweet. Must be enabled in settings
# as it required the paid version of the Twitter API.
def repost(id):
    twitter_client = twitter_client_connect()
    a = twitter_client.retweet(id)
    logger.info(f"retweeted tweet {id}")
    logger.debug(a)

# Function for deleting tweets. Takes ID of post from origin (Mastodon or Bluesky)
def delete_post(origin_id):
    twitter_api = twitter_api_connect()
    post_id = database.get_id(origin_id, "twitter")
    logger.info(f"Deleting tweet with id {post_id}")
    try:
        a = twitter_api.destroy_status(post_id)
        logger.debug(a)
    except Exception as e:
        logger.debug(e)
        if "No status found with that ID" in str(e):
            logger.info(f"Tweet with id {post_id} does not exist")

# Translating reply restrictions to Twitter specific versions. More information in readme.
def set_reply_settings(post):
    reply_settings = None
    if settings.allow_reply == "inherit":
        return settings.privacy[post.info["privacy"]]["twitter"]
    elif settings.allow_reply == "following":
        reply_settings = "following"
    elif settings.allow_reply == "mentioned":
        reply_settings = "mentionedUsers"
    return reply_settings
    




