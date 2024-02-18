import tweepy
from settings import settings 
from settings.auth import *
from local.functions import write_log

if settings.Twitter:
    twitter_client = tweepy.Client(consumer_key=TWITTER_APP_KEY,
                        consumer_secret=TWITTER_APP_SECRET,
                        access_token=TWITTER_ACCESS_TOKEN,
                        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET)

    tweepy_auth = tweepy.OAuth1UserHandler(TWITTER_APP_KEY, TWITTER_APP_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET)
    twitter_api = tweepy.API(tweepy_auth)

# Function for posting tweets
def tweet(post, reply_to_post, quoted_post, images, allowed_reply):
    media_ids = None
    reply_settings = set_reply_settings(allowed_reply)
    # If post includes images, images are uploaded so that they can be included in the tweet
    if images:
        media_ids = []
        for image in images:
            filename = image["filename"]
            alt = image["alt"]
            if len(alt) > 1000:
                alt = alt[:996] + "..."
            res = twitter_api.media_upload(filename)
            id = res.media_id
            # If alt text was added to the image on bluesky, it's also added to the image on twitter.
            if alt:
                write_log("Uploading image " + filename + " with alt: " + alt + " to twitter")
                twitter_api.create_media_metadata(id, alt)
            media_ids.append(id)
    # Checking if the post is longer than 280 characters, and if so sending to the
    # splitPost-function.
    partTwo = ""
    if len(post) > 280:
        post, partTwo = split_post(post)
    a = twitter_client.create_tweet(text=post, reply_settings=reply_settings, quote_tweet_id=quoted_post, in_reply_to_tweet_id=reply_to_post, media_ids=media_ids)
    write_log("Posted to twitter")
    id = a[0]["id"]
    if partTwo:
        a = twitter_client.create_tweet(text=partTwo, in_reply_to_tweet_id=id)
        id = a[0]["id"]
    return id

def retweet(tweet_id):
    a = twitter_client.retweet(tweet_id)
    write_log("retweeted tweet " + str(tweet_id))


# Function for splitting up posts that are too long for twitter.
def split_post(text):
    write_log("Splitting post that is too long for twitter.")
    first = text
    # We first try to split the post into sentences, and send as many as can fit in the first one,
    # and the rest in the second.
    sentences = text.split(". ")
    i = 1
    while len(first) > 280 and i < len(sentences):
        first = ".".join(sentences[:(len(sentences) - i)]) + "."
        second = ".".join(sentences[(len(sentences) - i):])
        i += 1
    # If splitting by sentance does not result in a short enough post, we try splitting by words instead.
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
        write_log("Was not able to split post.", "error")
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
