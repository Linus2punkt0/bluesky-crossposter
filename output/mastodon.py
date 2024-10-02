from mastodon import Mastodon
from loguru import logger
from settings import settings
from settings.auth import *


if settings.Mastodon:
    mastodon = Mastodon(
        access_token = MASTODON_TOKEN,
        api_base_url = MASTODON_INSTANCE
    )

# More or less the exact same function as for tweeting, but for tooting.
def toot(post, reply_to_post, quoted_post, media, visibility = "unlisted"):
    # Since mastodon does not have a quote repost function, quote posts are turned into replies. If the post is both
    # a reply and a quote post, the quote is replaced with a url to the post quoted.
    if reply_to_post is None and quoted_post:
        reply_to_post = quoted_post
    elif reply_to_post is not None and quoted_post:
        post_url = MASTODON_INSTANCE + "@" + MASTODON_HANDLE + "/" + str(quoted_post)
        post += "\n" + post_url
    media_ids = []
    # If post includes images, images are uploaded so that they can be included in the toot
    if media:
        for item in media:
            # If alt text was added to the image on bluesky, it's also added to the image on mastodon,
            # otherwise it will be uploaded without alt text.
            if item["alt"]:
                logger.info("Uploading media " + item["filename"] + " with alt: " + item["alt"] + " to mastodon")
                res = mastodon.media_post(item["filename"], description=item["alt"], synchronous=True)
            else:
                logger.info("Uploading media " + item["filename"])
                res = mastodon.media_post(item["filename"], synchronous=True)
            media_ids.append(res.id)
        media_ids.append(res.id)
    a = mastodon.status_post(post, in_reply_to_id=reply_to_post, media_ids=media_ids, visibility=visibility)
    logger.info("Posted to mastodon")
    id = a["id"]
    return id

def retoot(toot_id):
    mastodon.status_reblog(toot_id)
    logger.info("Boosted toot " + str(toot_id))