from mastodon import Mastodon
from settings import settings
from settings.auth import *
from local.functions import write_log

if settings.Mastodon:
    mastodon = Mastodon(
        access_token = MASTODON_TOKEN,
        api_base_url = MASTODON_INSTANCE
    )

# More or less the exact same function as for tweeting, but for tooting.
def toot(post, reply_to_post, quoted_post, images, visibility = "unlisted"):
    # Since mastodon does not have a quote repost function, quote posts are turned into replies. If the post is both
    # a reply and a quote post, the quote is replaced with a url to the post quoted.
    if reply_to_post is None and quoted_post:
        reply_to_post = quoted_post
    elif reply_to_post is not None and quoted_post:
        post_url = MASTODON_INSTANCE + "@" + MASTODON_USER + "/" + str(quoted_post)
        post += "\n" + post_url
    media_ids = []
    # If post includes images, images are uploaded so that they can be included in the toot
    if images:
        for image in images:
            filename = image["filename"]
            alt = image["alt"]
            # If alt text was added to the image on bluesky, it's also added to the image on mastodon,
            # otherwise it will be uploaded without alt text.
            if alt:
                write_log("Uploading image " + filename + " with alt: " + alt + " to mastodon")
                res = mastodon.media_post(filename, description=alt)
            else:
                write_log("Uploading image " + filename)
                res = mastodon.media_post(filename)
            media_ids.append(res.id)
    # I wanted to make this part a little neater, but didn't get it to work and gave up. So here we are.
    # If post is both reply and has images it is posted as both a reply and with images (duh). 
    # If just either of the two it is posted with just that, and if neither it is just posted as a text post.
    a = mastodon.status_post(post, in_reply_to_id=reply_to_post, media_ids=media_ids, visibility=visibility)
    write_log("Posted to mastodon")
    id = a["id"]
    return id

def retoot(toot_id):
    mastodon.status_reblog(toot_id)
    write_log("Boosted toot " + str(toot_id))