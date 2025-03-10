import os

# Enables/disables crossposting to twitter and mastodon
# Accepted values: True, False
Twitter = True
Mastodon = True
# visibility sets what visibility should be used when posting to Mastodon. Options are "public" for always public, "unlisted" for always unlisted,
# "private" for always private and "hybrid" for all posts public except responses in threads (meaning first post in a thread is public and the rest unlisted).
# Accepted values: public, private, hybrid
visibility = "hybrid"
# mentions set what is to be done with posts containing a mention of another user. Options are "ignore",
# for crossposting with no change, "skip" for skipping posts with mentions, "strip" for removing
# the starting @ of a username and "url" to replace the username with a link to their bluesky profile.
# Accepted values: ignore, skip, strip, url
mentions = "strip"
# post_default sets default posting mode. True means all posts will be crossposted unless otherwise specified,
# False means no posts will be crossposted unless explicitly specified. If no toggle (below) is specified
# post_default will be treated as True no matter what is set.
# Accepted values: True, False
post_default = True
# The function to select what posts are crossposted (mis)uses the language function in Bluesky.
# Enter a language here and all posts will be filtered based on if that language is included 
# in the post. 
# E.g. if you set post_default to True and add German ("de") as post toggle, all posts including
# German as a language will be skipped. If post_default is set to False, only posts including
# german will be crossposted. You can use different languages as selectors for Mastodon
# and Twitter. You can have both the actual language of the tweet, and the selector language
# added to the tweet and it will still work.
# Accepted values: Any language tag in quotes (https://en.wikipedia.org/wiki/IETF_language_tag)
mastodon_lang = ""
twitter_lang = ""
# quote_posts determines if quote reposts of other users' posts should be crossposted with the quoted post included as a link. If False these posts will be ignored.
quote_posts = True
# max_retries sets maximum amount of times poster will retry a failed crosspost.
# Accepted values: Integers greater than 0
max_retries = 5
# post_time_limit sets max time limit (in hours) for fetching posts. If no database exists, all posts within this time 
# period will be posted.
# Accepted values: Integers greater than 0
post_time_limit = 12
# max_per_hour limits the amount of posts that can be crossposted withing an hour. 0 means no limit.
# Accepted values: Any integer
max_per_hour = 0
# overflow_posts determines what happens to posts that are not crossposted due to the hourly limit.
# If set to "retry" the poster will attempt to send them again when posts per hour are below the limit.
# If set to "skip" the posts will be skipped and the poster will instead continue on with new posts.
# Accepted values: retry, skip
overflow_posts = "retry"
# If cross_delete is set to true, posts you delete from bluesky within one our of being crossposted will also be deleted from mastodon and twitter
cross_delete = True
# Setting a buffer to avoid exceeding the rate limit. The limit is set in percent, and when the ratelimit-remaining reaches
# x percent of ratelimit-limit the crossposter will pause until the ratelimit-reset.
rate_limit_buffer = 10
# Sets minimum log level i Loguru logger
log_level = "INFO"


# Override settings with environment variables if they exist
Twitter = os.environ.get('TWITTER_CROSSPOSTING').lower() == 'true' if os.environ.get('TWITTER_CROSSPOSTING') else Twitter
Mastodon = os.environ.get('MASTODON_CROSSPOSTING').lower() == 'true' if os.environ.get('MASTODON_CROSSPOSTING') else Mastodon
log_level = os.environ.get('LOG_LEVEL').lower() == 'true' if os.environ.get('LOG_LEVEL') else log_level
visibility = os.environ.get('MASTODON_VISIBILITY') if os.environ.get('MASTODON_VISIBILITY') else visibility
mentions = os.environ.get('MENTIONS') if os.environ.get('MENTIONS') else mentions
post_default = os.environ.get('POST_DEFAULT').lower() == 'true' if os.environ.get('POST_DEFAULT') else post_default
mastodon_lang = os.environ.get('MASTODON_LANG') if os.environ.get('MASTODON_LANG') else mastodon_lang
twitter_lang = os.environ.get('TWITTER_LANG') if os.environ.get('TWITTER_LANG') else twitter_lang
quote_posts = os.environ.get('QUOTE_POSTS') if os.environ.get('QUOTE_POSTS') else quote_posts
max_retries = int(os.environ.get('MAX_RETRIES')) if os.environ.get('MAX_RETRIES') else max_retries
post_time_limit = int(os.environ.get('POST_TIME_LIMIT')) if os.environ.get('POST_TIME_LIMIT') else post_time_limit
max_per_hour = int(os.environ.get('MAX_PER_HOUR')) if os.environ.get('MAX_PER_HOUR') else max_per_hour
overflow_posts = os.environ.get('OVERFLOW_POST') if os.environ.get('OVERFLOW_POST') else overflow_posts
rate_limit_buffer = int(os.environ.get('RATE_LIMIT_BUFFER')) if os.environ.get('RATE_LIMIT_BUFFER') else rate_limit_buffer
log_level = os.environ.get('LOG_LEVEL') if os.environ.get('LOG_LEVEL') else log_level
cross_delete = os.environ.get('CROSS_DELETE') if os.environ.get('CROSS_DELETE') else cross_delete