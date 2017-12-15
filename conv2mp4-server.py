"""==================================================================================
conv2mp4-py - https://github.com/Kameecoding/conv2mp4-py

Python 2.7 script that recursively searches through a defined file path and converts MKV, AVI, FLV,
and MPEG files to MP4 using handbrake. It then refreshes a Plex library, and deletes
the source file upon success and moves the new files into the defines directory (Plex Library directories
for example). Fails over to ffmpeg encode if conversion failure is detected. The purpose of this script
is to reduce the number of transcodes performed by a Plex server, by processing all files into an MP4 format.
=====================================================================================

This script requires FFMPEG and Handbrake. You can download them at the URLs below.
FFMPEG : https://FFMPEG.org/download.html
HANDBRAKEcli : https://HANDBRAKE.fr/downloads.php

-------------------------------------------------------------------------------------
User-specific variables
-------------------------------------------------------------------------------------
There are several user-defined variables you will need to edit using notepad or a program like Notepad++.

FFPROBE = path to ffprobe
FFMPEG = path to ffmpeg
HANDBRAKE = path to HandBrakeCLI
FILEBOT = path to FileBot

ENABLE_PLEX_UPDATE Set to True to enable the script to update your server
NOTE: Requires PLEX_IP and PLEX_TOKEN to work.
PLEX_IP = the IP address and port of your Plex server (for the purpose of refreshing its library)
PLEX_TOKEN = your Plex server's token (for the purpose of refreshing its library).
NOTE: See https://support.plex.tv/hc/en-us/articles/204059436-Finding-your-account-token-X-Plex-Token for instructions on retrieving your Plex server's token. Your Plex server's token is also easy to retrieve with Couchpotato or SickRage.

MAX_CONVERT_ITEMS = Maximum number of files to convert in one go
LOCALE = Three digit code for your language for example for Hungarian it's 'hun' 
FOREI_TVSHOW_TARGET = Path where you want your foreign langue Tv Shows

FOREIGN = Set to true if you want the script to take foreign language into account
EXTRACT_SRT = Whether to extract the subtitles from files into external SRTs (External SRT files don't trigger transcoding, while embedded might)
REMOVE_OLD = Whether to remove the files that have been already converted and are no longer needed
"""

import os
import sys
import time
import platform
import subprocess
import urllib2
import logging
import re
import shutil
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import json
reload(sys)
sys.setdefaultencoding('UTF-8')

"""----------------------------------------------------------------------------------
	Global Constants controlling the script
----------------------------------------------------------------------------------"""

IS_WINDOWS = any(platform.win32_ver())


#CONTROL THE SCRIPT WITH THESE VARIABLES
CREATE_FOREIGN = False
EXTRACT_SRT = True
REMOVE_CONVERTED = True
RENAME_FILES = True
MEDIA_DIR = "/home/kamee/downloads"
CONVERTED_DIR = '/home/kamee/converted'
#DIRECTORY WHERE RENAMED ITEMS WILL BE PLACED
RENAMED_DIR = '/home/kamee/renamed'
FOREIGN_MOVIE_DIR = ''
FOREIGN_TVSHOW_DIR = ''


""" Edit the following values to your liking, pay special attention to the media_path, PLEX_IP and PLEX_TOKEN values """
# Plex Server Token - See URL below inorder to obtain your Token
# https://support.plex.tv/hc/en-us/articles/204059436-Finding-your-account-token-X-Plex-Token
ENABLE_PLEX_UPDATE = False
PLEX_IP = '127.0.0.1:32400' #Typically '127.0.0.1:32400'
PLEX_TOKEN = '' # See https://support.plex.tv/hc/en-us/articles/204059436-Finding-your-account-token-X-Plex-Token
# Max media files to convert
MAX_CONVERT_ITEMS = 10
LOCALE = '' #Three digit code for your language for example for Hungarian it's 'hun'

# Paths to FFMPEG, HANDBRAKE-cli and your log file
# If you need help finding your install points in Linux, try 'which FFMPEG' and 'which HANDBRAKE'
# Make sure you install the following on your platform, FFMPEG, HANDBRAKE AND HANDBRAKE-cli
FFMPEG = 'ffmpeg'
FFPROBE = 'ffprobe'
HANDBRAKE = 'HandBrakeCLI'
FILEBOT = 'filebot'

