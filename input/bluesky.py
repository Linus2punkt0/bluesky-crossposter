from local.functions import logger
from settings.auth import BSKY_HANDLE, BSKY_PASSWORD, BSKY_PDS
from settings.paths import *
from settings import settings
from local.functions import RateLimitedClient, lang_toggle, rate_limit_write, session_cache_read, session_cache_write, on_session_change
import arrow, os



# Setting up connections to bluesky, twitter and mastodon
def bsky_connect():
    try:
        logger.info(f'Connecting to Bluesky: {BSKY_PDS}.')
        bsky = RateLimitedClient(BSKY_PDS)
        bsky.on_session_change(on_session_change)
        session = session_cache_read()
        if session:
            logger.info("Connecting to Bluesky using saved session.")
            bsky.login(session_string=session)
            logger.info("Successfully logged in to Bluesky using saved session.")
        else:
            logger.info("Creating new Bluesky session using password and username.")
            bsky.login(BSKY_HANDLE, BSKY_PASSWORD)
            logger.info("Successfully logged in to Bluesky.")
        session = bsky.export_session_string()
        session_cache_write(session)
        return bsky
    except Exception as e:
        logger.error(e)
        if e.response.content.error == "RateLimitExceeded":
            ratelimit_reset = e.response.headers["RateLimit-Reset"]
            rate_limit_write(ratelimit_reset)
        elif e.response.content.error == "ExpiredToken":
            logger.info("Session expired, removing session file.")
            os.remove(session_cache_path)
        exit()

# Getting posts from bluesky

def get_posts(timelimit = arrow.utcnow().shift(hours = -1), deleted = []):
    bsky = bsky_connect()
    logger.info("Gathering posts")
    posts = {}
    # Getting feed of user
    profile_feed = bsky.app.bsky.feed.get_author_feed({'actor': BSKY_HANDLE})
    visibility = settings.visibility
    for feed_view in profile_feed.feed:
