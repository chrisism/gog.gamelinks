#!/usr/bin/python

import sys, getopt
import sqlite3
import json
import errno
import os
from shutil import copyfile
import pprint
import string

from datetime import datetime
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement, Comment
from xml.dom import minidom

import http
import urllib.request

import subprocess, sys
import logging
from logging.handlers import TimedRotatingFileHandler

# --- GLOBALS -----------------------------------------------------------------
# Firefox user agents
# USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/68.0'
USER_AGENT = 'Mozilla/5.0 (X11; Linux i586; rv:31.0) Gecko/20100101 Firefox/68.0'

logger = logging.getLogger('gog_links')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

handler = TimedRotatingFileHandler('gog_links.log', when='D',interval=1, backupCount=14)
handler.setFormatter(formatter)
logger.addHandler(handler)

def main(argv):

    gog_path = None
    folder_style = "AEL"
    create_nfo_flag = False
    download_images_flag = False
    create_lnks_flag = False
    overwrite_files_flag = False
    add_to_shield = False

    example = 'main.py -g <GOG path> -d <destination path>'

    try:
        opts, args = getopt.getopt(argv,"hg:d:nois:la", \
            ["gog=","destination=","nfo","overwrite","img","style=", "lnk", "add"])
    except getopt.GetoptError:
        print(example)
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print(example)
            sys.exit()
        
        if opt in ("-g", "--gog"):
            gog_path = arg
        if opt in ("-d", "--destination"):
            output_folder = arg
        if opt in ("-s", "--style"):
            folder_style = arg

        if opt in ("-n", "--nfo"):
            create_nfo_flag = True
        if opt in ("-i", "--img"):
            download_images_flag = True
        if opt in ("-l", "--lnk"):
            create_lnks_flag = True
        if opt in ("-a", "--add"):
            add_to_shield = True
        if opt in ("-o", "--overwrite"):
            overwrite_files_flag = True

    if gog_path is None:
        print(example)
        sys.exit(2)

    # load games from GOG db
    try:
        games = load_games(gog_path)
    except Exception as ex:
        logger.error('(Exception) Object type "{}"'.format(type(ex)))
        logger.error('(Exception) Message "{}"'.format(str(ex)))
        logger.error('Could not load games from db')
        return
    
    logger.info('loaded {} games'.format(len(games)))

    # create NFO files
    if create_nfo_flag:
        logger.info('Creating NFO files for the games')
        create_nfos(games, output_folder, overwrite_files_flag)
        logger.info('NFO files done')

    # download images
    if download_images_flag:
        logger.info('Downloading images for the games')
        download_images(games, output_folder, overwrite_files_flag, folder_style)
        logger.info('Downloading complete')

    # create lnk files
    if create_lnks_flag:
        logger.info('Creating lnks for the games')
        create_lnks(games, output_folder, overwrite_files_flag)
        logger.info('Creating lnks complete')

    if add_to_shield:
        #C:\Users\<USER>\AppData\Local\NVIDIA Corporation\Shield Apps
        user_folder = os.path.expanduser('~')
        user_folder = os.path.join(user_folder, 'AppData', 'Local')
        nvidia_folder = os.path.join(user_folder, 'NVIDIA', 'NvBackend')
        shield_apps_folder = os.path.join(user_folder, 'NVIDIA Corporation', 'Shield Apps')

        logger.info('Gathering already recognized games by nvidia')
        recognized_games = load_games_from_geforce(nvidia_folder)
        logger.info('Done gathering recognized games')

        logger.info('Adding lnks to shield')
        add_games_to_shield(games, recognized_games, output_folder, shield_apps_folder, overwrite_files_flag)
        logger.info('Adding lnks to shield complete')