"""----------------------------------------------------------------------------------
	GOOGLE DRIVE STUFF - Not working ignore
----------------------------------------------------------------------------------"""
UPLOAD_TO_DRIVE = False
#drive object for google drive
DRIVE = None
#Map of files ids based on path
FILES = {}
#ROOT folder id for Google Drive
ROOT_ID = ''
AUTH_TOKEN = ''


#Pattern Constants - DO NOT EDIT THESE
TV_SHOW_PATTERNS = [".(tv[ ]{0,1}shows).",".([0-9]+)x[0-9][0-9].",".s([0-9]+)e([0-9]+).",".s([0-9]+)[\.]{0,1}([0-9]+)."]
SUB_PATTERN = 'Stream #[0-9]:([0-9])\(([a-z]{3})\): Subtitle: [a-z]{3,7}[ ]*[\(]*([a-z]*)[\) \(]*([a-z]*)[\)\W]*Metadata:[\W]*title[ ]*: ([a-z]*)'
SUB_PATTERN2 = 'Stream #[0-9]:([0-9])\(([a-z]{3})\): Subtitle: [a-z]{3,7}[ ]*[\(]*([a-z]*)[\) \(]*([a-z]*)[\)\W]*'
AUDIO_PATTERN = 'Stream #[0-9]:[0-9]\(([a-z]{3})\):[\W]*Audio'
LANG_PATTERN = ".{pattern}.".format(pattern=LOCALE)

MOVIE_TARGET = os.path.join(CONVERTED_DIR, 'Movies')
FOREIGN_MOVIE_TARGET = os.path.join(CONVERTED_DIR, FOREIGN_MOVIE_DIR)
TVSHOW_TARGET = os.path.join(CONVERTED_DIR, "TV Shows")
FOREIGN_TVSHOW_TARGET = os.path.join(CONVERTED_DIR, FOREIGN_TVSHOW_DIR)

# File types to convert
videos = ('.mkv', '.avi', '.flv', '.mpeg', '.mp4','.m4v')
subtitles = ('.srt','.ass')


# Put log file here
if IS_WINDOWS:
	LOG_FILE = os.path.expanduser('~/Desktop/simple_convert2.log')
else:
	LOG_FILE = os.path.expanduser('~/simple_convert.log')

""" Don't change the following unless you know what you are doing!! """

""" Set up the Logger """
logging.basicConfig(filename=LOG_FILE, level=logging.INFO)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s: %(name)-12s - %(levelname)-8s %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)
Logger = logging.getLogger('simple_convert')


