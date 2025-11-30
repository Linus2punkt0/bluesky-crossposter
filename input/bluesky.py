import arrow, fnmatch, re
from main.functions import logger
from settings.auth import BSKY_HANDLE
from settings.paths import *
from settings import settings
from main.connections import bsky_connect
from main.post import Post
from main.db import database
# Getting posts from bluesky



def get_posts():
    bsky = bsky_connect()
    logger.info("Gathering posts from Bluesky")
    posts = []
    # Getting feed of user
    profile_feed = bsky.app.bsky.feed.get_author_feed({'actor': BSKY_HANDLE})
    for status in profile_feed.feed:
        logger.trace(status)
        post_id = status.post.cid
        uri = status.post.uri
        # If the post was not written by the account that posted it, it is a repost from another account and is skipped.
        if status.post.author.handle != BSKY_HANDLE:
            logger.info(f'Post {post_id} is a repost of another account: ({status.post.author.handle}).')
            continue
        # Checking if the post has "indexe_at" set, meaning it is a repost.
        repost = False
        created_at = get_date(status.post.record.created_at.split(".")[0])
        logger.debug(f'Post created at: {created_at}')
        if hasattr(status.reason, "indexed_at"):
            repost = True
            created_at = get_date(status.reason.indexed_at.split(".")[0])
        # Checking if post is outside time limit
        if not created_at > database.get_post_time_limit():
            logger.info(f'Post {post_id} posted outside time limit.')
            continue
        # Checking if the status has already been posted to all required services (as well as adding it to the database)
        if database.posted(post_id, uri = uri) and not repost:
            logger.info(f'Post {post_id} already posted to all required services')
            continue
        # Checking if this is a repost of a post that can't be reposted because it has previously failed of been skipped
        if repost and database.not_posted(post_id):
            logger.info(f'Post {post_id} is a repost of a post that has previously failed or been skipped.')
            continue
        logger.debug(status)
        # Facets contains things like urls and mentions, which need to be deal with.
        # send_mention is used to keep track of if the mention-settings says for the post to be posted or not.
        # Default is True, because if nobody is mentioned it should be posted.
        text = status.post.record.text
        mentioned_users = []
        urls = []
        tags = []
        media = {}
        if status.post.record.facets:
            # Sometimes bluesky shortens URLs and in that case they need to be restored before crossposting
            # (Also using this function to fetch hashtags)
            text, urls, tags = restore_urls(status.post.record)
            # Retrieving list of mentioned users
            mentioned_users, text, urls = parse_facets(status.post.record, text, urls)
        # Sometimes posts have included links that are not included in the actual text of the post. This adds adds that back.
        if status.post.embed and hasattr(status.post.embed, "external") and hasattr(status.post.embed.external, "uri") and status.post.embed.external.uri not in text:
            # Checking if the url is from media tenor, then it is to be treated as media instead of as a link.
            if fnmatch.fnmatch(status.post.embed.external.uri, "*media.tenor.com*.gif*"): 
                logger.info("Found media from Media Tenor, adding to media items.")
                media = {
                "type": "image",
                "items": [{"url": status.post.embed.external.uri, "alt": re.sub("^Alt: ", "", status.post.embed.external.description, flags=re.I)}]
                }
            else:
                logger.info(f"Restoring url {status.post.embed.external.uri} in post.")
                text += '\n'+status.post.embed.external.uri
                urls.append(status.post.embed.external.uri)
        if mentioned_users and settings.mentions == "skip":
            logger.info(f'post {post_id} mentions a user, crossposter has been set to skip posts including mentions.')
            continue
        # Setting reply_to_user to the same as user handle and only changing it if the post is an actual reply.
        # Later a check is performed to if the variable is the same as the user handle, so only
        # posts that are not replies, and posts that are part of a thread are posted.
        reply_to_user = BSKY_HANDLE
        reply_id = ""
        # Checking if post is regular reply
        if status.post.record.reply:
            reply_id = status.post.record.reply.parent.cid
            # Poster will try to fetch reply to-username the "ordinary" way, 
            # and if it fails, it will try getting the entire thread and
            # finding it that way
            try:
                reply_to_user = status.reply.parent.author.handle
            except:
                reply_to_user = bsky.get_reply_to_user(status.post.record.reply.parent)
        # If post is a reply to another user, it is skipped
        if reply_to_user != BSKY_HANDLE:
            logger.info(f"Post {post_id} is a reply to another account ({reply_to_user}).")
            continue
        quoted_id = ""
        quote_url = ""
        # Checking if post is a quote post. Posts with references to feeds look like quote posts but aren't, and so will fail on missing attribute.
        # Since quote posts can give values in two different ways it's a bit of a hassle to double check if it is an actual quote post,
        # so instead I just try to run the function and if it fails I skip the post
        # If there is some reason you would want to crosspost a post referencing a bluesky-feed that I'm not seeing, I might update this in the future.
        if status.post.embed and hasattr(status.post.embed, "record"):
            try:
                quoted_user, quoted_id, quote_url, open = get_quote_post(status.post.embed.record)
            except:
                logger.debug(status)
                logger.info(f"Could not get post quoted in {post_id}")
                continue
            # If post is a quote post of a post from another user, and quote-posting is disabled in settings
            # or the post is not open to users not logged in, the post will be skipped
            if quoted_user != BSKY_HANDLE and (not settings.quote_posts or not open):
                continue
            # If the post is a quote of user account, the url to the post is removed (if it was included).
            # instead the version of the post from twitter or mastodon will be referenced.
            elif quoted_user == BSKY_HANDLE:
                text = text.replace(quote_url, "")
        # Checking who is allowed to reply to the post
        privacy_setting = get_privacy(status.post.threadgate)
        # Fetching images and video if there are any in the post
        image_data = ""
        video_data = {}
        if status.post.embed and hasattr(status.post.embed, "images"):
            image_data = status.post.embed.images
        elif status.post.embed and hasattr(status.post.embed, "media") and hasattr(status.post.embed.media, "images"):
            image_data = status.post.embed.media.images
        elif  status.post.record.embed and (hasattr(status.post.record.embed, "video") \
            or (hasattr(status.post.record.embed, "media") and hasattr(status.post.record.embed.media, "video"))):
            video_data = get_video_data(status)
            media = {
                "type": "video",
                "items": [video_data]
            }
            logger.debug(f"Found video: {video_data}")
        if image_data:
            images = []
            for image in image_data:
                images.append({"url": image.fullsize, "alt": image.alt})
            media = {
                "type": "image",
                "items": images
            }
        post_info = {
            "post_id": post_id,
            "text": text,
            "urls": urls,
            "tags": tags,
            "reply_id": reply_id,
            "quote_id": quoted_id,
            "quote_url": quote_url,
            "media": media,
            "language": status.post.record.langs,
            "privacy": privacy_setting,
            "repost": repost,
            "created_at": created_at
        }
        logger.debug(post_info)
        posts.append(post_info)
    posts = sorted(posts, key=lambda d: d['created_at'])
    post_dict = {}
    for post in posts:
        post_dict[post["post_id"]] = Post(post)
    return post_dict


