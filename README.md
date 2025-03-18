The Bluesky Crossposter is a python application that automatically takes post from one service (Bluesky or Mastodon) and posts them to one or more other services (Bluesky, Mastodon and/or Twitter). The application can handle posts, threads, quote posts*, reposts**, deletes, media (including alt text) and privacy settings***

**Quote posts only work fully on your own posts, as other's posts don't necessarily exist on the target service. Otherwise posts will be sent as a post with an included link (if enabled in settings). They also don't work on Mastoon, since Mastodon doesn't have a quote post function, so there they will be converted to replies (if qoute of yourself) or a post with a url (if quote of someone else).*

***Reposts on twitter are disabled by default as this requires the paid version of the API*

****More information futher down.*

# Setup

To get started, make copies of the txt-files in the settings folder with .py file endings. Input the necessary information in each file, most importantly the necessary keys and passwords in auth.py.

In settings.py you can configure the poster to work the way you want it, setting what inputs and outputs to use, how mentions and quote posts are handled etc. Finally set up a way for the code to be run periodically, for example a cronjob running every five or ten minutes.

When first run, or run without a database file, all posts within the timelimit set by postTimeLimit in settings/settings.py will be posted. If you have used a previous version of the crossposter, place database.json-file in the db folder, and it will be converted to the new format upon first run.

## Running with Docker
The included Dockerfile and docker-compose file can be used to run the service in a docker container. Configuration options can be set in the docker-compose file, added to an .env file (see env.example) or injected as environment variables in some other way. An additional configuration option, RUN_INTERVAL, is provided to set the interval in seconds for which to check for new posts.

**NOTE!** Crossposter Mk 3 has not been tested in docker, meaning there might be issues to resolve.

##  Privacy settings

Every service manages post privacy differently. Most notably, Mastodon limits who can view posts, while Bluesky and Twitter limits who can interact. There are several options for privacy settings for posts, with the default being "inherit". When mastodon_visibility and/or allow_reply is set to inherit, the poster will try to translate the settings from the input source to the most closely resembling setting for the output. Exakt behavior can be tweaked in settings. This is the default:

### Bluesky -> Crossposter

| Bluesky       | Crossposter   |
| ------------- | ------------- |
| Everybody     | Public        |
| Nobody        | Mentioned     |
| Followers     | Followers     |
| Following     | Following     |
| Mentioned     | Mentioned     |

### Mastodon -> Crossposter

| Mastodon      | Crossposter   |
| ------------- | ------------- |
| Public        | Public        |
| Direct        | Mentioned     |
| Private       | Followers     |
| Unlisted      | Unlisted      |
| Following     | Following     |


### Crossposter -> Outputs

| Crossposter   | Mastodon      | Twitter       | Bluesky       |
| ------------- | ------------- | ------------- | ------------- |
| Public        | Public        | Everybody     | Everybody     |
| Following     | Private       | Following     | Following     |
| Followers     | Private       | Following     | Following*    |
| Unlisted      | Unlisted      | Following     | Following     |
| Mentioned     | Mentioned     | Mentioned     | Mentioned     |


*Though Bluesky has a setting for only letting followers reply, it can for some reason not be set using the API. Keeping the option in case this changes.


-----
