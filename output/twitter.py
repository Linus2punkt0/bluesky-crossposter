import tweepy
from loguru import logger
from settings import settings 
from settings.auth import *

if settings.Twitter:
    twitter_client = tweepy.Client(consumer_key=TWITTER_APP_KEY,
                        consumer_secret=TWITTER_APP_SECRET,
                        access_token=TWITTER_ACCESS_TOKEN,
                        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET)

    tweepy_auth = tweepy.OAuth1UserHandler(TWITTER_APP_KEY, TWITTER_APP_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET)
    twitter_api = tweepy.API(tweepy_auth)

# Function for posting tweets
def tweet(post, reply_to_post, quoted_post, media, allowed_reply):
    media_ids = None
    reply_settings = set_reply_settings(allowed_reply)
    # If post includes images, images are uploaded so that they can be included in the tweet
    if media:
        media_ids = []
        for item in media:
            alt = item["alt"]
            # Abiding by alt character limit
            if len(alt) > 1000:
                alt = alt[:996] + "..."
            res = twitter_api.media_upload(item["filename"])
            id = res.media_id
            # If alt text was added to the image on bluesky, it's also added to the image on twitter.
            if alt:
                logger.info("Uploading media " + item["filename"] + " with alt: " + alt + " to twitter")
                twitter_api.create_media_metadata(id, alt)
            media_ids.append(id)
    # Checking if the post is longer than 280 characters, and if so sending to the
    # splitPost-function.
    partTwo = ""
    if len(post) > 280:
        post, partTwo = split_post(post)
    a = twitter_client.create_tweet(text=post, reply_settings=reply_settings, quote_tweet_id=quoted_post, in_reply_to_tweet_id=reply_to_post, media_ids=media_ids)
    logger.info("Posted to twitter")
    id = a[0]["id"]
    if partTwo:
        a = twitter_client.create_tweet(text=partTwo, in_reply_to_tweet_id=id)
        id = a[0]["id"]
    return id

def retweet(tweet_id):
    a = twitter_client.retweet(tweet_id)
    logger.info("retweeted tweet " + str(tweet_id))

def delete(tweet_id):
    logger.info("Deleting tweet with id " + tweet_id)
    try:
        a = twitter_api.destroy_status(tweet_id)
        logger.debug(a)
    except Exception as e:
        logger.debug(e)
        if "No status found with that ID" in str(e):
            logger.info("Tweet with id %s does not exist" % tweet_id)

# Function for splitting up posts that are too long for twitter.
def split_post(text):
    logger.info("Splitting post that is too long for twitter.")
    first = text
    # We first try to split the post by paragraphs, and send as many as can fit in the first post,
    # and the rest in the second.
    if "\n" in text:
        paragraphs = text.split("\n")
        i = 1
        while len(first) > 280 and i < len(paragraphs):
            first = "\n".join(sentences[:(len(sentences) - i)]) + "\n"
            second = "\n".join(sentences[(len(sentences) - i):])
            i += 1
    # If post can't be split by paragraph, we try by sentence.
    if len(first) > 280:
        first = text
        sentences = text.split(". ")
        i = 1
        while len(first) > 280 and i < len(sentences):
            first = ". ".join(sentences[:(len(sentences) - i)]) + "."
            second = ". ".join(sentences[(len(sentences) - i):])
            i += 1
    # If splitting by sentence does not result in a short enough post, we try splitting by words instead.
    if len(first) > 280:
        first = text
        words = text.split(" ")
        i = 1
        while len(first) > 280 and i < len(words):
            first = " ".join(words[:(len(words) - i)])
            second = " ".join(words[(len(words) - i):])
            i += 1
    # If splitting has ended up with either a first or second part that is too long, we return empty
    # strings and the post is not sent to twitter.
    if len(first) > 280 or len(second) > 280:
        logger.info("Was not able to split post.", "error")
        first = ""
        second = ""
    return first, second


def set_reply_settings(allowed):
    reply_settings = None
    if allowed == "None" or allowed == "Mentioned":
        reply_settings = "mentionedUsers"
    elif allowed == "Following":
        reply_settings = "following"
    return reply_settings
