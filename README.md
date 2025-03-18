# Mk3 in beta

Crossposter Mk3 is now in beta. You can find it in the branch poster-mk3 if you wish to try it out. I highly recommend setting up a new folder and migrating a copy of your database over, and not updating in your current running folder, as the database will be formatted, and issues could cause it to be corrupted. 

The new version allows for Mastodon to be used as input and Bluesky as output, among other changes. The new format will make it easier to add new inputs and outputs in the future.

# Update Spring 2025

A new version of the poster is coming up, and in preparation removing the settings-files from the repo and replacing them with txt-versions, so as not to overwrite user settings on update. The new version will be launched in a beta branch, and for those wanting to try it out (and later anyone upgrading) I recommend cloning a whole new version of the poster and moving copies of the database and settings into that one.

# Update Fall 2024

New functionality has been added over the fall, including functionality to handle Blueskys new video functions. Another new function is cross-deletion, meaning if you delete a post within one hour of posting it on Bluesky, it will also be deleted on the other platforms. This function can be disabled in settings by setting cross_delete to False.

This will probably be the last update for a while, except for some bug fixes if needed. Before further updates the poster would probably need some major rewrites to make it be less of a mess.

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