def load_games(path):
    db_path = os.path.join(path, 'galaxy-2.0.db')
    logger.debug('connecting to db@{}'.format(db_path))
    conn = sqlite3.connect(db_path)
    conn.row_factory = dict_factory
    c = conn.cursor()
    
    #   GameLinks - All owned games
    #   GamePieceTypes
    #   GamePieces - Game extra info    
    #   InstalledBaseProducts - Installed Gog games (productid, installationpath)
    #   InstalledExternalProducts - Installed ex games (platformid, productid)
    #	Platforms (id, name)
    #	PlayTasks   (SELECT * FROM PlayTasks p left join PlayTaskTypes  pt on  p.typeid = pt.id  left join PlayTaskLaunchParameters as pp on p.id = pp.playtaskid)
    #	ReleaseProperties (releaseKey	isDlc	isVisibleInLibrary	gameId)

    q = 'SELECT \
             u.userId, u.isHidden, r.* \
            ,p.id AS platformId \
            ,IFNULL(p.name, "gog") AS platform \
            ,gpt.value as title \
            ,gps.value as summary \
            ,gpm.value as meta \
            ,gpmd.value as media \
            ,gpi.value as images \
            ,gpo.value AS sort \
            ,CASE \
                WHEN prk.externalId IS NULL AND ig.productId IS NULL THEN 0 \
                WHEN prk.externalId IS NOT NULL AND ie.id IS NULL THEN 0 \
                ELSE 1 \
            END AS Installed \
        FROM UserReleaseProperties AS u \
            LEFT JOIN ReleaseProperties AS r ON u.releaseKey = r.releaseKey \
            LEFT JOIN ProductsToReleaseKeys AS prk ON r.releaseKey = prk.releaseKey \
            LEFT JOIN Platforms AS p ON INSTR(r.releaseKey, p.name) > 0 \
            LEFT JOIN GamePieces AS gpt ON r.releaseKey = gpt.releaseKey \
                INNER JOIN GamePieceTypes gtypes1 ON gpt.gamePieceTypeId = gtypes1.Id AND gtypes1.type = \'title\' \
            LEFT JOIN GamePieces AS gps ON r.releaseKey = gps.releaseKey \
                INNER JOIN GamePieceTypes gtypes2 ON gps.gamePieceTypeId = gtypes2.Id AND gtypes2.type = \'summary\' \
            LEFT JOIN GamePieces AS gpm  ON r.releaseKey = gpm.releaseKey \
                INNER JOIN GamePieceTypes gtypes3 ON gpm.gamePieceTypeId = gtypes3.Id AND gtypes3.type = \'meta\' \
            LEFT JOIN GamePieces AS gpmd ON r.releaseKey = gpmd.releaseKey \
                INNER JOIN GamePieceTypes gtypes4 ON gpmd.gamePieceTypeId = gtypes4.Id AND gtypes4.type = \'media\' \
            LEFT JOIN GamePieces AS gpi  ON r.releaseKey = gpi.releaseKey \
                INNER JOIN GamePieceTypes gtypes5 ON gpi.gamePieceTypeId = gtypes5.Id AND gtypes5.type = \'originalImages\' \
            LEFT JOIN GamePieces AS gpo  ON r.releaseKey = gpo.releaseKey \
                INNER JOIN GamePieceTypes gtypes6 ON gpo.gamePieceTypeId = gtypes6.Id AND gtypes6.type = \'sortingTitle\' \
            LEFT JOIN InstalledBaseProducts AS ig ON ig.productId = prk.gogId \
            LEFT JOIN InstalledExternalProducts AS ie ON ie.id = prk.externalId \
        WHERE isVisibleInLibrary = 1 AND isDlc = 0 AND u.isHidden = 0'

    games = []
    for row in c.execute(q):
        game = Game(row)
        
        if ' demo' in game.title.lower() or \
            ' beta' in game.title.lower() or \
            ' test' in game.title.lower():
            continue

        games.append(game)
    
    conn.close()
    return games