#        logger.debug(feed_view)
        # If the post was not written by the account that posted it, it is a repost from another account and we skip it.
        if feed_view.post.author.handle != BSKY_HANDLE:
            logger.debug(f'Skipping repost from another account: {feed_view.post.author.handle}. ')
            continue
        # Checking if the post has "indexe_at" set, meaning it is a repost.
        repost = False
        created_at = get_date(feed_view.post.record.created_at.split(".")[0])
        logger.debug(f'Post created at: {created_at}')
        if hasattr(feed_view.reason, "indexed_at"):
            repost = True
            created_at = get_date(feed_view.reason.indexed_at.split(".")[0])
        # The language settings on posts are used to determine if a post should be crossposted
        # to a specific service. Here we check the settings against the language of the post to 
        # see what service it should post to. We also check if posting for a service is enabled
        # at all in the settings. If it shouldn't post to either, we skip it.
        logger.debug(f'The post was reposted: {repost}')
        langs = feed_view.post.record.langs
        mastodon_post = (lang_toggle(langs, "mastodon") and settings.Mastodon)
        twitter_post = (lang_toggle(langs, "twitter") and settings.Twitter)
        logger.debug(f'The post have to be posted on Mastodon: {mastodon_post}')
        logger.debug(f'The post have to be posted on Twitter: {twitter_post}')
        if not mastodon_post and not twitter_post:
            continue
        cid = feed_view.post.cid
        text = feed_view.post.record.text
        # Checking if there are any posts in the cache that are no longer in the timeline, meaning they have been deleted.
        if cid in deleted:
            deleted.remove(cid)
        # Facets contains things like urls and mentions, which we need to deal with.
        # send_mention is used to keep track of if the mention-settings says for the post to be posted or not.
        # Default is True, because if nobody is mentioned it should be posted.
        send_mention = True
        if feed_view.post.record.facets:
            # Sometimes bluesky shortens URLs and in that case we need to restore them before crossposting
            text = restore_urls(feed_view.post.record)
            # If a user is mentioned the parse_mentioned_username function will deal with it according
            # to how the variable "mentions" is set in settings. If it is set to "ignore", nothing is
            # done.
            if settings.mentions != "ignore":
                text, send_mention = parse_mentioned_username(feed_view.post.record, text)
        # If "mentions" is set to "skip" a post with a mention should not be crossposted, and parse_mentioned_username will
        # return send_mention as False.
        if not send_mention:
            continue
        # Setting reply_to_user to the same as user handle and only changing it if the tweet is an actual reply.
        # This way we can just check if the variable is the same as the user handle later and send through
        # both tweets that are not replies, and posts that are part of a thread.
        reply_to_user = BSKY_HANDLE
        reply_to_post = ""
        quoted_post = ""
        quote_url = ""
        # Checking who is allowed to reply to the post
        allowed_reply = get_allowed_reply(feed_view.post)
        # Checking if post is a quote post. Posts with references to feeds look like quote posts but aren't, and so will fail on missing attribute.
        # Since quote posts can give values in two different ways it's a bit of a hassle to double check if it is an actual quote post,
        # so instead I just try to run the function and if it fails I skip the post
        # If there is some reason you would want to crosspost a post referencing a bluesky-feed that I'm not seeing, I might update this in the future.
        if feed_view.post.embed and hasattr(feed_view.post.embed, "record"):
            try:
                quoted_user, quoted_post, quote_url, open = get_quote_post(feed_view.post.embed.record)
            except:
                logger.error("Post " + cid + " is of a type the crossposter can't parse.")
                continue
            # If post is a quote post of a post from another user, and quote-posting is disabled in settings
            # or the post is not open to users not logged in, the post will be skipped
            if quoted_user != BSKY_HANDLE and (not settings.quote_posts or not open):
                continue
            # If the post is a quote of ourselves, the url to the post is removed (if it was included),
            # as we instead want to reference the version of the post from twitter or mastodon.
            # If no such post exists, we can add back the link to the bluesky-post later
            elif quoted_user == BSKY_HANDLE:
                text = text.replace(quote_url, "")
        # Checking if post is regular reply
        if feed_view.post.record.reply:
            reply_to_post = feed_view.post.record.reply.parent.cid
            # Poster will try to fetch reply to-username the "ordinary" way, 
            # and if it fails, it will try getting the entire thread and
            # finding it that way
            try:
                reply_to_user = feed_view.reply.parent.author.handle
            except:
                reply_to_user = bsky.get_reply_to_user(feed_view.post.record.reply.parent)
        # If unable to fetch user that was replied to, code will skip this post. If the post was not a 
        # reply at all, the reply_to_user will still be set to the user account.
        if not reply_to_user:
            logger.info("Unable to find the user that post " + cid + " replies to or quotes")
            continue
        # Checking if post is withing timelimit and not a reply to someone elses post.
        if created_at > timelimit and reply_to_user == BSKY_HANDLE:
            # Fetching images if there are any in the post
            image_data = ""
            video_data = {}
            media = {}
            if feed_view.post.embed and hasattr(feed_view.post.embed, "images"):
                image_data = feed_view.post.embed.images
            elif feed_view.post.embed and hasattr(feed_view.post.embed, "media") and hasattr(feed_view.post.embed.media, "images"):
                image_data = feed_view.post.embed.media.images
            elif  feed_view.post.record.embed and (hasattr(feed_view.post.record.embed, "video") \
                or (hasattr(feed_view.post.record.embed, "media") and hasattr(feed_view.post.record.embed.media, "video"))):
                video_data = get_video_data(feed_view)
                media = {
                    "type": "video",
                    "data": video_data
                }
                logger.debug("Found video: %s" % video_data)
            # Sometimes posts have included links that are not included in the actual text of the post. This adds adds that back.
            if feed_view.post.embed and hasattr(feed_view.post.embed, "external") and hasattr(feed_view.post.embed.external, "uri"):
                if feed_view.post.embed.external.uri not in text:
                    text += '\n'+feed_view.post.embed.external.uri
            if image_data:
                images = []
                for image in image_data:
                    images.append({"url": image.fullsize, "alt": image.alt})
                media = {
                    "type": "image",
                    "data": images
                }
            if visibility == "hybrid" and reply_to_post:
                visibility = "unlisted"
            elif visibility == "hybrid":
                visibility = "public"
            post_info = {
                "text": text,
                "reply_to_post": reply_to_post,
                "quoted_post": quoted_post,
                "quote_url": quote_url,
                "media": media,
                "visibility": visibility,
                "twitter": twitter_post,
                "mastodon": mastodon_post,
                "allowed_reply": allowed_reply,
                "repost": repost,
                "timestamp": created_at
            }
            logger.debug(post_info)
            # Saving post to posts dictionary
            posts[cid] = post_info;
    return posts, deleted

