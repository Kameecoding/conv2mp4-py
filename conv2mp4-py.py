"""==================================================================================
conv2mp4-py - https://github.com/Kameecoding/conv2mp4-py

Python 2.7 script that recursively searches through a defined file path and converts MKV, AVI, FLV,
and MPEG files to MP4 using handbrake (with AAC audio). It then refreshes a Plex library, and deletes
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

NOTE: to use a mapped drive, you must run net use z: \server\share /persistent:yes as the user you're going to run the script as (generally Administrator) prior to running the script.

FFMPEG = path to ffmpeg.exe
HANDBRAKE = path to HandBrakeCLI.exe 
FILEBOT = path to FileBot.exe 

ENABLE_PLEX_UPDATE Set to True to enable the script to update your server
NOTE: Requires PLEX_IP and PLEX_TOKEN to work.
PLEX_IP = the IP address and port of your Plex server (for the purpose of refreshing its library)
PLEX_TOKEN = your Plex server's token (for the purpose of refreshing its library).
NOTE: See https://support.plex.tv/hc/en-us/articles/204059436-Finding-your-account-token-X-Plex-Token for instructions on retrieving your Plex server's token. Your Plex server's token is also easy to retrieve with Couchpotato or SickRage.

MAX_CONVERT_ITEMS = Maximum number of files to convert in one go
LOCALE = Three digit code for your language for example for Hungarian it's 'hun' 

Target Folders for converted files 
MOVIE_TARGET = Path where you want your movies
TVSHOW_TARGET = Path where you want your TV SHows
LANG_MOVIE_TARGET = Path where you want your foreign language movies
LANG_TVSHOW_TARGET = Path where you want your foreign langue Tv Shows

FOREIGN = Set to true if you want the script to take foreign language into account
PREFER_METADATA = The Script tries to match the description and the metadata of the subtitles in the file, you can try turning it on and off to see if the subtitles were matched better
EXTRACT_SRT = Whether to extract the subtitles from files into external SRTs (External SRT files don't trigger transcoding, while embedded might)

MOVE_FILES = Whether to allow to move the files to new directories or keep them in the same
CREATE_MOVIE_DIRS = Whether to create a directory for each movie file: e.g. it will put the movie Pacific Rim and all it's subtitles to the folder [MOVIE_TARGET or LANG_MOVIE_TARGET]\Pacific Rim (2013)\ 
CREATE_TVSHOW_DIRS = Whether to create a directory for each TV Show: e.g. it will put the tv show Modern Family and all it's episodes and subtitles to the folder [TVSHOW_TARGET or LANG_TVSHOW_TARGET]\Modern Family\ 
CREATE_SEASON_DIRS = Used together with CREATE_TVSHOW_DIRS, also adds a Season folder. e.g. first Season of Modern Family will get put into: [TVSHOW_TARGET or LANG_TVSHOW_TARGET]\Modern Family\Season 01\ 
NOTE: Only Works with CREATE_TVSHOW_DIRS set to True
REMOVE_OLD = Whether to remove the files that have been already converted and are no longer needed
HARD_LINK = Whether to create hardlink between folders, for example if you have a movie with both English and Foreign audio and you want plex to detect it in both the English and Foreign Library the easiest way is to Hard link the directories
NOTE: Only Works with FOREIGN and MOVE_FILES set to True"""

import os
import sys
import time
import platform
import subprocess
import urllib2
import logging
import re
import shutil
import ntfsutils.junction

"""----------------------------------------------------------------------------------
    Global Constants controlling the script
----------------------------------------------------------------------------------"""

IS_WINDOWS = any(platform.win32_ver())


#CONTROL THE SCRIPT WITH THESE VARIAB:ES
FOREIGN = True
PREFER_METADATA = True
CREATE_MOVIE_DIRS = True
CREATE_TVSHOW_DIRS = True
CREATE_SEASON_DIRS = True
MOVE_FILES = True
EXTRACT_SRT = True
REMOVE_CONVERTED = True
HARD_LINK  = True
DEV_NULL = open(os.devnull,'w')


# File types to convert
videos = ('.mkv', '.avi', '.flv', '.mpeg', '.mp4')
subtitles = ('.srt','.ass')


""" Edit the following values to your liking, pay special attention to the media_path, PLEX_IP and PLEX_TOKEN values """
# Plex Server Token - See URL below inorder to obtain your Token
# https://support.plex.tv/hc/en-us/articles/204059436-Finding-your-account-token-X-Plex-Token
ENABLE_PLEX_UPDATE = True
PLEX_IP = '' #Typically '127.0.0.1:32400'
PLEX_TOKEN = '' # See https://support.plex.tv/hc/en-us/articles/204059436-Finding-your-account-token-X-Plex-Token 
# Max media files to convert
MAX_CONVERT_ITEMS = 200
LOCALE = '' #Three digit code for your language for example for Hungarian it's 'hun'

