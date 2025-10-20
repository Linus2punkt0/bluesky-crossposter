import tweepy, traceback, requests
from mastodon import Mastodon
from atproto import Client, Session, SessionEvent
from main.functions import logger
from settings.auth import *
from settings.paths import session_cache_path, rate_limit_path
from settings import settings
import arrow, os

# Connection to Mastodon API
def mastodon_connect():
    if hasattr(mastodon_connect, "_connection"):
        logger.info("Already connected to Mastodon API.")
        return mastodon_connect._connection
    logger.info("Connecting to Mastodon API.")
    mastodon_connect._connection = Mastodon(
        access_token = MASTODON_TOKEN,
        api_base_url = MASTODON_INSTANCE
    ) 
    return mastodon_connect._connection

# Twitter has two different API methods, and both are needed.

# Connection to Twitter API
def twitter_api_connect():
    if hasattr(twitter_api_connect, "_connection"):
        logger.info("Already connected to Twitter API.")
        return twitter_api_connect._connection
    logger.info("Connecting to Twitter API.")
    tweepy_auth = tweepy.OAuth1UserHandler(TWITTER_APP_KEY, TWITTER_APP_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET)
    twitter_api_connect._connection = tweepy.API(tweepy_auth)
    return twitter_api_connect._connection

# Connection to Twitter client 
def twitter_client_connect():
    if hasattr(twitter_client_connect, "_connection"):
        logger.info("Already connected to Twitter Client.")
        return twitter_client_connect._connection
    logger.info("Connecting to Twitter Client.")
    twitter_client_connect._connection = tweepy.Client(consumer_key=TWITTER_APP_KEY,
                        consumer_secret=TWITTER_APP_SECRET,
                        access_token=TWITTER_ACCESS_TOKEN,
                        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
                        return_type=requests.Response)
    return twitter_client_connect._connection

# Connecting to Bluesky ATProto
def bsky_connect():
    if hasattr(bsky_connect, "_connection"):
        logger.info("Already connected to Bluesky.")
        return bsky_connect._connection
    try:
        logger.info(f'Connecting to Bluesky: {BSKY_PDS}.')
        bsky_connect._connection = RateLimitedClient(BSKY_PDS)
        # In order to not be ratelimited, session is cached in a session file.
        bsky_connect._connection.on_session_change(on_session_change)
        session = session_cache_read()
        # Try excepting will catch both missing and expired session files and will instead attempt
        # regular login
        try:
            logger.info("Connecting to Bluesky using saved session.")
            bluesky_clbsky_connect._connectionient.login(session_string=session)
            logger.info("Successfully logged in to Bluesky using saved session.")
        except:
            logger.info("Creating new Bluesky session using password and username.")
            bsky_connect._connection.login(BSKY_HANDLE, BSKY_PASSWORD)
            logger.info("Successfully logged in to Bluesky.")
        session = bsky_connect._connection.export_session_string()
        session_cache_write(session)
        return bsky_connect._connection
    except Exception as e:
        logger.error(e)
        if e.response.content.error == "RateLimitExceeded":
            logger.debug("Bluesky ratelimit was exceeded!")
        elif e.response.content.error == "ExpiredToken":
            logger.info("Session expired, removing session file.")
            os.remove(session_cache_path)
        exit()


# A wrapper class for the atproto client that allows us to get ratelimit info
class RateLimitedClient(Client):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._limit = self._remaining = self._reset = None

    def get_rate_limit(self):
        return self._limit, self._remaining, self._reset

    def _invoke(self, *args, **kwargs):
        self.response = super()._invoke(*args, **kwargs)
        if not self.response.headers.get("RateLimit-Limit"):
            return self.response
        self._limit = self.response.headers.get("RateLimit-Limit")
        self._remaining = self.response.headers.get("RateLimit-Remaining")
        self._reset = self.response.headers.get("RateLimit-Reset")

        return self.response
    
    # Function for fetching the user a post is a reply to
    def get_reply_to_user(self, reply):
        uri = reply.uri
        username = ""
        try: 
            response = self.app.bsky.feed.get_post_thread(params={"uri": uri})
            username = response.thread.post.author.handle
        except Exception as e:
            logger.info("Unable to retrieve reply_to-user of post. Probably a reply to a deleted post.")
            logger.debug(traceback.format_exc())
        return username
    
# Checks if changes are made to the Bluesky session, meaning the local session file needs to be updated
def on_session_change(event: SessionEvent, session: Session) -> None:
    logger.info('Session changed:', event, repr(session))
    if event in (SessionEvent.CREATE, SessionEvent.REFRESH):
        logger.info('Saving changed session')
        session_cache_write(session.export())

# Reading local Bluesky session file
def session_cache_read():
    logger.info("Reading session cache")
    if not os.path.exists(session_cache_path):
        logger.info(session_cache_path + " not found.")
        return None
    with open(session_cache_path, 'r') as file:
        return file.read()

# Writing local Bluesky session file
def session_cache_write(session):
    logger.info("Saving session cache")
    with open(session_cache_path, "w") as file:
        file.write(session)

