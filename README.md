# bluesky-crossposter

The Bluesky Crossposter is a python script that when running will automatically post your bluesky-posts to mastodon and twitter, excluding responses and reposts. The script can handle threads, quote posts of your own posts, and image posts, including alt text on images. 

To get started, get the necessary keys and passwords and enter them in auth.py. Then fill in your paths in path.py. Finally set up a way for the code to be run periodically, for example a cronjob running every five or ten minutes.

When first run, or run without a database file, all posts within the timelimit set by postTimeLimit in settings.py will be posted.

In the settings.py you can also disable posting to twitter or mastodon if you only want to post to one of them. Just change "True" to "False" for the service you want to disable. You can also disable logging if you have limited space where the program will run.

The file settings.py now also allows (mis)using blueskys language function by designating a language that when set can be used to decide if a specific post should or should not be crossposted. More info can be found in the file.

Bluesky Crossposter™©® developed by denvitadrogen
