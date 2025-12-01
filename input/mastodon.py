import arrow, html, re
import settings.settings as settings
from main.functions import logger, extract_urls, clean_html
from main.connections import mastodon_connect
from main.post import Post
from main.db import database


def get_posts():
    logger.info("Gathering posts from Mastodon")
    posts = []
    mastodon = mastodon_connect()
    user_id = mastodon.me()["id"]
    statuses = mastodon.account_statuses(user_id)
    for status in statuses:
        logger.trace(status)
        post_id = str(status.id)
        # If post is a reply and the reply is to another account, it will not be crossposted. Same if it is a repost of a post from another account.
        if (status.in_reply_to_account_id and status.in_reply_to_account_id != user_id) or (status.reblog and status.reblog.account.id != user_id):
            logger.info(f'Post {post_id} is a reply to or reblog of another account.')
            continue
        created_at = arrow.get(status.created_at)
        # Checking if post is outside time limit
        if not created_at > database.get_post_time_limit():
            logger.info(f'Post {post_id} posted outside time limit.')
            continue
        # Checking if the status has already been posted to all required services (as well as adding it to the database)
        if database.posted(post_id) and not status.reblog:
            logger.info(f'Post {post_id} already posted to all required services')
            continue
        # Checking if this is a repost of a post that can't be reposted because it has previously failed of been skipped
        if status.reblog and database.not_posted(post_id):
            logger.info(f'Post {post_id} is a repost of a post that has previously failed or been skipped.')
            continue
        if status.mentions and settings.mentions == "skip":
            logger.info(f'post {post_id} mentions a user, crossposter has been set to skip posts including mentions.')
            continue
        elif status.mentions:
            text, urls = parse_mentioned_users(status.mentions, text, urls)
        logger.debug(status)
        # Getting text content and converting it from html to a regular string
        text = ""
        urls = []
        if status.content:
            # Removing paragraph end tag from post to avoid trailing newlines
            text = re.sub('</p>$', "", status.content)
            # Using replace to retain newlines before removing all other html
            text = text.replace("<p>", "").replace("</p>", "\n\n").replace("<br />", "\n")
            text = clean_html(text)
            text = html.unescape(text)
            # Extracting URLs from status
            urls = extract_urls(text)
        # Getting media items and tags from post
        media = {}
        tags = []
        if status.tags:
            for tag in status.tags:
                tags.append(tag.name)
        if status.media_attachments:
            items = []
            for item in status.media_attachments:
                media["type"] = item.type
                items.append({"url": item.url, "alt": item.description})
            media["items"] = items
        post_info = {
            "post_id": post_id,
            "text": text,
            "urls": urls,
            "tags": tags,
            "reply_id": status.in_reply_to_id,
            # Quote posts are not applicable for mastodon
            "quote_id": None,
            "quote_url": None,
            "media": media,
            "sensitive": status.sensitive,
            "privacy": get_privacy(status.visibility),
            "language": [status.language],
            "repost": (status.reblog),
            "created_at": created_at
        }
        posts.append(post_info)
    # Sorting posts by creation date
    posts = sorted(posts, key=lambda d: d['created_at'])
    post_dict = {}
    # Creating post objects and placing in a dict
    for post in posts:
        post_dict[post["post_id"]] = Post(post)
    return post_dict


# Changing usernames in post according to settings
def parse_mentioned_users(mentioned, text, urls):
    users = []
    for user in mentioned:
        # Adding username to user-array
        if settings.mastodon_mentions == "username":
            users.append(f"@{user.username}")
        # Replacing username with account name and adding to user array
        if settings.mastodon_mentions == "account":
            users.append(f"@{user.acct}")
            text = text.replace(f"@{user.username}", f"@{user.acct}")
        # Replacing username with url and adding url to user and url array
        if settings.mentions == "url":
            users.append(user.url)
            urls.append(user.url)
            text = text.replace(f"@{user.username}", f"{user.url}")
    # Removing leading @ in username/account name
    if settings.mentions == "strip":
        for user in users:
            text = text.replace(user, user.replace("@", "", 1))
    return text, urls


# Translating visibility settings to crossposter privacy settings. More info in readme
def get_privacy(visibility):
    if visibility == "direct":
        return "mentioned"
    elif visibility == "private":
        return "followers"
    elif visibility == "unlisted":
        return "unlisted"
    elif visibility == "public":
        return "public"
    else:
        logger.error("Couldn't parse privacy settings, setting it to public.")
        logger.debug(visibility)
        return "public"