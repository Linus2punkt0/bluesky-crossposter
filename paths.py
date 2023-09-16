# This file contains all necessary file and folder paths. Make sure to end folder paths with "/".

# basePath is the path from root to he lowest common denominator for all of the other paths.
# Using an absolute path is especially important if running via cron.
basePath = "/"
# Path to the database file. If you want it somewhere other than directly in the base path you can 
# either write the entire path manually, or just add the rest of the path on top of the basePath.
databasePath = basePath + "db/" + "database.json"
# Path to backup of database.
backupPath = basePath + "db/" + "database.bak"
# Path for storing logs
logPath = basePath + "logs/"
# Path to folder for temporary storage of images
imagePath = basePath + "images/"