from atproto import Client, Session, SessionEvent
from loguru import logger
from settings.auth import *
from settings.paths import *
from local.functions import *
from settings import settings
import  os, shutil, re, arrow, sys


# Setting up logging
logger.remove()
log_format = "<yellow>{time:YYYY-MM-DD HH:mm:ss}</yellow> <lvl>[{level}]: {message}</lvl> <yellow>({function} {file}:{line})</yellow>"
logger.add(sys.stdout, format=log_format, level=settings.log_level)
logger.add("%s/crossposter_{time:YYMMDD}.log" % log_path,
        level=settings.log_level,
        format=log_format, 
        rotation="00:00", retention="1 week")

# A wrapper class for the atproto client that allows us to get ratelimit info
class RateLimitedClient(Client):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._limit = self._remaining = self._reset = None

    def get_rate_limit(self):
        return self._limit, self._remaining, self._reset

    def _invoke(self, *args, **kwargs):
        self.response = super()._invoke(*args, **kwargs)
        logger.debug(self.response)
        if not self.response.headers.get("RateLimit-Limit"):
            return self.response
        self._limit = self.response.headers.get("RateLimit-Limit")
        self._remaining = self.response.headers.get("RateLimit-Remaining")
        self._reset = self.response.headers.get("RateLimit-Reset")
        if (int(self._remaining) / int(self._limit)) * 100 < settings.rate_limit_buffer:
            logger.info("Rate limit buffer reached, after this run poster will pause until %s" % arrow.Arrow.fromtimestamp(self._reset).format("YYYY-MM-DD HH:mm:ss"))
            rate_limit_write(self._reset)
        else:
            logger.info("Bluesky rate limit has %s out of %s remaining." % (self._remaining, self._limit))

        return self.response
    
    def get_reply_to_user(self, reply):
        uri = reply.uri
        username = ""
        try: 
            response = self.app.bsky.feed.get_post_thread(params={"uri": uri})
            username = response.thread.post.author.handle
        except Exception as e:
            logger.info("Unable to retrieve reply_to-user of post. Probably a reply to a deleted post.")
        return username

def on_session_change(event: SessionEvent, session: Session) -> None:
    print('Session changed:', event, repr(session))
    if event in (SessionEvent.CREATE, SessionEvent.REFRESH):
        print('Saving changed session')
        session_cache_write(session.export())

def session_cache_read():
    logger.info("Reading session cache")
    if not os.path.exists(session_cache_path):
        logger.info(session_cache_path + " not found.")
        return None
    with open(session_cache_path, 'r') as file:
        return file.read()

def session_cache_write(session):
    logger.info("Saving session cache")
    with open(session_cache_path, "w") as file:
        file.write(session)


# Functions for checking and saving ratelimit-reset
def check_rate_limit():
    logger.info("Checking if application has reach rate limit buffer limit.")
    if not os.path.exists(rate_limit_path):
        return False
    with open(rate_limit_path, 'r') as file:
        timestamp = arrow.Arrow.fromtimestamp(file.read())
        if timestamp > arrow.now():
            logger.info("Rate limit buffer reached, will resume posting %s" % timestamp.humanize())
            return True
        else:
            os.remove(rate_limit_path)
            return False

def rate_limit_write(ratelimit_reset):
    logger.info("Saving ratelimit-reset time")
    file = open(rate_limit_path, "w")
    file.write(ratelimit_reset)
    file.close()


# This function uses the language selection as a way to select which posts should be crossposted.
def lang_toggle(langs, service):
    if service == "twitter":
        lang_toggle = settings.twitter_lang
    elif service == "mastodon":
        lang_toggle = settings.mastodon_lang
    else:
        logger.error("Something has gone very wrong.")
        exit()
    if not lang_toggle:
        return True
    if langs and lang_toggle in langs:
        return (not settings.post_default)
    else:
        return settings.post_default

# Function for correctly counting post length
def post_length(post):
    # Twitter shortens urls to 23 characters
    short_url_length = 23
    length = len(post)
    # Finding all urls and calculating how much shorter the post will be after shortening
    regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
    urls = re.findall(regex, post)
    for url in urls:
        url_length = len(url[0])
        if url_length > short_url_length:
            length = length - (url_length - short_url_length)
    return length



# Cleaning up downloaded images
def cleanup():
    logger.info("Deleting local images")
    for filename in os.listdir(image_path):
        if (filename == ".gitignore"):
            continue
        file_path = os.path.join(image_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            logger.error('Failed to delete %s. Reason: %s' % (file_path, e))

# Following two functions deals with the post per hour limit

# Function for reading post log and checking number of posts sent in last hour
def post_cache_read():
    logger.info("Reading cache of recent posts.")
    cache = {}
    timelimit = arrow.utcnow().shift(hours = -1)
    if not os.path.exists(post_cache_path):
        logger.info(post_cache_path + " not found.")
        return cache
    with open(post_cache_path, 'r') as file:
        for line in file:
            try:
                post_id = line.split(";")[0]
                timestamp = int(line.split(";")[1].split(".")[0])
                timestamp = arrow.Arrow.fromtimestamp(timestamp)
            except Exception as e:
                logger.error(e)
                continue
            if timestamp > timelimit:
                cache[post_id] = timestamp
    return cache

def post_cache_write(cache):
    if not cache:
        if os.path.exists(post_cache_path):
            os.remove(post_cache_path)
        logger.info("No posts in cache, nothing to save.")
        return
    logger.info("Saving post cache.")
    append_write = "w"
    for post_id in cache:
        timestamp = str(cache[post_id].timestamp())
        file = open(post_cache_path, append_write)
        file.write(post_id + ";" + timestamp + "\n")
        file.close()
        append_write = "a"

# The timelimit specifies the cutoff time for which posts are crossposted. This is usually based on the 
# post_time_limit in settings, but if overflow_posts is set to "skip", meaning any posts that could
# not be posted due to the hourly post max limit is to be skipped, then the timelimit is instead set to
# when the last post was sent.
def get_post_time_limit(cache):
    timelimit = arrow.utcnow().shift(hours = -settings.post_time_limit)
    if settings.overflow_posts != "skip":
        return timelimit
    for post_id in cache:
        if timelimit < cache[post_id]:
            timelimit = cache[post_id]
    return timelimit

