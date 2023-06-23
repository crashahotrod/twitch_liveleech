# twitch_liveleech - Copyright 2022 IRLToolkit Inc.
# Usage: main.py [mode] [channel] [dump path] [final path]
# Modified by crashahotrod to add the following features:
    #Make output more plex friendly
    #Rename logs for multi-channel support
    #Disable ads on subscribed channels
    #Add kick.com support

import sys
mode = str(sys.argv[1]) #kick or twitch
channelName = str(sys.argv[2])
downloadPath = sys.argv[3]
finalPath = sys.argv[4]
logname= channelName + "_" + mode + ".log"
muxlogname = channelName + "_" + mode + "_mux.log"
downloadlogname = channelName + "_" + mode + "_download.log"
import logging
logging.basicConfig(handlers=[logging.FileHandler(logname), logging.StreamHandler()], level=logging.INFO, format="%(asctime)s [%(levelname)s] [{}] %(message)s".format(channelName))

import os
import re
import string
import time
import datetime
import requests
import streamlink
import ffmpeg
import cloudscraper
months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
sleepDuration = 35
sl = streamlink.Streamlink()
twitchClientId = os.getenv('TWITCH_LIVELEECH_CLIENT_ID')
twitchClientSecret = os.getenv('TWITCH_LIVELEECH_CLIENT_SECRET')
#Disable Ads on Subscribed channels https://streamlink.github.io/cli/plugins/twitch.html#authentication
twitchAuthorization = os.getenv('TWITCH_LIVELEECH_AUTHORIZATION')
twitchAPIheader={'Authorization' : twitchAuthorization}

if(mode == "twitch"):
    sl.set_plugin_option('twitch', 'disable-hosting', True)
    sl.set_plugin_option('twitch', 'disable-ads', True)
    sl.set_plugin_option('twitch', 'disable-reruns', True)
    sl.set_plugin_option('twitch', 'api-header', twitchAPIheader)
elif(mode == "kick"):
    pass
else:
    logging.critical("Invalid mode argument please specify kick or twitch")
    os._exit(1)

def append_file(fileName, data):
    with open(fileName, 'a') as f:
        f.write('\n')
        f.write(data.decode())

def get_channel_title(old):
    if(mode == "twitch"):
        req = requests.post('https://id.twitch.tv/oauth2/token?client_id={}&client_secret={}&grant_type=client_credentials'.format(twitchClientId, twitchClientSecret))
        if req.status_code != requests.codes.ok:
            logging.warning('Failed to get Twitch app auth token due to HTTP error. Code: {} | Text: {}'.format(req.status_code, req.text))
            return 'UNKNOWN TITLE'
        twitchAuthorization = req.json()['access_token']
        headers = {'Client-Id': twitchClientId, 'Authorization': 'Bearer ' + twitchAuthorization}
        req = requests.get('https://api.twitch.tv/helix/users?login={}'.format(channelName.lower()), headers=headers)
        if req.status_code != requests.codes.ok:
            logging.warning('Failed to get Twitch user id due to HTTP error. Code: {} | Text: {}'.format(req.status_code, req.text))
            return 'UNKNOWN TITLE'
        channelId = req.json()['data'][0]['id']
        req = requests.get('https://api.twitch.tv/helix/channels?broadcaster_id={}'.format(channelId), headers=headers)
        if req.status_code != requests.codes.ok:
            logging.warning('Failed to get channel title due to HTTP error. Code: {} | Text: {}'.format(req.status_code, req.text))
            return 'UNKNOWN TITLE'
        data = req.json()
        title = data['data'][0]['title']
        logging.info('Found Video Title: {}'.format(title))
        return title
    elif(mode == "kick"):
        scraper = cloudscraper.create_scraper()
        url = ('https://kick.com/api/v1/channels/{}'.format(channelName))
        req = scraper.get(url)
        if req.status_code != requests.codes.ok:
            logging.warning('Failed to get channel title due to HTTP error. Code: {} | Text: {}'.format(req.status_code, req.text))
            return 'UNKNOWN TITLE'
        data = req.json()
        req.close()
        if "session_title" in data['livestream']:
            title = data['livestream']['session_title']
            logging.info('Found Video Title: {}'.format(title))
            return(title)
        else:
            if (old != "") or (old != "UNKNOWN TITLE"):
                return old
            else:
                logging.warning('Failed to get channel title due to API error. Code: {} | Text: {}'.format(req.status_code, req.text))
                return 'UNKNOWN TITLE'
    else:
        logging.critical("Invalid mode argument please specify kick or twitch")
        os._exit(1)