def create_nfos(games, output_folder, overwrite_existing):
    nfo_folder = os.path.join(output_folder, 'games')
    if not os.path.exists(nfo_folder):
        os.makedirs(nfo_folder)
    for game in games:

        doc_path = os.path.join(nfo_folder, '{}.nfo'.format(game.fileTitle))
        if not overwrite_existing and os.path.exists(doc_path):
            continue

        gameXml = Element('game')
        SubElement(gameXml, 'title').text = game.title
        SubElement(gameXml, 'sorttitle').text = game.sortTitle
        SubElement(gameXml, 'year').text = str(game.releaseDate.year) if game.releaseDate is not None else None
        SubElement(gameXml, 'genre').text = ', '.join(game.genres) if game.genres else ''
        SubElement(gameXml, 'developer').text = ', '.join(game.developers) if game.developers else ''
        SubElement(gameXml, 'rating').text = str(int(game.score/10)) if game.score is not None else None
        SubElement(gameXml, 'plot').text = game.summary
        SubElement(gameXml, 'themes').text = ', '.join(game.themes) if game.themes else '' 
        SubElement(gameXml, 'premiered').text = str(game.releaseDate)
        SubElement(gameXml, 'platform').text = str(game.platform)
        SubElement(gameXml, 'is_installed').text = str(game.is_installed)

        if game.fanart is not None:
            fanartXml = SubElement(gameXml, 'fanart')
            SubElement(fanartXml, 'thumb').text = game.fanart
        if game.cover is not None:
            coverXml = SubElement(gameXml, 'cover')
            SubElement(coverXml, 'thumb').text = game.cover
        if game.icon is not None:
            iconXml = SubElement(gameXml, 'icon')
            SubElement(iconXml, 'thumb').text = game.icon

        imagesXml = SubElement(gameXml, 'screenshots')
        for snap in game.snaps:
            SubElement(imagesXml, 'thumb').text = snap

        if game.videos and len(game.videos) > 0:
            SubElement(gameXml, 'trailer').text = str(game.videos[0].get_url())

        videosXml = SubElement(gameXml, 'videos')
        for video in game.videos:
            SubElement(videosXml, 'video').text = video.get_url()
            
        xmldoc = prettify(gameXml)
        try:
            with open(doc_path, 'w', encoding='utf-8') as f:
                f.write(xmldoc)
        except OSError:
            logger.error('(OSError) Cannot write {} file'.format(doc_path))
        except IOError as e:
            logger.error('(IOError) errno = {}'.format(e.errno))
            if e.errno == errno.ENOENT: logger.error('(IOError) No such file or directory.')
            logger.error('(IOError) Cannot write {} file'.format(doc_path))

        logger.debug('  Created NFO file for game {}'.format(game.title))

def download_images(games, output_folder, overwrite_existing, folder_style):
    if folder_style == 'AEL':
        download_images_ael_style(games, output_folder, overwrite_existing)
    else:
        download_images_kodi_style(games, output_folder, overwrite_existing)

def download_images_ael_style(games, output_folder, overwrite_existing):   

    snaps_folder  = os.path.join(output_folder, 'snaps')
    fanart_folder = os.path.join(output_folder, 'fanarts')
    cover_folder  = os.path.join(output_folder, 'boxfronts')
    icon_folder   = os.path.join(output_folder, 'icons')

    if not os.path.exists(snaps_folder):
        os.makedirs(snaps_folder)
    if not os.path.exists(fanart_folder):
        os.makedirs(fanart_folder)
    if not os.path.exists(cover_folder):
        os.makedirs(cover_folder)
    if not os.path.exists(icon_folder):
        os.makedirs(icon_folder)

    for game in games:

        file_name   = '{}.png'.format(game.fileTitle)
        dest_icon   = os.path.join(icon_folder, file_name)
        dest_fanart = os.path.join(fanart_folder, file_name)
        dest_cover  = os.path.join(cover_folder, file_name)
        dest_snap   = os.path.join(snaps_folder, file_name)
    
        if game.cover is not None and (not os.path.exists(dest_cover) or overwrite_existing):
            net_download_img(game.cover, dest_cover)
            logger.debug('  Downloaded cover image for game {}'.format(game.title))
        if game.fanart is not None and (not os.path.exists(dest_fanart) or overwrite_existing):
            net_download_img(game.fanart, dest_fanart)
            logger.debug('  Downloaded fanart image for game {}'.format(game.title))
        if game.icon is not None and (not os.path.exists(dest_icon) or overwrite_existing):
            net_download_img(game.icon, dest_icon)
            logger.debug('  Downloaded icon image for game {}'.format(game.title))
        if len(game.snaps) > 0 and (not os.path.exists(dest_snap) or overwrite_existing):
            net_download_img(game.snaps[0], dest_snap)
            logger.debug('  Downloaded snap image for game {}'.format(game.title))

