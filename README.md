# DEPRECATED

THIS PROJECT IS NO LONGER BEING MAINTAINED OR UPDATED WITH FRESH COMMITS:

Work is dedicated to it's successor: plexarizer


# conv2mp4-py
Python 2.7 script that recursively searches through a defined file path and converts MKV, AVI, FLV, and MPEG files to MP4 using handbrake (with AAC audio). It then refreshes a Plex library, and deletes the source file upon success and moves the new files into the defines directory (Plex Library directories for example). Fails over to ffmpeg encode if conversion failure is detected. The purpose of this script is to reduce the number of transcodes performed by a Plex server, by processing all files into an MP4 format.<br><br>
<b><u>Dependencies</u></b><br>
This script requires Python, Filebot, ffmpeg and Handbrake to be installed on your computer. You can download them from here:<br>
<a href="https://www.python.org/downloads/">Python</a><br>
<a href="https://www.filebot.net/#download">FileBot</a><br>
<a href="https://ffmpeg.org/download.html">ffmpeg</a><br>
<a href="https://handbrake.fr/downloads.php">Handbrake</a><br><br>
<b>Usage</b><br>
You need to launch either with the bundled launcher script or manually from a commandline:
  There is only one argument: the path to the media files<br><br>
<b>User-defined variables</b><br>
There are several user-defined variables you will need to edit using notepad or a program like <a href="https://notepad-plus-plus.org/download/v6.9.2.html">Notepad++</a>.<br><br>
<i>NOTE: to use a mapped drive, you must run <code>net use z: \\server\share /persistent:yes</code> as the user you're going to run the script as (generally Administrator) prior to running the script.</i><br>

<b>FFMPEG</b> = path to ffmpeg.exe<br>
<b>HANDBRAKE</b> = path to HandBrakeCLI.exe <br>
<b>FILEBOT</b> = path to FileBot.exe <br>
<b>MEDIA_PATH</b> = Path to your uncoverted media <br>

<b>ENABLE_PLEX_UPDATE</b> Set to True to enable the script to update your server<br>
<i>NOTE: Requires PLEX_IP and PLEX_TOKEN to work.</i><br>
<b>PLEX_IP</b> = the IP address and port of your Plex server (for the purpose of refreshing its library)<br>
<b>PLEX_TOKEN</b> = your Plex server's token (for the purpose of refreshing its library).<br>
<i>NOTE: See https://support.plex.tv/hc/en-us/articles/204059436-Finding-your-account-token-X-Plex-Token for instructions on retrieving your Plex server's token. Your Plex server's token is also easy to retrieve with Couchpotato or SickRage.</i><br>

<b>MAX_CONVERT_ITEMS</b> = Maximum number of files to convert in one go<br>
<b>LOCALE</b> = Three digit code for your language for example for Hungarian it's 'hun' <br>

<b>Target Folders for converted files</b> <br>
<b>MOVIE_TARGET</b> = Path where you want your movies<br>
<b>TVSHOW_TARGET</b> = Path where you want your TV SHows<br>
<b>LANG_MOVIE_TARGET</b> = Path where you want your foreign language movies<br>
<b>LANG_TVSHOW_TARGET</b> = Path where you want your foreign langue Tv Shows<br>

<b>FOREIGN</b> = Set to true if you want the script to take foreign language into account<br>
<b>EXTRACT_SRT</b> = Whether to extract the subtitles from files into external SRTs (External SRT files don't trigger transcoding, while embedded might)<br>

<b>REMOVE_OLD</b> = Whether to remove the files that have been already converted and are no longer needed<br>