def check_generate_path(pathPrefix):
    date = datetime.date.today()
    dir = '{}/{}_{}'.format(pathPrefix, months[date.month - 1], date.year)
    if not os.path.exists(dir):
        logging.info('Creating directory: {}'.format(dir))
        os.makedirs(dir)

def check_full_path(fpath, fname, iter):
    logging.info('Checking full path: {}'.format(fpath))
    if not os.path.exists(fpath):
        logging.info('Creating directory: {}'.format(fpath))
        os.makedirs(fpath)
    filename = fname + str(iter)
    for filepath in os.listdir(fpath):
        if filename in filepath:
            iter += 1
            return check_full_path(fpath, fname, iter)
    return iter

if __name__ == '__main__':
    if not twitchClientId or not twitchClientSecret:
        logging.critical('Missing TWITCH_LIVELEECH_CLIENT_ID or TWITCH_LIVELEECH_CLIENT_SECRET env variable(s).')
        os._exit(1)

    while True:
        success = False
        logging.info('Sleeping for {} seconds...'.format(sleepDuration))
        time.sleep(sleepDuration)
        logging.info('Done.')

        try:
            if(mode == "twitch"):
                streams = sl.streams('https://twitch.tv/{}'.format(channelName))
            elif(mode == "kick"):
                #scraper = cloudscraper.create_scraper()
                #url = ('https://kick.com/api/v1/channels/{}'.format(channelName))
                #req = scraper.get(url)
                #data = req.json()
                streams = sl.streams('https://kick.com/{}'.format(channelName))
                #streams = sl.streams(data['playback_url'])
            else:
                logging.critical("Invalid mode argument please specify kick or twitch")
                os._exit(1)
        except streamlink.exceptions.PluginError:
            logging.error('Failed to fetch stream via streamlink.')
            #req.close()
            continue
        except Exception as e:
            logging.warning('Failed to record stream. Code: {}'.format(e))
            #req.close()
            continue
        if not streams:
            logging.info('No streams are available.')
            continue
        elif 'best' not in streams:
            logging.error('`best` stream not available!')
            break
        logging.info('Stream found! Opening ffmpeg...')
        title = get_channel_title("")
        fullDownloadPath = '{}/{}.flv'.format(downloadPath, int(time.time()))
        logging.info('Writing download to: {}...'.format(fullDownloadPath))
        stream = ffmpeg.input(streams['best'].url).output(fullDownloadPath, vcodec='copy', acodec='aac')
        out, err = ffmpeg.run(stream, capture_stdout=True, capture_stderr=True)
        if err.returncode == 0:
            success = True
        append_file(downloadlogname, err)
        logging.info('Stream ended!')

        #check_generate_path(finalPath)

        title = get_channel_title(title)
        validChars = "-.() %s%s" % (string.ascii_letters, string.digits)
        title = ''.join(c for c in title if c in validChars)
        logging.info('Modified Title: {}'.format(title))
        date = datetime.date.today()
        season = date.strftime("%y%m")
        day = str(date.day)
        ctime = int(time.time())
        partPath = '{}/Season {}/'.format(finalPath, season)
        logging.info('Part Path: {}'.format(partPath))
        partFile = '{} - s{}e{}'.format(channelName, season, day)
        logging.info('Part File: {}'.format(partFile))
        partIter = check_full_path(partPath, partFile, 1)
        logging.info('Part Iter: {}'.format(partIter))
        fullPath = '{}{}{} - {}.mp4'.format(partPath, partFile, partIter, title)
        logging.info('Muxing file {} to final path {}'.format(fullDownloadPath, fullPath))
        mux = ffmpeg.input(fullDownloadPath).output(fullPath, vcodec='copy', acodec='copy')
        out, err = ffmpeg.run(mux, capture_stdout=True, capture_stderr=True)
        if (err.returncode == 0) and success:
            os.remove(fullDownloadPath)
        append_file(muxlogname, err)
        logging.info('Done.')
