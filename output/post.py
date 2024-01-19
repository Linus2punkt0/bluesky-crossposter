import random, string, urllib, arrow
from settings import settings 
from settings.paths import *
from local.functions import write_log
from local.db import db_write
from output.twitter import tweet, retweet
from output.mastodon import toot, retoot


def post(posts, database, post_cache):
    # The updates status is set to false until anything has been altered in the databse. If nothing has been posted in a run, we skip resaving the database.
    updates = False
    # Running through the posts dictionary reversed, to get oldest posts first.
    for cid in reversed(list(posts.keys())):
        post = posts[cid]
        # Checking if a maximum amount of posts per hour is set, and if so if it has been reached.
        if settings.max_per_hour != 0 and len(post_cache) >= settings.max_per_hour:
            write_log("Max posts per hour reached.")
            break
        # If a post is posted, we want to add a timestamp to the post_cache. Since there are several
        # reasons why a post might not be posted, we start out with this set to false for each post,
        # and change it to true if a post is actually sent.
        posted = False
        # Checking if the post is already in the database, and in that case getting the IDs for the post
        # on twitter and mastodon. If one or both of these IDs are empty, post will be sent.
        # Also checking the existing fail count against the max_retries set in settings, to avoid
        # retrying a failure so much that the poster gets ratelimited
        tweet_id = ""
        toot_id = ""
        t_fail = 0
        m_fail = 0
        if cid in database:
            tweet_id = database[cid]["ids"]["twitter_id"]
            toot_id = database[cid]["ids"]["mastodon_id"]
            t_fail = database[cid]["failed"]["twitter"]
            m_fail = database[cid]["failed"]["mastodon"]
        if m_fail >= settings.max_retries:
            write_log("Error limit reached, not posting to Mastodon", "error")
            if not toot_id:
                updates = True
                toot_id = "FailedToPost"
        if t_fail >= settings.max_retries:
            write_log("Error limit reached, not posting to Twitter", "error")
            if not tweet_id:
                updates = True
                tweet_id = "FailedToPost"
        text = post["text"]
        reply_to_post = post["reply_to_post"]
        quoted_post = post["quoted_post"]
        quote_url = post["quote_url"]
        images = post["images"]
        visibility = post["visibility"]
        allowed_reply = post["allowed_reply"]
        tweet_reply = ""
        toot_reply = ""
        tweet_quote = ""
        toot_quote = ""
        # If the post has already been sent to both twitter and mastodon and is not a repost, no
        # further action is needed.
        if tweet_id and toot_id and not post["repost"]:
            continue
        # If a retweet is found within the last hour, we check the cache to see if it has already been retweeted
        repost_timelimit = arrow.utcnow().shift(hours = -1)
        if cid in post_cache:
            repost_timelimit = post_cache[cid]
        # If it is a reply, we get the IDs of the posts we want to reply to from the database.
        # If post is not found in database, we can't continue the thread on mastodon and twitter,
        # and so we skip it.
        if reply_to_post in database:
            tweet_reply = database[reply_to_post]["ids"]["twitter_id"]
            toot_reply = database[reply_to_post]["ids"]["mastodon_id"]
        elif reply_to_post and reply_to_post not in database:
            write_log("Post " + cid + " was a reply to a post that is not in the database.", "error")
            continue
        # If post is a quote post we get the IDs of the posts we want to quote from the database.
        # If the posts are not found in the database we check if the quote_post setting is true or false in settings.
        # If true we add the URL of the bluesky post to the text of the post, if false we skip the post.
        if quoted_post in database:
            tweet_quote = database[quoted_post]["ids"]["twitter_id"]
            toot_quote = database[quoted_post]["ids"]["mastodon_id"]
        elif quoted_post and quoted_post not in database:
            if settings.quote_posts and quote_url not in text:
                text += "\n" + quote_url
            elif not settings.quote_posts:
                write_log("Post " + cid + " was a quote of a post that is not in the database.", "error")
                continue
        # In case the tweet or toot reply/quote variables are empty, we set them to None, to make sure they are in the correct format for 
        # the api requests. This is not necessary for the toot_quote variable, as it is not sent as a parameter in itself anyway.
        if not tweet_reply:
            tweet_reply = None
        if not toot_reply:
            toot_reply = None
        if not tweet_quote:
            tweet_quote = None
        # If either tweet or toot has not previously been posted, we download images (given the post includes images).
        if images and (not tweet_id or not toot_id):
            images = get_images(images)
        # If mastodon is set to false, the post is not sent to mastodon.
        if not post["twitter"]:
            toot_id = "skipped"
            write_log("Not posting to Twitter because posting was set to false.")
        elif tweet_id and not post["repost"]:
            write_log("Post " + cid + " already sent to twitter.")
        # if the post already exists and is a repost, we check if it has already been reposted, and if not, repost it.
        elif tweet_id and post["repost"] and post["timestamp"] > repost_timelimit:
            try:
                # This is where retweets would go if they weren't locked behind a paywall.
                pass
                # retweet(tweet_id)
                # posted = True
            except Exception as error:
                write_log(error, "error")
        # Trying to post to twitter and mastodon. If posting fails the post ID for each service is set to an
        # empty string, letting the code know it should try again next time the code is run.
        elif not tweet_id and tweet_reply != "skipped" and tweet_reply != "FailedToPost":
            updates = True
            try:
                tweet_id = tweet(text, tweet_reply, tweet_quote, images, allowed_reply)
                posted = True
            except Exception as error:
                write_log(error, "error")
                t_fail += 1
                tweet_id = ""
                # If a tweet failes as a duplicate post, we don't want to try sending it again.
                if "duplicate content" in str(error):
                    t_fail = settings.max_retries
                    tweet_id = "duplicate"
        else:
            write_log("Not posting " + cid + " to Twitter")
        # If mastodon is set to false, the post is not sent to mastodon.
        if not post["mastodon"]:
            toot_id = "skipped"
            write_log("Not posting to Mastodon because posting was set to false.")
        elif toot_id and not post["repost"]:
            write_log("Post " + cid + " already sent to mastodon.")
        # if the post already exists and is a repost, we check if it has already been reposted, and if not, repost it.
        elif toot_id and post["repost"] and post["timestamp"] > repost_timelimit:
            try:
                retoot(toot_id)
                posted = True
            except Exception as error:
                write_log(error, "error")
        # Mastodon does not have a quote retweet function, so those will just be sent as replies.
        elif not toot_id and toot_reply != "skipped" and toot_reply != "FailedToPost":
            updates = True
            try:
                toot_id = toot(text, toot_reply, toot_quote, images, visibility)
                posted = True
            except Exception as error:
                write_log(error, "error")
                m_fail += 1
                toot_id = ""
        else:
            write_log("Not posting " + cid + " to Mastodon")
        # Saving post to database
        database = db_write(cid, tweet_id, toot_id, {"twitter": t_fail, "mastodon": m_fail}, database)
        if posted:
            post_cache[cid] = arrow.utcnow()
    return updates, database, post_cache

# Function for getting included images. If no images are included, an empty list will be returned, 
# and the posting functions will know not to include any images.
def get_images(images):
    local_images = []
    for image in images:
        # Getting alt text for image. If there is none this will be an empty string.
        alt = image["alt"]
        # Giving the image just a random filename
        filename = ''.join(random.choice(string.ascii_lowercase) for i in range(10)) + ".jpg"
        filename = image_path + filename
        # Downloading fullsize version of image
        urllib.request.urlretrieve(image["url"], filename)
        # Saving image info in a dictionary and adding it to the list.
        image_info = {
            "filename": filename,
            "alt": alt
        }
        local_images.append(image_info)
    return local_images