# Paths to FFMPEG, HANDBRAKE-cli and your log file
# If you need help finding your install points in Linux, try 'which FFMPEG' and 'which HANDBRAKE'
# Make sure you install the following on your platform, FFMPEG, HANDBRAKE AND HANDBRAKE-cli
FFMPEG = 'C:\\FFMPEG\\bin\\FFMPEG.exe' #'/usr/bin/FFMPEG'
HANDBRAKE = "C:\Program Files\HandBrake\HandBrakeCLI.exe" #'/usr/bin/HandBrakeCLI'
FILEBOT = 'C:\Program Files\FileBot\\FILEBOT.exe'

MOVIE_TARGET = '' #Example: "F:\Media\Movies"
LANG_MOVIE_TARGET = '' # Example: "F:\Media\Filmek"
TVSHOW_TARGET = '' #Example F:\Media\TV Shows'
LANG_TVSHOW_TARGET = '' #Example "F:\Media\Sorozatok"

#Pattern Constants - DO NOT EDIT THESE
TV_SHOW_PATTERNS = [".s([0-9]+).",".([0-9]+)x[0-9][0-9].",".s([0-9]+)e([0-9]+)."]
SUB_PATTERN = 'Stream #[0-9]:([0-9])\(([a-z]{3})\): Subtitle: [a-z]{3,7}[ ]*[\(]*([a-z]*)[\) \(]*([a-z]*)[\)\W]*Metadata:[\W]*title[ ]*: ([a-z]*)'
SUB_PATTERN2 = 'Stream #[0-9]:([0-9])\(([a-z]{3})\): Subtitle: [a-z]{3,7}[ ]*[\(]*([a-z]*)[\) \(]*([a-z]*)[\)\W]*'
AUDIO_PATTERN = 'Stream #[0-9]:[0-9]\(([a-z]{3})\):[\W]*Audio'
LANG_PATTERN = ".{pattern}.".format(pattern=LOCALE)

#COUNTRY TUPLE FOR translating matched METADATA patterns
COUNTRY_TUPLE = {
    'nagyar'    : 'hun',
    'hungarian' : 'hun',
    'angol'     : 'eng',
    'english'   : 'eng',
    'forced'    : 'forced',
    'dutch'     : 'dut',
    'french'    : 'fre',
    'german'    : 'ger',
    'italian'   : 'ita',
}

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
    #TODO keep suffixes
    file_list = find_media_files(media_path)
        
    for file in file_list:
        #skip already renamed files
        if re.search('.s([0-9]+)e([0-9]+).',os.path.basename(file),re.I):
            continue

        the_db = 'TheMovieDB'
        #if it looks like a TV Show change lookup
        if is_tvshow(file):
            the_db = 'TheTVDB'
        
        suffix_match = re.search('\.([a-z]{3})\.',os.path.basename(file),re.I)
        forced_match = re.search('.(forced).',file,re.I)
        if suffix_match:
            suffix = suffix_match.group(1)
            is_good_suffix = False
            if suffix in COUNTRY_TUPLE.values():
                is_good_suffix = True

        if forced_match:
            forced = forced_match.group(1)
        
        #rename the files       
        proc = subprocess.Popen([
            FILEBOT,
            '-rename', file,
            '--format','{n} - {s00e00} - {t}',
            '--db', the_db,
            '-non-strict'
        ],stdout=subprocess.PIPE,stderr=subprocess.PIPE)

        output = proc.stdout.read()
        
        if output.find('already exists') != -1:
            Logger.warning("{filename} wasn't renamed because a file with same name already exists".format(filename=file))
            continue
        
        try:
            match = re.search('\[MOVE\] Rename \[(.*?)\] to \[(.*?)\]',output,re.I | re.M)
            output_file = match.group(2)
            rename_output = output_file
            output_file_extention = output_file[-3:]
            output_file = output_file[:-3]

            if 'suffix' in locals() and is_good_suffix:
                output_file += suffix + '.'
            if 'forced' in locals():
                output_file += forced + '.'
            output_file += output_file_extention
            if rename_output != output_file:
                shutil.move(rename_output,output_file)
        except AttributeError:
            Logger.warning("Unable to match output file name for {filename}".format(filename=file))
            continue
        Logger.info("{filename} renamed".format(filename=file))