"""----------------------------------------------------------------------------------
	Rename Files using Filebot,
	looks for patterns in the name to determine if it's a TV Show or a Movie
----------------------------------------------------------------------------------"""
def rename_files(media_path):
	file_list = find_media_files(media_path)
		
	for file in file_list:
		#skip already renamed files
		#if re.search('.- s([0-9]+)e([0-9]+) -.',os.path.basename(file),re.I):
		#	continue
		#if re.search('.\(([0-9]{4})\).',os.path.basename(file),re.I):
		#	continue

		the_db = 'TheMovieDB'
		form = '{plex}'
		#if it looks like a TV Show change lookup
		if is_tvshow(file):
			the_db = 'TheTVDB'

		try:
			#rename the files
			proc = subprocess.Popen([
				FILEBOT,
				'-rename', file,
				'--format',form,
				'--db', the_db,
				'-non-strict',
				'--output', RENAMED_DIR
			],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
		except OSError as e:
			if e.errno == os.errno.ENOENT:
				Logger.error("Filebot not found, install on your system to use this script")
				sys.exit(0)

		output = proc.stdout.read()
		
		if output.find('already exists') != -1:
			Logger.warning("{filename} wasn't renamed because a file with same name already exists".format(filename=file))

		Logger.info("{filename} renamed".format(filename=file))
	if REMOVE_CONVERTED:
		for file in file_list:
			Logger.info("{filename} removed".format(filename=os.path.dirname(file)))
			shutil.rmtree(os.path.dirname(file), ignore_errors=True)

def is_tvshow(filename):
	for pattern in TV_SHOW_PATTERNS:
		match = re.search(pattern,filename,re.I)
		if match:
			return True
	return False

def check_path(target_dir):
	if not os.path.isdir(target_dir):
		os.makedirs(target_dir)


"""----------------------------------------------------------------------------------
	Update Plex Server
----------------------------------------------------------------------------------"""
def update_plex():
	Logger.info("plex - sending request to update Plex")
	url = 'http://%s/library/sections/all/refresh?X-Plex-Token=%s' % (PLEX_IP, PLEX_TOKEN)

	try:
		urllib2.urlopen(url).read()
	except urllib2.HTTPError, e:
		Logger.warning("plex - unable to make request to Plex - HTTP Error %s", str(e.code))
	except urllib2.URLError, e:
		Logger.warning("plex - unable to make request to Plex - URL Error %s", e.reason)
	else:
		Logger.info("plex - update successful")


""" Build a array of files to convert """
def find_media_files(media_path):
	unconverted = []

	for dirname, directories, files in os.walk(media_path):
		for file in files:
			#skip hidden files
			if file.startswith('.'):
				continue

			if is_video(file) or is_subtitle(file):
				file = os.path.join(dirname, file)
				#Skip Sample files			   
				if re.search(".sample.",file,re.I):
					continue		
							
				unconverted.append(file)

	sorted_unconvered =  sorted(unconverted)

	return sorted_unconvered

def is_subtitle(filename):
	if filename.endswith(subtitles):
		return True
	return False

def is_video(filename):
	if filename.endswith(videos):
		return True
	return False



def get_length(file):
	#Get file info and Parse it	 
	proc =subprocess.Popen([
		FFMPEG,
		'-i', file,
	],stdout=None,stderr=subprocess.PIPE)
	output = proc.stderr.read()

	pattern = '.Duration: ([0-9]{2}):([0-9]{2}):([0-9]{2}).'
	match = re.search(pattern,output,re.I | re.M)
	
	if not match:
		Logger.info("ERROR: Failed to assert duration")
		sys.exit(0)
	return [int(match.group(1)),int(match.group(2)),int(match.group(3))]


def good_output(oldFile,new_file):
	oldSize = get_length(oldFile)
	newSize = get_length(new_file)

	for i in range(0,2):
		if i == 2:
			if abs(oldSize[i]- newSize[i]) > 5:
				Logger.info("ERROR: File Duration difference bigger than 5 seconds, convert failed")
				return False
		else:
			if oldSize[i] != newSize [i]:
				Logger.info("ERROR: File Duration difference bigger than 5 seconds, convert failed")
				return False
	Logger.info("SUCCESS: File Duration difference less than 5 seconds, convert successful")
	return True

#Recursively build a map of folder paths to GDRIVE ids
def ListFolder(parent,currentFolder):
	file_list = DRIVE.ListFile({'q': "'%s' in parents and trashed=false" % parent}).GetList()
	for f in file_list:
		if f['mimeType']=='application/vnd.google-apps.folder': # if folder
			FILES[os.path.join(currentFolder,f['title'])] = f['id']
			ListFolder(f['id'], os.path.join(currentFolder,f['title']))

""" Main Application """
def main(argv):

	global MEDIA_DIR
	global DRIVE

	if len(argv) == 2:
		MEDIA_DIR = argv[1]

	if not os.path.exists(MEDIA_DIR):
		Logger.error("Unable to find directory: {path}".format(path=MEDIA_DIR))
		Logger.info("You can enter a valid media path in the script header or you can pass it in as an argument")
		sys.exit(0)

	check_path(CONVERTED_DIR)
	check_path(RENAMED_DIR)

	if UPLOAD_TO_DRIVE:
		gauth = GoogleAuth()
		# Try to load saved client credentials
		gauth.LoadCredentialsFile("mycreds.txt")
		if gauth.credentials is None:
			# Authenticate if they're not there
			gauth.CommandLineAuth()
		elif gauth.access_token_expired:
			# Refresh them if expired
			gauth.Refresh()
		else:
			# Initialize the saved creds
			gauth.Authorize()
		# Save the current credentials to a file
		gauth.SaveCredentialsFile("mycreds.txt")

		DRIVE = GoogleDrive(gauth)

		ListFolder(ROOT_ID, 'media')

	while True:
		#Rename Files Using Filebot
		if RENAME_FILES:
			rename_files(MEDIA_DIR)
			
		#Find Media files to convert
		MediaFile.files = find_media_files(RENAMED_DIR)
		media_files = []
		#Create file objects
		while MediaFile.files:
			media_files.append(MediaFile())

		Logger.info("%d total files to convert", len(media_files))

		i = 0
		for file in media_files:
			i = i + 1
			if i > MAX_CONVERT_ITEMS:
				break

			Logger.info("converting %d of %d items", i, len(media_files) if len(media_files) < MAX_CONVERT_ITEMS else MAX_CONVERT_ITEMS)
			
			try:
				file.execute()
			except KeyboardInterrupt:
				Logger.info("KeyBoardInterrupt Detected, Exiting")
				sys.exit(1)
			
			# Update Plex
			if ENABLE_PLEX_UPDATE == True:
				update_plex()
			
		if i:
			subprocess.call(['python','sync.py'])
			#sys.exit(0);
			shutil.rmtree(TVSHOW_TARGET,ignore_errors=True)
			shutil.rmtree(FOREIGN_TVSHOW_TARGET, ignore_errors=True)
			shutil.rmtree(MOVIE_TARGET,ignore_errors=True)
			shutil.rmtree(FOREIGN_MOVIE_TARGET, ignore_errors=True)
		else:
			time.sleep(600)

def create_folder(name, parent_id, parent_path):
	folder_metadata = {'title': name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [{'id': parent_id}]}
	folder = DRIVE.CreateFile(folder_metadata)
	folder.Upload()
	
	global FILES

	if folder['id']:
		FILES[os.path.join(parent_path, name)] = folder['id']
		logging.info("Created remote folder: {name} path: {path}".format(name=folder['title'], path=parent_path))
	else:
		logging.error("Failed to create new folder {folder} in parent {path}, with id: {id}".format(folder=name, path=parent_path, id=parent_id))
		raise Exception("Failed to create new folder {folder} in parent {path}, with id: {id}".format(folder=name, path=parent_path, id=parent_id))

def drive_upload(source):
	if MEDIA_DIR in source:
		target = os.path.dirname(source.replace(MEDIA_DIR, 'media'))
	else:
		target = os.path.dirname(source.replace(CONVERTED_DIR, 'media'))
	target_copy = target
	to_add = []
	while (not FILES.get(target_copy)):
		to_add.insert(0, os.path.basename(target_copy))
		target_copy = os.path.dirname(target_copy)

	if (to_add):
		for folder in to_add:
			create_folder(folder, FILES[target_copy], target_copy)
			target_copy = os.path.join(target_copy,folder)

	Logger.info("Uploading file: {name} to {target}, with Title: {title}".format(name=source, target=target, title=os.path.basename(source)))
	f = DRIVE.CreateFile({"parents": [{"id": FILES[target]}], "title" : os.path.basename(source)})
	f.SetContentFile(source)
	f.Upload()

	if not f['id']:
		logging.error("Failed to upload file {source}".format(source=source))
		raise Exception("Failed to upload file {source}".format(source=source))

"""----------------------------------------------------------------------------------
Returns a list of dictionaries with two entries:
index = the index of the subtitle stream in the file
path  = the path where it should be extracted to
----------------------------------------------------------------------------------"""
def get_external_srt_targets(json_output, base_name):
	result = []
	for stream in json_output['streams']:
		if stream['codec_type'] != "subtitle":
			continue
		current = {}
		forced = False
		language = ''

		current['index'] = stream['index']
		if stream.get('tags'):
			language = stream['tags']['language'].decode('UTF-8').lower()
			if stream['tags'].get('title'):
				forced = 'forced' == stream['tags']['title'].decode('UTF-8').lower()

		if not forced and stream.get('disposition') and stream['disposition'].get('forced'):
			forced = stream['disposition']['forced'] == 1

		curr_path = base_name + '.'
		if language:
			curr_path = curr_path + language + '.'
		if forced:
			curr_path = curr_path + 'forced.'

		current['path'] = curr_path + 'srt'

		result.append(current)

	return result

"""----------------------------------------------------------------------------------
Returns a list of dictionaries with two entries:
index = the index of the subtitle stream in the file
language = the language of the audio stream
----------------------------------------------------------------------------------"""
def get_audio_streams(json_output):
	result = []
	
	for stream in json_output['streams']:
		if stream['codec_type'] != "audio":
			continue
		current = {}
		current['index'] = stream['index']
		if stream.get('tags') and stream['tags'].get('language'):
			current.update({'language':stream['tags']['language']})
		else:
			current['language'] = 'unk'
		#TODO add bitrate, codec what you want

		result.append(current)

	return result


class MediaFile:

	files = []

	def __init__(self):
		#Initialize attributes
		self.input_video = ''
		self.external_subtitles = []
		self.target_dir = ''
		self.error = 0

		self.extracted_srts = []
		self.find_matches()
		self.is_show = is_tvshow(self.input_video)
		self.find_target_dir()
		Logger.info("Found target directory: {target}".format(target=self.target_dir))
		self.output_video = os.path.join(self.target_dir, os.path.basename(self.input_video)[:-3] + 'mp4')

	"""----------------------------------------------------------------------------------
	Execute Converting of the file
	----------------------------------------------------------------------------------"""
	def execute(self):
		check_path(self.target_dir)
		
		if EXTRACT_SRT:
			self.extract_srt()
			self.move_external_subs()

		if self.input_video != self.output_video:
			try:
				self.handbrake_convert();
				if UPLOAD_TO_DRIVE:
					self.upload_to_drive()
			except KeyboardInterrupt:
				Logger.info("KeyBoardInterrupt Detected, Cleaning up and Exiting")
				self.remove_media_file(self.output_video)
				sys.exit(0)
			if REMOVE_CONVERTED:
				Logger.info("Deleting old files")
				self.remove_media_file(self.input_video)
				self.remove_folder(os.path.dirname(self.input_video))
		else:
			Logger.info("{file} already exists, skipping.".format(file=self.input_video))


	"""----------------------------------------------------------------------------------
	Find Video files and matching external subtitles
	----------------------------------------------------------------------------------"""	
	def find_matches(self):
		self.input_video = ''
		for file in self.files:
			if is_video(file):
				self.input_video = file
				break
		if not self.input_video:
			logging.error("Unable to find video files, exiting, files : {files}".format(files=self.files))
			sys.exit(1)
		self.files.remove(self.input_video)

		self.external_subtitles = []

		to_remove = []
		for file in self.files:
			match = os.path.commonprefix([self.input_video,file])
			video_file_dir = os.path.dirname(self.input_video)
			if len(match) == len(self.input_video[:-3]):
				self.external_subtitles.append(file)
				to_remove.append(file)
			elif os.path.dirname(os.path.dirname(file)) == video_file_dir:
				new_file_name = os.path.join(video_file_dir, os.path.basename(file))
				match = os.path.commonprefix([self.input_video, new_file_name])
				if len(match) == len(self.input_video[:-3]):
					logging.info("Moving file one directory up: {file}".format(file=os.path.basename(file)))
					shutil.move(file, video_file_dir)
					self.external_subtitles.append(new_file_name)
					to_remove.append(file)

		for srt in to_remove:
			self.files.remove(srt)
		to_remove = []

		for file in self.files:
			compare = [os.path.basename(self.input_video),os.path.basename(file)]
			if os.path.commonprefix(compare) == os.path.basename(self.input_video[:-4]):
				if is_subtitle(file):
					self.external_subtitles.append(file)
					to_remove.append(file)

		for srt in to_remove:
			self.files.remove(srt)

 
	"""----------------------------------------------------------------------------------
	Find target directory
	----------------------------------------------------------------------------------"""					
	def find_target_dir(self):
	
		self.target_dir = os.path.dirname(self.input_video)
		self.target_dir = self.target_dir.replace(RENAMED_DIR, CONVERTED_DIR)

		#If we care about foreign languages execute this part
		if CREATE_FOREIGN:
			audiostreams = self.get_audio_streams()
			#If the the input is matches LOCALE put it in the lang folders
			for audio in audiostreams:
				if (audio['language'] == LOCALE):
					if self.is_show:
						self.target_dir = self.target_dir.replace(TVSHOW_TARGET, FOREIGN_TVSHOW_TARGET)
					else:
						self.target_dir = self.target_dir.replace(MOVIE_TARGET, FOREIGN_MOVIE_TARGET)
					return


	"""----------------------------------------------------------------------------------
	Get Audio streams from the file
	----------------------------------------------------------------------------------"""
	def get_audio_streams(self):
		with open(os.devnull, 'w') as DEV_NULL:
			#Get file info and Parse it
			try:
				proc = subprocess.Popen([
					FFPROBE,
					'-i', self.input_video,
					'-of', 'json',
					'-show_streams'
				], stdout=subprocess.PIPE, stderr=DEV_NULL)
			except OSError as e:
				if e.errno == os.errno.ENOENT:
					Logger.error("FFPROBE not found, install on your system to use this script")
					sys.exit(0)
			output = proc.stdout.read()

			return get_audio_streams(json.loads(output))

	"""----------------------------------------------------------------------------------
	Convert files found to mp4 using HandBrakeCLI
	----------------------------------------------------------------------------------"""
	def handbrake_convert(self):
		Logger.info("HANDBRAKECLI - converting %s to %s", self.input_video, self.output_video)

		try:
			proc = subprocess.Popen([
				HANDBRAKE,
				'-i', self.input_video,
				'-o', self.output_video,
				'--auto-anamorphic',
				'-E', 'copy',
				'-e', 'x264',
				'-q', '20.0',
				'--optimize',
				'--all-audio',
				'--audio-copy-mask', 'aac,eac3,ac3,dtshd,dts,truehd',
				'--audio-fallback', 'ac3',
				'-f', 'av_mp4',
				'--vfr',
				'--x264-preset', 'medium',
				'--h264-profile', 'high',
				'--h264-level', '4.1'
			], stdout=None, stderr=subprocess.PIPE)
			output = proc.stderr.read()

			print output

			if output.find("Encode done!") == -1:
				self.error = 1

			# If the return code is 1 that means HANDBRAKECLI failed
			if self.error == 1:
				Logger.warning("HANDBRAKECLI - failure converting %s", os.path.basename(self.input_video))
				self.remove_media_file(self.output_video)

		except OSError as e:
			if e.errno == os.errno.ENOENT:
				Logger.warning("HANDBRAKECLI not found, install on your system to use this script")
				sys.exit(0)

		Logger.info("HANDBRAKECLI - {input} converted succesfully converted to: {output}".format(input=self.input_video,output=self.output_video))

	"""----------------------------------------------------------------------------------
		Convert files found to mp4 using HandBrakeCLI
		----------------------------------------------------------------------------------"""
	def upload_to_drive(self):
		drive_upload(self.output_video)

		for srtFile in self.extracted_srts:
			drive_upload(srtFile);

	"""----------------------------------------------------------------------------------
	Extract SRT files if they are embedded
	----------------------------------------------------------------------------------"""
	def extract_srt(self):

		#Get file info and Parse it
		with open(os.devnull, 'w') as DEV_NULL:
			try:
				proc = subprocess.Popen([
					FFPROBE,
					'-i', self.input_video,
					'-of', 'json',
					'-show_streams'
				], stdout=subprocess.PIPE, stderr=DEV_NULL)
			except OSError as e:
				if e.errno == os.errno.ENOENT:
					Logger.error("FPROBE not found, install on your system to use this script")
					sys.exit(0)

			output = proc.stdout.read()

			output = json.loads(output)

			filename = os.path.basename(self.output_video)[:-4]
			filename = os.path.join(self.target_dir, filename)

			for srtFile in get_external_srt_targets(output, filename):

				Logger.info("creating subtitle: {name}".format(name=srtFile['path']))
				proc = subprocess.Popen([
					FFMPEG,'-y',
					'-i', self.input_video,
					'-map', '0:{num}'.format(num=srtFile['index']),
					srtFile['path']
				],stdout=DEV_NULL, stderr=DEV_NULL)

				if os.path.exists(srtFile['path']):
					if os.path.getsize(srtFile['path']) > 0:
						self.extracted_srts.append(srtFile['path'])
					else:
						os.remove(srtFile['path'])


	"""----------------------------------------------------------------------------------
	Move Subs to target_dir
	----------------------------------------------------------------------------------"""
	def move_external_subs(self):
		for sub in self.external_subtitles:
			new_sub = os.path.join(self.target_dir,os.path.basename(sub))
			if sub != new_sub:	
				shutil.move(sub,new_sub)
				Logger.info("Subtitle: {old}\n moved to {new}".format(old=sub,new=new_sub))

	"""----------------------------------------------------------------------------------
	Remove files quietly if they don't exist
	----------------------------------------------------------------------------------"""
	def remove_media_file(self,file):
		try:
			if self.input_video != self.output_video:
				os.remove(file)
		except OSError as e:
			if e.errno != os.errno.ENOENT:
				raise
		else:
			Logger.info("system - deleted file %s",file)

	"""----------------------------------------------------------------------------------
	Recursively remove folders
	----------------------------------------------------------------------------------"""
	def remove_folder(self,folder):
		if not find_media_files(folder) and folder != MEDIA_DIR and folder != "/home/kamee/converted" and os.path.dirname(self.input_video) != self.target_dir:
			try:
				shutil.rmtree(folder,True)
				Logger.info("Folder {folder} succesfully removed".format(folder=folder))
				self.remove_folder(os.path.dirname(folder))
			except OSError as reason:
				Logger.info(reason)


if __name__ == '__main__':
	main(sys.argv)