def download_images_kodi_style(games, output_folder, overwrite_existing):   
    
    for game in games:

        dest_icon   = os.path.join(output_folder, game.fileTitle, 'icon.png')
        dest_fanart = os.path.join(output_folder, game.fileTitle, 'fanart.png')
        dest_cover  = os.path.join(output_folder, game.fileTitle, '{}.tbn'.format(game.fileTitle))
        dest_snap   = os.path.join(output_folder, game.fileTitle, 'snap.png')
    
        if game.cover is not None and (not os.path.exists(dest_cover) or overwrite_existing):
            net_download_img(game.cover, dest_cover)
            logger.debug('  Downloaded cover image for game {}'.format(game.title))
        if game.fanart is not None and (not os.path.exists(dest_fanart) or overwrite_existing):
            net_download_img(game.fanart, dest_fanart)
            logger.debug('  Downloaded fanart image for game {}'.format(game.title))
        if game.icon is not None and (not os.path.exists(dest_icon) or overwrite_existing):
            net_download_img(game.icon, dest_icon)
            logger.debug('  Downloaded icon image for game {}'.format(game.title))
        if len(game.snaps) > 0 and (not os.path.exists(dest_snap) or overwrite_existing):
            net_download_img(game.snaps[0], dest_snap)
            logger.debug('  Downloaded snap#0 image for game {}'.format(game.title))

        if len(game.snaps) > 1:
            i = 1
            for snap in game.snaps[1:]:
                snap_path = os.path.join(output_folder, game.fileTitle, 'extrasnaps', 'snap{}.png'.format(str(i)))
                if not os.path.exists(snap_path) or overwrite_existing:
                    net_download_img(snap, snap_path)
                    logger.debug('  Downloaded snap#{} image for game {}'.format(i, game.title))
                i = i + 1

def create_lnks(games, output_folder, overwrite_existing):
    
    if not os.name == 'nt':
        return

    dir_path = os.path.dirname(os.path.realpath(__file__))
    ps_path = os.path.join(dir_path, 'shortcuts.ps1')

    lnk_folder = os.path.join(output_folder, 'games')
    for game in games:

        game_path = os.path.join(lnk_folder, '{}.lnk'.format(game.fileTitle))
        if not overwrite_existing and os.path.exists(game_path):
            continue
        
        cmd = [ 
            "PowerShell", 
            "-ExecutionPolicy",
             "Unrestricted", 
             "-File", 
             ps_path,
             "E:\\Software\\GOG Galaxy\\GalaxyClient.exe", 
             "/command=runGame /gameId={}".format(game.id),
              game_path]
        #print(' CMD={}'.format(cmd))
        ec = subprocess.call(cmd)
        logger.debug('  Powershell returned: {0:d}'.format(ec))
        logger.debug('  Created shortcut for game {} at {}'.format(game.title, game_path))

def add_games_to_shield(games, recognized_games, output_folder, shield_folder, overwrite_existing):
    
    lnk_folder = os.path.join(output_folder, 'games')
    img_folder = os.path.join(output_folder, 'boxfronts')
    for game in games:

        img_path = os.path.join(img_folder, '{}.png'.format(game.fileTitle))
        game_path = os.path.join(lnk_folder, '{}.lnk'.format(game.fileTitle))

        shield_lnk = os.path.join(shield_folder,'{}.lnk'.format(game.fileTitle))
        shield_img_folder = os.path.join(shield_folder, 'StreamingAssets', game.fileTitle) 
        shield_img = os.path.join(shield_img_folder, 'box-art.png')

        if game in recognized_games:
            logger.warn('  Game {} already recognized. Skipping'.format(game.title))
            if os.path.exists(shield_lnk):
                logger.warn('  Removing lnk file for game {} from Shield'.format(game.title))
                os.remove(shield_lnk)
            continue

        if not os.path.exists(game_path):
            logger.debug(' {} not found, skipping'.format(game_path))
            continue
        
        if not overwrite_existing and os.path.exists(shield_lnk):
            continue

        try:
            if not os.path.exists(shield_img):
                os.makedirs(shield_img_folder)

            logger.debug('Copying lnk file for {} to {}'.format(game.fileTitle, shield_lnk))
            copyfile(game_path, shield_lnk)
            logger.debug('Copying boxart for {} to {}'.format(game.fileTitle, shield_img))
            
            copyfile(img_path, shield_img)
        except Exception as ex:
            logger.error('(Exception) Object type "{}"'.format(type(ex)))
            logger.error('(Exception) Message "{0}"'.format(str(ex)))
    
