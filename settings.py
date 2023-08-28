# Enables/disables crossposting to twitter and mastodon
# Accepted values: True, False
Twitter = True
Mastodon = True
# Enables/disables logging
# Accepted values: True, False
Logging = True
# Sets default posting mode. True means all posts will be crossposted unless otherwise specified,
# False means no posts will be crossposted unless explicitly specified. If no toggle (below) is specified
# postDefault will be treated as True no matter what is set.
# Accepted values: True, False
postDefault = True
# The function to select what posts are crossposted (mis)uses the language function in Bluesky.
# Enter a language here and all posts will be filtered based on if that language is included 
# in the post. 
# E.g. if you set postDefault to True and add German ("de") as post toggle, all posts including
# German as a language will be skipped. If postDefault is set to False, only posts including
# german will be crossposted. You can use different languages as selectors for Mastodon
# and Twitter. You can have both the actual language of the tweet, and the selector language
# added to the tweet and it will still work.
# Accepted values: Any language tag in quotes (https://en.wikipedia.org/wiki/IETF_language_tag)
mastodonLang = ""
twitterLang = ""
# Sets maximum amount of times poster will retry a failed crosspost.
maxRetries = 5
