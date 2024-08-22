# Mk 2

Version 2 of the crossposter has now been released. The new version contains a bunch of new options, along with fixes and restructuring. To start using the new version I recommend making a new, separate installation and transferring your settings and database to the new version. 

New functions include:
- Reposting your own posts (only works on Mastodon unless you pay for a higher level of twitters API)
- Quote posts of other people's posts, with their posts included as a link to Bluesky (can be toggled on/off in settings and automatically skips posts from users whos posts are not public).
- Username handling allows you to either skip posts where you mention another Bluesky user, or cleanup of username so that they are not interpreted as users after being crossposted.
- Limiting posts per hour, either skipping posts that go over the posts per hour limit, or sending them at a later time.

# bluesky-crossposter

The Bluesky Crossposter is a python script that when running will automatically post your bluesky-posts to mastodon and twitter, excluding responses and reposts. The script can handle threads, quote posts of your own posts, and image posts, including alt text on images. 

To get started, get the necessary keys and passwords and enter them in settings/auth.py. Then fill in your paths in settings/path.py. Finally set up a way for the code to be run periodically, for example a cronjob running every five or ten minutes.

When first run, or run without a database file, all posts within the timelimit set by postTimeLimit in settings/settings.py will be posted.

In the settings.py you can also disable posting to twitter or mastodon if you only want to post to one of them. Just change "True" to "False" for the service you want to disable. You can also disable logging if you have limited space where the program will run.

The file settings.py now also allows (mis)using blueskys language function by designating a language that when set can be used to decide if a specific post should or should not be crossposted. More info can be found in the file.

## Running with Docker
The included Dockerfile and docker-compose file can be used to run the service in a docker container. Configuration options can be set in the docker-compose file, added to an .env file (see env.example) or injected as environment variables in some other way. An additional configuration option, RUN_INTERVAL, is provided to set the interval in seconds for which to check for new posts.

Bluesky Crossposter™©® developed by denvitadrogen