def load_games_from_geforce(shield_folder):
    db_file = os.path.join(shield_folder, 'journalBS.main.xml')
    xml_data = None 
    
    try:
        xml_data = ET.parse(db_file)
    except OSError:
        logger.error('(OSError) Cannot read {} file'.format(db_file))
    except IOError as e:
        logger.error('(IOError) errno = {}'.format(e.errno))
        if e.errno == errno.ENOENT: logger.error('(IOError) No such file or directory.')
        logger.error('(IOError) Cannot read {} file'.format(db_file))
        
    if xml_data is None:
        return []

    games = []
    
    game_nodes =  xml_data.findall('.//Application/*')
    logger.info('Nvidia has {} games recognized'.format(len(game_nodes)))

    for game_xml in game_nodes:
        
        title_node = game_xml.find('DisplayName')
        sort_title_node = game_xml.find('ShortName')
        stream_supported_node = game_xml.find('IsStreamingSupported')

        logger.debug('  Found Nvidia recognized game: {}'.format(title_node.text))
        if stream_supported_node.text == '0':
            logger.debug('  [SKIP] Streaming not supported. Skipping: {}'.format(title_node.text))
            continue

        game = Game(None)
        game.title = title_node.text
        game.sortTitle = sort_title_node.text.replace('_', ' ')
        game.fileTitle = sort_title_node.text.replace('_', ' ')
        logger.debug('  [ADD] Streaming supported. Adding: {}'.format(title_node.text))
        games.append(game)

    return games

def prettify(elem):
    """Return a pretty-printed XML string for the Element.
    """
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

def net_download_img(img_url, file_path):
    # --- Download image to a buffer in memory ---
    # If an exception happens here no file is created (avoid creating files with 0 bytes).
    try:
        req = urllib.request.Request(img_url)
        # req.add_unredirected_header('User-Agent', net_get_random_UserAgent())
        req.add_unredirected_header('User-Agent', USER_AGENT)
        img_buf = urllib.request.urlopen(req, timeout = 120).read()
    except IOError as ex:
        logger.error('(IOError) Object type "{}"'.format(type(ex)))
        logger.error('(IOError) Message "{0}"'.format(str(ex)))
        return
    except Exception as ex:
        logger.error('(Exception) Object type "{}"'.format(type(ex)))
        logger.error('(Exception) Message "{0}"'.format(str(ex)))
        return

    # --- Write image file to disk ---
    # There should be no more 0 size files with this code.
    try:
        with open(file_path, 'wb') as f:
            f.write(img_buf)
    except IOError as ex:
        logger.error('(IOError) In net_download_img(), disk code.')
        logger.error('(IOError) Object type "{}"'.format(type(ex)))
        logger.error('(IOError) Message "{0}"'.format(str(ex)))
    except Exception as ex:
        logger.error('(Exception) In net_download_img(), disk code.')
        logger.error('(net_download_img) Object type "{}"'.format(type(ex)))
        logger.error('(Exception) Message "{0}"'.format(str(ex)))

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def convert_romans_in_text(s):
    words = s.split()
    converted = []
    for word in words:
        num = romanToInt(word)
        if num > 0:
            converted.append(str(num))
        else:
            converted.append(word)
    return ' '.join(converted)

