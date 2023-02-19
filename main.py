# twitch_liveleech - Copyright 2022 IRLToolkit Inc.
# Usage: twitch_liveleech.py [channel] [dump path] [final path]
# Modified by crashahotrod to make more plex friendly and rename logs for multi-channel support

import sys
channelName = sys.argv[1]
downloadPath = sys.argv[2]
finalPath = sys.argv[3]
logname= str(channelName) + ".log"
muxlogname = str(channelName) + "_mux.log"
downloadlogname = str(channelName) + "_download.log"
import logging
logging.basicConfig(handlers=[logging.FileHandler(logname), logging.StreamHandler()], level=logging.INFO, format="%(asctime)s [%(levelname)s] [{}] %(message)s".format(channelName))

import os
import string
import time
import datetime
import requests
import streamlink
import ffmpeg

twitchClientId = os.getenv('TWITCH_LIVELEECH_CLIENT_ID')
twitchClientSecret = os.getenv('TWITCH_LIVELEECH_CLIENT_SECRET')

months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
sleepDuration = 45

sl = streamlink.Streamlink()
sl.set_plugin_option('twitch', 'disable-hosting', True)
sl.set_plugin_option('twitch', 'disable-ads', True)
sl.set_plugin_option('twitch', 'disable-reruns', True)

def append_file(fileName, data):
    with open(fileName, 'a') as f:
        f.write('\n')
        f.write(data.decode())

def get_channel_title():
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
    return data['data'][0]['title']

def check_generate_path(pathPrefix):
    date = datetime.date.today()
    dir = '{}/{}_{}'.format(pathPrefix, months[date.month - 1], date.year)
    if not os.path.exists(dir):
        logging.info('Creating directory: {}'.format(dir))
        os.makedirs(dir)

if __name__ == '__main__':
    if not twitchClientId or not twitchClientSecret:
        logging.critical('Missing TWITCH_LIVELEECH_CLIENT_ID or TWITCH_LIVELEECH_CLIENT_SECRET env variable(s).')
        os._exit(1)

    while True:
        logging.info('Sleeping for {} seconds...'.format(sleepDuration))
        time.sleep(sleepDuration)
        logging.info('Done.')

        try:
            streams = sl.streams('https://twitch.tv/{}'.format(channelName))
        except streamlink.exceptions.PluginError:
            logging.error('Failed to fetch stream via streamlink.')
            continue
        if not streams:
            logging.info('No streams are available.')
            continue
        elif 'best' not in streams:
            logging.error('`best` stream not available!')
            break
        logging.info('Stream found! Opening ffmpeg...')

        fullDownloadPath = '{}/{}.flv'.format(downloadPath, int(time.time()))
        logging.info('Writing download to: {}...'.format(fullDownloadPath))
        stream = ffmpeg.input(streams['best'].url).output(fullDownloadPath, vcodec='copy', acodec='aac')
        out, err = ffmpeg.run(stream, capture_stdout=True, capture_stderr=True)
        append_file(downloadlogname, err)
        logging.info('Stream ended!')

        check_generate_path(finalPath)

        title = get_channel_title()
        validChars = "-.() %s%s" % (string.ascii_letters, string.digits)
        title = ''.join(c for c in title if c in validChars)

        date = datetime.date.today()
        season = "Season " + str(date.strftime("%y%m"))
        episode = str(date.day) + "01" #need to find a way to increment this value for multiple streams in the same day
        fullPath = '{}/{}/{}_{}_{}.mp4'.format(finalPath, season, episode, title, int(time.time()))
        logging.info('Muxing file {} to final path {}'.format(fullDownloadPath, fullPath))
        mux = ffmpeg.input(fullDownloadPath).output(fullPath, vcodec='copy', acodec='copy')
        out, err = ffmpeg.run(mux, capture_stdout=True, capture_stderr=True)
        append_file(muxlogname, err)
        logging.info('Done.')