def is_tvshow(filename):
    for pattern in TV_SHOW_PATTERNS:
        match = re.search(pattern,filename,re.I)
        if match:
            return True
    return False

def combine_matches(matches1,matches2):
    offset = 132456789
    output = []

    if len(matches1) > 0 and int(matches1[0][0]) < offset:
        offset = matches1[0][0]
    if len(matches2) > 0 and int(matches2[0][0]) < offset:
        offset = matches2[0][0]
    while len(matches1) > 0 or len(matches2) > 0:   
        if len(matches1) == 0:
            output.append(matches2[0])
            del matches2[0]
        elif len(matches2) == 0:
            output.append(matches1[0])
            del matches1[0]
        elif matches1[0][0] < matches2[0][0]:
            output.append(matches1[0])
            del matches1[0]
        elif matches1[0][0] > matches2[0][0]:
            output.append(matches2[0])
            del matches2[0]
        elif len(matches1[0]) > len(matches2[0]):
            output.append(matches1[0])
            del matches1[0]
            del matches2[0]
        else:
            Logger.info("combine_matches: Unexpected result while parsing subtitles")
        #print output
    return (offset,output)



def check_path(target_dir):
    if not os.path.isdir(target_dir):
        os.makedirs(target_dir)

def get_locale(prefix,title=''):
    temp = '' 
    if title == '':
        temp = ".{prefix}".format(prefix=prefix)
    else:
        if(PREFER_METADATA):
            temp=  ".{prefix}".format(prefix=translate_title(prefix,title))
        else:
            temp = ".{prefix}".format(prefix=prefix)
    return temp

def translate_title(prefix,title):
    title=title.lower()
    if PREFER_METADATA:
        try:        
            if prefix != COUNTRY_TUPLE[title]:
                if COUNTRY_TUPLE[title] == 'forced':
                    return prefix + '.forced' 
                else:
                    return COUNTRY_TUPLE[title]
        except KeyError:
            Logger.info("Unknown Country Touple Key: {key}".format(key=title))
    return prefix


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
       
    #print 
    #print os.listdir(media_path)

    #for directories in next(os.walk(media_path))[1]:
    #    print "Directories:" + directories

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

    return sorted_unconvered[:MAX_CONVERT_ITEMS] if MAX_CONVERT_ITEMS else sorted_unconvered

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


""" Main Application """
def main(argv):

    if len(argv) == 1:
        path, binary = os.path.split(argv[0])
        print "Usage: {} [directory ...]".format(binary)
        sys.exit(0)

    global media_path
    media_path = argv[1]

    if not os.path.exists(media_path):
        Logger.error("Unable to find directory: {path}".format(path=media_path))
        sys.exit(0)

    
    #Rename Files Using Filebot
    rename_files(media_path)
        
    #Find Media files to convert
    MediaFile.files = find_media_files(media_path)
    media_files = []
    #Create file objects
    while MediaFile.files:
        media_files.append(MediaFile())

    Logger.info("%d total files to convert", len(media_files))

    i = 1
    for file in media_files:

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
        # Keep a counter of item processed
        i = i + 1