def romanToInt(s):
    """
    :type s: str
    :rtype: int
    """
    roman = {'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000,'IV':4,'IX':9,'XL':40,'XC':90,'CD':400,'CM':900}
    
    for c in s:
        if not c in roman:
            return -1

    i = 0
    num = 0
    while i < len(s):
        if i+1<len(s) and s[i:i+2] in roman:
            num+=roman[s[i:i+2]]
            i+=2
        else:
            #print(i)
            num+=roman[s[i]]
            i+=1
    
    return num

# Given a text clean it so the cleaned string can be used as a filename.
# 1) Convert any non-printable character into ' '
# 2) Remove special chars
# 3) (DISABLED) Convert spaces ' ' into '_'
def text_str_to_filename_str(title_str):
    not_valid_chars = '\',"*/:<>?\\|'
    cleaned_str_1 = ''.join([i if i in string.printable else ' ' for i in title_str])
    cleaned_str_2 = ''.join([i if i not in not_valid_chars else '' for i in cleaned_str_1])
    #cleaned_str_3 = cleaned_str_2.replace(' ', '_')
    return cleaned_str_2

class Game(object):

    def __init__(self, data_row):
        
        if data_row is None:
            return 

        self.id = data_row['releaseKey']
        self.game_id = data_row['gameId']
        
        self.title = json.loads(data_row['title'])['title'] if data_row['title'] else 'Unknown'
        self.fileTitle = text_str_to_filename_str(self.title)
        self.sortTitle = json.loads(data_row['sort'])['title'] if data_row['sort'] else self.title
        self.summary = json.loads(data_row['summary'])['summary'] if data_row['summary'] else ''

        self.is_installed = data_row['Installed']
        self.platform = data_row['platform']

        meta_data = json.loads(data_row['meta']) if data_row['meta'] else None
        media = json.loads(data_row['media']) if data_row['media'] else None
        images = json.loads(data_row['images']) if data_row['images'] else None

        self.score = meta_data['criticsScore'] if meta_data and 'criticsScore' in meta_data else None
        self.developers = meta_data['developers'] if meta_data and 'developers' in meta_data else None 
        self.genres = meta_data['genres'] if meta_data and 'genres' in meta_data else None
        self.themes = meta_data['themes'] if meta_data and 'themes' in meta_data else None
        self.publishers = meta_data['publishers'] if meta_data and 'publishers' in meta_data else None
        self.releaseDateTimestamp = meta_data['releaseDate'] if meta_data and 'releaseDate' in meta_data else None

        if self.releaseDateTimestamp is not None:
            self.releaseDate = datetime.utcfromtimestamp(self.releaseDateTimestamp) 
        else: self.releaseDate = None

        self.fanart = images['background'].replace('\\','').replace('.webp', '.png') if images['background'] is not None else None
        self.icon   = images['squareIcon'].replace('\\','').replace('.webp', '.png') if images['squareIcon'] is not None else None
        self.cover  = images['verticalCover'].replace('\\','').replace('.webp', '.png') if images['verticalCover'] is not None else None
        self.snaps = []
        if media and 'screenshots' in media:
            for img in media['screenshots']:
                self.snaps.append(img
                    .replace('\\','')
                    .replace('{formatter}', '')
                    .replace('{ext}', 'png'))

        self.videos = []
        if media and 'videos' in media:
            for videoMedia in media['videos']:
                self.videos.append(Video(videoMedia))
        
        # hack
        if '10Wing' in self.fileTitle:
            self.fileTitle = self.fileTitle.replace('10Wing', 'XWing')

    def __eq__(self, other):
        if self.sortTitle.lower() == other.sortTitle.lower():
            return True
        
        converted_lh = convert_romans_in_text(self.sortTitle.upper())
        converted_rh = convert_romans_in_text(other.sortTitle.upper())
        return converted_lh == converted_rh

class Video(object):

    def __init__(self, video_data):
        self.name = video_data['name']
        self.provider = video_data['provider']
        self.videoId = video_data['videoId']

    def get_url(self):
        if self.provider == 'youtube':
            return 'http://www.youtube.com/watch?v={}'.format(self.videoId)

        return self.videoId

if __name__ == "__main__":
    main(sys.argv[1:])