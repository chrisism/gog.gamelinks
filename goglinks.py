#!/usr/bin/python

import sys, getopt
import sqlite3
import json
import errno
import os
from shutil import copyfile
import pprint

from datetime import datetime
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement, Comment
from xml.dom import minidom

import http
import urllib.request

import subprocess, sys
import logging

# --- GLOBALS -----------------------------------------------------------------
# Firefox user agents
# USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/68.0'
USER_AGENT = 'Mozilla/5.0 (X11; Linux i586; rv:31.0) Gecko/20100101 Firefox/68.0'

logger = logging.getLogger('gog_links')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('gog_links.log')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

def main(argv):
    gog_path = None
    folder_style = "AEL"
    create_nfo_flag = False
    download_images_flag = False
    create_lnks_flag = False
    overwrite_files_flag = False

    example = 'main.py -g <GOG path> -d <destination path>'

    try:
        opts, args = getopt.getopt(argv,"hg:d:nois:l", \
            ["gog=","destination=","nfo","overwrite","img","style=", "lnk"])
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
        if opt in ("-o", "--overwrite"):
            overwrite_files_flag = True

    if gog_path is None:
        print(example)
        sys.exit(2)

    # load games from GOG db
    games = load_games(gog_path)
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

        logger.info('Adding lnks to shield')
        #C:\Users\<USER>\AppData\Local\NVIDIA Corporation\Shield Apps
        shield_folder = os.path.expanduser('~')
        shield_folder = os.path.join(shield_folder, 'AppData', 'Local', 'NVIDIA Corporation','Shield Apps')
        add_games_to_shield(games, output_folder, shield_folder, overwrite_files_flag)
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
            r.* \
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
        FROM ReleaseProperties AS r \
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
        WHERE isVisibleInLibrary = 1 AND isDlc = 0'

    games = []
    for row in c.execute(q):
        game = Game(row)
        games.append(game)
    
    conn.close()
    return games

def create_nfos(games, output_folder, overwrite_existing):
    nfo_folder = os.path.join(output_folder, 'games')
    if not os.path.exists(nfo_folder):
        os.makedirs(nfo_folder)
    for game in games:

        doc_path = os.path.join(nfo_folder, '{}.nfo'.format(game.sortTitle))
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
    fanart_folder = os.path.join(output_folder, 'fanart')
    cover_folder  = os.path.join(output_folder, 'boxfront')
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

        file_name   = '{}.png'.format(game.sortTitle)
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

        dest_icon   = os.path.join(output_folder, game.sortTitle, 'icon.png')
        dest_fanart = os.path.join(output_folder, game.sortTitle, 'fanart.png')
        dest_cover  = os.path.join(output_folder, game.sortTitle, '{}.tbn'.format(game.sortTitle))
        dest_snap   = os.path.join(output_folder, game.sortTitle, 'snap.png')
    
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
                snap_path = os.path.join(output_folder, game.sortTitle, 'extrasnaps', 'snap{}.png'.format(str(i)))
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

        game_path = os.path.join(lnk_folder, '{}.lnk'.format(game.sortTitle))
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

def add_games_to_shield(games, output_folder, shield_folder, overwrite_existing):
    
    lnk_folder = os.path.join(output_folder, 'games')
    img_folder = os.path.join(output_folder, 'boxfront')
    for game in games:

        img_path = os.path.join(img_folder, '{}.png'.format(game.sortTitle))
        game_path = os.path.join(lnk_folder, '{}.lnk'.format(game.sortTitle))
        if not os.path.exists(game_path):
            logger.debug(' {} not found, skipping'.format(game_path))
            continue
        
        shield_lnk = os.path.join(shield_folder,'{}.lnk'.format(game.sortTitle))
        shield_img_folder = os.path.join(shield_folder, 'StreamingAssets', game.sortTitle) 
        shield_img = os.path.join(shield_img_folder, 'box-art.png')
        if not overwrite_existing and os.path.exists(shield_lnk):
            continue

        try:
            if not os.path.exists(shield_img):
                os.makedirs(shield_img_folder)

            logger.debug('Copying lnk file for {} to {}'.format(game.sortTitle, shield_lnk))
            copyfile(game_path, shield_lnk)
            logger.debug('Copying boxart for {} to {}'.format(game.sortTitle, shield_img))
            
            copyfile(img_path, shield_img)
        except Exception as ex:
            logger.error('(Exception) Object type "{}"'.format(type(ex)))
            logger.error('(Exception) Message "{0}"'.format(str(ex)))
    
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

class Game(object):

    def __init__(self, data_row):
        
        self.id = data_row['releaseKey']
        self.game_id = data_row['gameId']
        
        self.title = json.loads(data_row['title'])['title'] if data_row['title'] else 'Unknown'
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

        self.fanart = images['background'].replace('\\','') if images['background'] is not None else None
        self.icon   = images['squareIcon'].replace('\\','') if images['squareIcon'] is not None else None
        self.cover  = images['verticalCover'].replace('\\','') if images['verticalCover'] is not None else None
 
        self.snaps = []
        if media and 'screenshots' in media:
            for img in media['screenshots']:
                self.snaps.append(img
                    .replace('\\','')
                    .replace('{formatter}', '')
                    .replace('{ext}', 'jpg'))

        self.videos = []
        if media and 'videos' in media:
            for videoMedia in media['videos']:
                self.videos.append(Video(videoMedia))

class Video(object):

    def __init__(self, video_data):
        self.name = video_data['name']
        self.provider = video_data['provider']
        self.videoId = video_data['videoId']

    def get_url(self):
        if self.provider == 'youtube':
            return 'https://youtube.com/embed/{}'.format(self.videoId)

        return self.videoId

if __name__ == "__main__":
    main(sys.argv[1:])