# Sometimes the date string is given in a different format, this is dealt with here.
def get_date(date_string):
    date_in_format = 'YYYY-MM-DDTHH:mm:ss'
    try:
        date = arrow.get(date_string, date_in_format)
    except:
        date = arrow.get(date_string, date_in_format+"ZZ")
    return date


def get_privacy(threadgate):
        if threadgate is None:
            return "public"
        if not threadgate.record.allow or len(threadgate.record.allow) == 0:
            return "mentioned"
        # For some reason the threadgate rule is not always stored the same way, because of course it's not.
        try:
            threadgate_type = threadgate.record.allow[0]["$type"]
        except:
            threadgate_type = threadgate.record.allow[0].py_type
        if threadgate_type == "app.bsky.feed.threadgate#followerRule":
            return "followers"
        elif threadgate_type == "app.bsky.feed.threadgate#followingRule":
            return "following"
        elif threadgate_type == "app.bsky.feed.threadgate#mentionRule":
            return "mentioned"
        else:
            logger.error("Couldn't parse privacy settings, setting it to public.")
            logger.debug(threadgate)
            return "public"


# Function for restoring shortened URLS
def restore_urls(record):
    urls = []
    tags = []
    text = record.text
    encoded_text = text.encode("UTF-8")
    for facet in record.facets:
        if facet.features[0].py_type == "app.bsky.richtext.facet#tag":
            tags.append(facet.features[0].tag)
        if facet.features[0].py_type != "app.bsky.richtext.facet#link":
            continue
        url = facet.features[0].uri
        urls.append(url)
        # The index section designates where a URL starts end ends. Using this the exact
        # string representing the URL in the post can be identified, and replace it with the actual URL.
        start = facet.index.byte_start
        end = facet.index.byte_end
        section = encoded_text[start:end]
        shortened = section.decode("UTF-8")
        text = text.replace(shortened, url)
    return text, urls, tags

# Function for retrieving users and urls from facets, and converting the user to whatever format is selected in settings
def parse_facets(record, text, urls):
    users = []
    encoded_text = text.encode("UTF-8")
    for facet in record.facets:
        if facet.features[0].py_type != "app.bsky.richtext.facet#mention":
            continue
        # The index section designates where a username starts end ends. Using this the exact
        # string representing the user in the post can be identified, and replace it with the corrected value
        start = facet.index.byte_start
        end = facet.index.byte_end
        username = encoded_text[start:end]
        username = username.decode("UTF-8")
        # Removing @ in the beginning of username if mentions are set to "strip"
        if settings.mentions == "strip":
            text = text.replace(username, username.replace("@", ""))
        # Switching out username for url to user if mentions are set to "url"
        if settings.mentions == "url":
            base_url = "https://bsky.app/profile/"
            did = facet.features[0].did
            url = base_url + did
            urls.append(url)
            text = text.replace(username, url)
            username = url
        users.append(username)
    return users, text, urls


# Quoted posts can be stored in several different ways for some reason. 
# This function checks which one is used and fetches information accordingly.
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
    # who are not logged in. Only publicly available posts are crossposted.
    if labels and labels[0].val == "!no-unauthenticated":
        open = False
    url = "https://bsky.app/profile/" + user + "/post/" + uri.split("/")[-1]
    return user, cid, url, open

# Fetching video data
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