# Sometimes the date string is given in a different format, this is dealt with here.
def get_date(date_string):
    date_in_format = 'YYYY-MM-DDTHH:mm:ss'
    try:
        date = arrow.get(date_string, date_in_format)
    except:
        date = arrow.get(date_string, date_in_format+"ZZ")
    return date

def get_allowed_reply(post):
        reply_restriction = post.threadgate
        if reply_restriction is None:
            return "All"
        if not reply_restriction.record.allow or len(reply_restriction.record.allow) == 0:
            return "None"
        if reply_restriction.record.allow[0].py_type == "app.bsky.feed.threadgate#followingRule":
            return "Following"
        if reply_restriction.record.allow[0].py_type == "app.bsky.feed.threadgate#mentionRule":
            return "Mentioned"
        return "Unknown"

# Function for restoring shortened URLS
def restore_urls(record):
    text = record.text
    encoded_text = text.encode("UTF-8")
    for facet in record.facets:
        if facet.features[0].py_type != "app.bsky.richtext.facet#link":
            continue
        url = facet.features[0].uri
        # The index section designates where a URL starts end ends. Using this we can pick out the exact
        # string representing the URL in the post, and replace it with the actual URL.
        start = facet.index.byte_start
        end = facet.index.byte_end
        section = encoded_text[start:end]
        shortened = section.decode("UTF-8")
        text = text.replace(shortened, url)
    return text


def parse_mentioned_username(record, text):
    # send_mention keeps track if the post should be sent at all.
    send_mention = True
    encoded_text = text.encode("UTF-8")
    for facet in record.facets:
        if facet.features[0].py_type != "app.bsky.richtext.facet#mention":
            continue
        # The index section designates where a username starts end ends. Using this we can pick out the exact
        # string representing the user in the post, and replace it with the corrected value
        start = facet.index.byte_start
        end = facet.index.byte_end
        username = encoded_text[start:end]
        username = username.decode("UTF-8")
        # If the mentions setting is set to skip, None will be returned, if it's set to strip the
        # text will be returned with the @ of the username removed, if it's set to URL the name will
        # be replaced with a link to the profile.
        if settings.mentions == "skip":
            send_mention = False
        elif settings.mentions == "strip":
            text = text.replace(username, username.replace("@", ""))
        elif settings.mentions == "url":
            base_url = "https://bsky.app/profile/"
            did = facet.features[0].did
            url = base_url + did
            text = text.replace(username, url)
    return text, send_mention

# Quoted posts can be stored in several different ways for some reason. With this
# function we check which one is used and fetches information accordingly.
def get_quote_post(post):
    open = True
    if isinstance(post, dict):
        user = post["record"]["author"]["handle"]
        cid = post["record"]["cid"]
        uri = post["record"]["uri"]
        labels = post["record"]["author"]["labels"]
    elif hasattr(post, "author"):
        user = post.author.handle
        cid = post.cid
        uri = post.uri
        labels = post.author.labels
    else:
        user = post.record.author.handle
        cid = post.record.cid
        uri = post.record.uri
        labels = post.record.author.labels
    # the val label is used by bluesky to check if a post should be viewable by people
    # who are not logged in. When crossposting with a link to a bsky post, we first
    # want to make sure that the post in question is publicly available.
    if labels and labels[0].val == "!no-unauthenticated":
        open = False
    url = "https://bsky.app/profile/" + user + "/post/" + uri.split("/")[-1]
    return user, cid, url, open


def get_video_data(post_data):
    did = post_data["post"]["author"]["did"]
    if hasattr(post_data.post.record.embed, "video"):
        blob_cid = post_data["post"]["record"]["embed"]["video"].ref.link
        alt = post_data["post"]["record"]["embed"]["alt"]
    else:
        blob_cid = post_data["post"]["record"]["embed"]["media"]["video"].ref.link
        alt = post_data["post"]["record"]["embed"]["media"]["alt"]
    url = "https://bsky.social/xrpc/com.atproto.sync.getBlob?did=%s&cid=%s" % (did, blob_cid)
    # Setting alt to empty string if it is noneType
    if not alt:
        alt = ""
    return {"url": url, "alt": alt}
