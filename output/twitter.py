import traceback, arrow, json, tweepy
from main.functions import logger, limit_gif_size
from main.connections import twitter_api_connect, twitter_client_connect
from settings.auth import *
from settings import settings
from settings.paths import rate_limit_path
from main.db import database


# Function for processing output queue
def output(queue):
    if check_ratelimit_reset():
        return
    logger.info("Posting queue to Twitter.")
    for item in queue:
        try:
            if item["type"] == "repost" and settings.retweets:
                repost(item)
            else:
                post(item)
        except tweepy.TooManyRequests:
            logger.error("Twitter ratelimit reached!")
            logger.debug(traceback.format_exc())
            set_ratelimit_reset(arrow.now().shift(days=1).timestamp())
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
    if item["post"].info["reply_id"] and not reply_id or reply_id in ["skipped", "FailedToPost", "duplicate"]:
        logger.info(f"Can't continue thread since {item['post'].info['reply_id']} has not been crossposted")
        return
    if item["type"] == "quote" and (not quote_id or quote_id in ["skipped", "FailedToPost", "duplicate"]):
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
                # Shrinking and chunking uploads of gifs to avoid size limitations
                chunked = False
                media_category = None
                filename = media_item["filename"]
                if media_item["type"] == "GIF":
                    chunked = True
                    media_category = "tweet_gif"
                    filename = limit_gif_size(filename, 15728640)
                alt = media_item["alt"]
                # Abiding by alt character limit
                if len(alt) > 1000:
                    alt = alt[:996] + "..."
                logger.info(f'Uploading media {filename}, chunked={chunked}, media_category={media_category}')
                res = twitter_api.media_upload(filename, chunked=chunked, media_category=media_category)
                logger.debug(res)
                id = res.media_id
                # If alt text was added to the image on bluesky, it's also added to the image on twitter.
                if alt:
                    logger.info(f"Adding alt-text: {alt}")
                    res = twitter_api.create_media_metadata(id, alt)
                    logger.debug(res)
                media_ids.append(id)
            media = []
        # API won't handle leading spaces. Tricking it by addigng a "Zero Width Non-Joiner".
        if text_post.startswith(" "):
            text_post = text_post.replace(" ", "\u200C ", 1)
        logger.debug(f"text={text_post}, reply_settings={reply_settings}, quote_tweet_id={quote_id}, in_reply_to_tweet_id={reply_id}, media_ids={media_ids}")
        a = twitter_client.create_tweet(text=text_post, reply_settings=reply_settings, quote_tweet_id=quote_id, in_reply_to_tweet_id=reply_id, media_ids=media_ids)
        logger.debug(a.headers)
        logger.debug(a.content)
        content = json.loads(a.content)
        # If a quote post gets split, only the first post quotes, and the second becomes just a reply to that post
        quote_id = None
        reply_id = content["data"]["id"]
        # Checking remaining ratelimit and ratelimit reset time
        remaining_ratelimit = int(a.headers["x-app-limit-24hour-remaining"])
        logger.info(f"{remaining_ratelimit} posts remaining until twitter ratelimit is reached")
        reset_time = int(a.headers["x-app-limit-24hour-reset"])
        if remaining_ratelimit < 1:
            logger.info("Twitter ratelimit has been reached.")
            set_ratelimit_reset(reset_time)
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
    

def set_ratelimit_reset(reset):
    timestamp = arrow.get(reset)
    logger.info(f"Twitter ratelimit has been reached. Trying again in {timestamp.humanize()}.")
    logger.info("Saving ratelimit-reset time")
    file = open(rate_limit_path, "w")
    file.write(f"{timestamp.timestamp()}")
    file.close()


# Functions for checking and saving ratelimit-reset
def check_ratelimit_reset():
    logger.info("Checking if crossposter has reached ratelimit for Twitter.")
    if not os.path.exists(rate_limit_path):
        return False
    with open(rate_limit_path, 'r') as file:
        timestamp = file.read()
        if timestamp:
            timestamp = arrow.Arrow.fromtimestamp(timestamp)
        else:
            timestamp = arrow.now()
        if timestamp > arrow.now():
            logger.info(f"Rate limit buffer reached, will try again {timestamp.humanize()}.")
            return True
        else:
            os.remove(rate_limit_path)
            return False