class MediaFile:

    files = []

    def __init__(self):
        #Initialize attributes
        self.input_video = ''
        self.external_subtitles = []
        self.hard_link = ''
        self.target_dir = ''
        self.error = 0

        self.find_matches()
        self.is_show = is_tvshow(self.input_video)
        self.add_targets()
        self.append_folder()
        self.output_video = os.path.join(
                                self.target_dir, 
                                os.path.basename(self.input_video)[:-3] + 'mp4')

    """----------------------------------------------------------------------------------
    Execute Converting of the file
    ----------------------------------------------------------------------------------"""
    def execute(self):
        check_path(self.target_dir)
        
        if EXTRACT_SRT:
            self.extract_srt()
        if MOVE_FILES:
            self.move_external_subs()
        self.create_hard_link()
        try:
            self.handbrake_convert()
        except KeyboardInterrupt:
            Logger.info("KeyBoardInterrupt Detected, Cleaning up and Exiting")
            self.remove_media_file(self.output_video)
            sys.exit(0)
        if REMOVE_CONVERTED:
            self.remove_media_file(self.input_video)
            self.remove_folder(os.path.dirname(self.input_video))

    """----------------------------------------------------------------------------------
    Create hard links from english to foreign directories
    ----------------------------------------------------------------------------------"""
    def create_hard_link(self):
        if self.hard_link:
            if not os.path.isdir(self.hard_link):
                Logger.info("Hardlinking {source} and {target}".format(source=self.target_dir,target=self.target_dir))
                check_path(os.path.dirname(self.hard_link))
                if IS_WINDOWS:
                    ntfsutils.junction.create(self.target_dir,self.hard_link)
                else:
                    os.link(self.target_dir,self.hard_link)
            else:
                Logger.warning("Can't hardlink {source} and {target}, {target} already exists".format(source=self.target_dir,target=self.target_dir))
            

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
            logging.error("Unable to find video files, exiting")
            sys.exit(1)
        self.files.remove(self.input_video)

        self.external_subtitles = []
        for file in self.files:
            match = os.path.commonprefix([self.input_video,file])
            if len(match) == len(self.input_video[:-3]):
                self.external_subtitles.append(file)
                self.files.remove(file)
        
        for file in self.files:
            compare = [os.path.basename(self.input_video),os.path.basename(file)]
            
            if os.path.commonprefix(compare) == os.path.basename(self.input_video[:-3]):
                if is_subtitle(file):
                    self.external_subtitles.append(file)
                    self.files.remove(file)
        
    """----------------------------------------------------------------------------------
    Add target directory and hardlink if enabled
    ----------------------------------------------------------------------------------"""                    
    def add_targets(self):
    
        self.target_dir = os.path.dirname(self.input_video)
        self.hard_link = ''
        
        if MOVE_FILES:
            #If we care about foreign languages execute this part
            if FOREIGN:
                audiostreams = self.get_audio_streams()
                #if we want to create hard links and there is both english and locale audio stream in the file or in the name
                if HARD_LINK and ((LOCALE in audiostreams and 'eng' in audiostreams) or (re.search('.{}.'.format(LOCALE),self.input_video,re.I) and re.search('.eng.',self.input_video,re.I))):
                    self.target_dir = TVSHOW_TARGET if self.is_show else MOVIE_TARGET
                    self.hard_link = LANG_TVSHOW_TARGET if self.is_show else LANG_MOVIE_TARGET                 
                else:
                    #If the the input is matches LOCALE put it in the lang folders
                    if re.search(LANG_PATTERN,self.input_video,re.I | re.M):
                        self.target_dir = LANG_TVSHOW_TARGET if self.is_show else LANG_MOVIE_TARGET
                    #Else put them in the main folder
                    else:
                        self.target_dir = TVSHOW_TARGET if self.is_show else MOVIE_TARGET
            #if we don't give a shit about multiple languages simply determine if tvshow or movie
            else:
                self.target_dir = TVSHOW_TARGET if self.is_show else MOVIE_TARGET
    

    """----------------------------------------------------------------------------------
    Get Audio streams from the file
    ----------------------------------------------------------------------------------"""
    def get_audio_streams(self):
        #Get file info and Parse it  
        try:
            proc =subprocess.Popen([
                FFMPEG,
                '-i', self.input_video,
            ],stdout=None,stderr=subprocess.PIPE)
        except OSError as e:
            if e.errno == os.errno.ENOENT:
                Logger.error("FFMPEG not found, install on your system to use this script")
                sys.exit(0)
        output = proc.stderr.read()
        return re.findall(AUDIO_PATTERN,output,re.I | re.M)

    """----------------------------------------------------------------------------------
    Add /Season XX  or /MovieName (Year) to target dir
    ----------------------------------------------------------------------------------"""
    def append_folder(self):

        if (CREATE_TVSHOW_DIRS and self.is_show):
            sub_folder=os.path.basename(self.input_video)[:os.path.basename(self.input_video).find('-')-1]
            if CREATE_SEASON_DIRS: 
                match = re.search(TV_SHOW_PATTERNS[0],self.input_video,re.I)
                if match:
                    season = match.group(1)
                else:
                    match = re.search(TV_SHOW_PATTERNS[2],self.input_video,re.I)
                    if match:
                        season = match.group(1)
                    if 'season' in locals():
                        if len(season) == 1:
                            season = ' 0' + season
                        else:
                            season = ' ' + season
                    else:
                        Logger.info('Failed to match season pattern in {new}'.format(new=self.input_video))
                        sys.exit(0)
                sub_folder = os.path.join(sub_folder,'Season' + season) 
        elif (CREATE_MOVIE_DIRS and not self.is_show):
            sub_folder=os.path.basename(self.input_video)[:-4]
        if 'sub_folder' in locals():
            self.target_dir = os.path.join(self.target_dir,sub_folder)

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
            '-e', 'x264',
            '-q', '20.0',
            '-a','1,2,3,4,5,6',
            '-E','faac,copy:aac',
            '-B', '160,160',
            '-6', 'dpl2,none' ,
            '-R', 'Auto,Auto',
            '-D', '0.0,0.0',
            '--optimize',
            '--audio-copy-mask','aac'
            '--audio-fallback','faac',
            '-f', 'mp4',
            '--decomb',
            '--loose-anamorphic',
            '--modulus', '2',
            '--cfr','-r','30',
            '--markers','-4', 
            '--x264-preset', 'medium',
            '--h264-profile', 'high',
            '--h264-level', '4.0',  
            ], stdout=None,stderr=subprocess.PIPE)
            output = proc.stderr.read()
            
            print output
            
            if output.find("Encode done!") == -1:
                self.error = 1

            # If the return code is 1 that means HANDBRAKECLI failed
            if self.error == 1:
                Logger.warning("HANDBRAKECLI - failure converting %s", os.path.basename(self.input_video))
                self.remove_media_file(self.output_video)
                self.ffmpeg_convert()

        except OSError as e:
            if e.errno == os.errno.ENOENT:
                Logger.warning("HANDBRAKECLI not found, install on your system to use this script")
                sys.exit(0)
            else:
                Logger.info("HANDBRAKECLI - {input} converted succesfully converted to: {output}".format(input=self.input_video,output=self.output_video))


    """----------------------------------------------------------------------------------
    Convert files found to mp4 using ffmeg
    ----------------------------------------------------------------------------------"""
    def ffmpeg_convert(self):
        Logger.info("FFMPEG - converting %s to %s", self.input_video, self.output_video)

        self.error = 0

        try:
            proc = subprocess.Popen([
                FFMPEG,
                '-n',
                '-fflags', '+genpts',
                '-f', 'h264',
                '-i', self.input_video,
                '-vcodec', 'copy',
                '-acodec', 'aac',
                '-strict', '-2',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-strict','experimental',
                '-b:a', '192K',
                '-maxrate', '5200K',
                '-bufsize', '5200K',
                '-crf', '23',
                '-r','30',
                self.output_video
            ],stdout=subprocess.PIPE,stderr=subprocess.PIPE)

            output = proc.stderr.read()
            
            if output.find("Error ") != -1 and not good_output(self.input_video,self.output_video):
                self.error = 1

            # If the return code is 1 that means FFMPEG failed, use HANDBRAKE instead
            if self.error == 1:
                Logger.warning("FFMPEG - failure converting %s", os.path.basename(self.input_video))

        except OSError as e:
            if e.errno == os.errno.ENOENT:
                Logger.error("FFMPEG not found, install on your system to use this script")
                sys.exit(0)
            else:
                Logger.info("FFMPEG - converting successful: %s", os.path.basename(self.input_video))

    """----------------------------------------------------------------------------------
    Extract SRT files if they are embedded
    ----------------------------------------------------------------------------------"""
    def extract_srt(self):
        
        #Get file info and Parse it
        try:
            proc =subprocess.Popen([
                FFMPEG,
                '-i', self.input_video,
            ],stdout=None,stderr=subprocess.PIPE)
            output = proc.stderr.read()
        except OSError as e:
            if e.errno == os.errno.ENOENT:
                Logger.error("FFMPEG not found, install on your system to use this script")
                sys.exit(0)

        #Try to match subtitles
        matches1 = re.findall(SUB_PATTERN,output,re.I | re.M)
        matches2 = re.findall(SUB_PATTERN2,output,re.I | re.M)
        
        (offset, finalmatch) = combine_matches(matches1,matches2)
        
        #Check if there is a forced option
        if not finalmatch:
            return 
        
        filename = os.path.basename(self.output_video)[:-4]

        for match in finalmatch:
            forced=''
            if 'forced' in match:
                forced = '.forced'
            prefix=''
            if len(match) == 5: 
                prefix = get_locale(match[1],match[4]) 
            else:
                prefix = get_locale(match[1])

            if prefix.find('forced') != -1:
                srtFile = os.path.join(self.target_dir,filename + prefix + ".srt")
            else:
                srtFile = os.path.join(self.target_dir,filename + prefix + forced + ".srt")

            Logger.info("creating subtitle: {name}".format(name=srtFile))
            proc =subprocess.call([
                FFMPEG,'-y',
                '-i', self.input_video,
                '-map', '0:s:{num}'.format(num=int(match[0])-int(offset)),
                srtFile
            ],stdout=DEV_NULL,stderr=DEV_NULL)
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
        if not find_media_files(folder) and folder != media_path and os.path.dirname(self.input_video) != self.target_dir:
            try:
                shutil.rmtree(folder,True)
                Logger.info("Folder {folder} succesfully removed".format(folder=folder))
                remove_folder(os.path.dirname(folder))
            except OSError as reason:
                Logger.info(reason)


if __name__ == '__main__':
    main(sys.argv)
