#!/usr/bin/env python

import os
import shutil
import subprocess

# global variables
SYNC_DIRS = [
   {
      'src' : "", #directory source files on your system
      'dst' : "", #destination directory on gdrive
      'log' : "./sync_log.txt",
      'repo': "" #your gdrive name from rclone configuration
   }
]
RCLONE_RETRIES = 3
RCLONE_CHECKERS = 4
RCLONE_TRANFERS = 4
RCLONE_STATS_INTERVAL = '10s'
RCLONE_CHUNK_SIZE = '128M'
RCLONE_UPLOAD_CUTOFF = '512M'

#
# Synchronize each directory to Google Drive
#
for sync_entry in SYNC_DIRS:
   #
   # Backup the previous sync log file
   #
   log_file = sync_entry['log']
   if os.path.isfile(log_file):
      shutil.move(log_file, log_file + ".BAK")

   #
   # Sync the next directory to Google Drive.
   #
   # Use the rclone 'copy' command instead of 'sync'
   # to prevent accidental deletion on the remote if
   # the source directory is not mounted.
   #
   # A 64M chunk-size is used for performance purposes.
   # Google recommends as large a chunk size as possible.
   # Rclone will use the following amount of RAM at run-time
   # (8MB chunks by default; not high enough)...
   #
   #    RAM = (chunk-size * num-transfers)
   #
   # So our command will use larger chunk sizes (more RAM)...
   #
   #    RAM = 0.5 GB = (64MB * 8 transfers)
   #
   # For more details...
   #
   #    https://github.com/ncw/rclone/issues/397
   #

   # build the shell command
   cmd = """rclone --verbose \
         --retries {retries} \
         --checkers {checkers} \
         --transfers {transfers} \
         --stats {stats_interval} \
         --drive-chunk-size {chunk_size} \
         --drive-upload-cutoff {upload_cutoff} \
         copy --no-update-modtime {src} {repo}:{dst} 2>&1 | tee -a {log_file}"""

   # build the command arg values
   args = {
      'retries': RCLONE_RETRIES,
      'checkers': RCLONE_CHECKERS,
      'transfers': RCLONE_TRANFERS,
      'stats_interval': RCLONE_STATS_INTERVAL,
      'chunk_size': RCLONE_CHUNK_SIZE,
      'upload_cutoff': RCLONE_UPLOAD_CUTOFF,
      'src': sync_entry['src'],
      'dst': sync_entry['dst'],
      'repo': sync_entry['repo'],
      'log_file': log_file
   }

   # execute the shell command
   subprocess.call(cmd.format(**args), shell=True)

