#!/usr/bin/env python3
# $Id: downloader.py 300 2025-08-02 15:17:38Z drew $
#
# git repository
#  https://github.com/ajgallant/mtg-downloader.git
# a fork of
#  https://github.com/Wookappa/mtg-set-dowloader-binder.git
# images compatible with
#  https://github.com/Card-Forge/forge.git

###
#
# downloader.py
#
description = "Magic: The Gathering card image downloader"
# 
# Fetch sets of Magic: The Gathering card images from scryfall.com
# Image filenames are compatible with the Forge rules engine, a MTG player.
#
# The downloader can fetch all cards from a set, query or a list of cards.  
# The list of cards can be specified in a text file, where each line follows
# the format:
#
#  <card_name> [<set>] <card number>  # comment
#  <card_name> (<set>) <card number>
#
# examples:
#  # Elven Wars deck 1.4
#  Mountain [ltr] 300    Mountain from set LTR, card number 300
#  Island (ltr)          Islands from set LTR
#  Soldier               Soldiers from all sets
#  [MOE]                 Card set MOE
#
# Scryfall search
#  https://scryfall.com/docs/syntax
# Scryfall API
#  https://scryfall.com/docs/api/cards
#  https://scryfall.com/docs/api/cards/search
#    set query parameter:    set:eek
#    token query parameter:  is:token
#
# Command line options:
import argparse
arg_parser = argparse.ArgumentParser(description=description, 
    formatter_class=argparse.RawTextHelpFormatter)
arg_parser.add_argument('-s', '--set-names', action='store_true',
    help="""Use set names for card directories\nEx: Ravnicar/Plains.jpg
""")
arg_parser.add_argument('-o', '--output-directory', action='store',
    dest='output_directory', metavar='dir', default='art', 
    help='Directory to store card images')
#arg_parser.add_argument('-h', '--help', action='help')
#
###

import os
import re
import urllib
import datetime
import json
from functools import lru_cache
import requests
# import urllib3  # useful for HTTP requests
from PIL import Image
from ratelimit import limits, sleep_and_retry
# ratelimit sleep_and_retry is best used by a single thread.  conditions and
# semaphores could be used to ensure each thread calls the decorated function
# in turn.

# Disable SSL verification warning
# urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#
# get_request_limited(*args, **kwargs)
# a rate limited wrapper of request.get()
#
# call this function to limit the rate of requests to the Scryfall API
#
@sleep_and_retry
@limits(calls=12, period=1)  # limit to 12 calls per second
def get_request_limited(*args, **kwargs):
    return requests.get(*args, **kwargs)

#
# makedirs(path, exist_ok)
# wrapper of os.makedirs() to reduce redundant calls
#
@lru_cache(256)
def makedirs(path, exist_ok=True):
    return  os.makedirs(path, exist_ok=exist_ok)

#
# get_valid_filename(name)
# converts a string to a valid filename.
#    
# Removes characters that are not alphanumeric or in a list of
# accepted punctuation.
#
def get_valid_filename(name):
    filename = str(name).strip()
    # Perform substitutions
    filename = filename.replace(' // ', '')
    # Remove any characters that are not alphanumeric or accepted punctuation
    return re.sub(r'(?u)[^-\w .;,:+\']', '', filename) # (?u) is unicode regex

#
# get_key(card, set_name)
# generate a unique key for the card based on its set name and card name
#
# append an optional numeric suffix to the filename if it already exists
# e.g. "Mountain" -> "Mountain", "Mountain2", "Mountain3",
#
# cards with multiple card_faces may have two card images.  The file naming
# convention in Forge may be found in:
#  forge-core/src/main/java/forge/card/CardRules.java : getName()
#  forge-core/src/main/java/forge/item/PaperCard.java
#  forge-core/src/main/java/forge/util/ImageUtil.java : getNameToUse()
#
def get_key(card, set_name):
    keys = get_key.keys
    name = get_valid_filename(card['name'])
    key = "{set_name}/{name}".format(set_name=set_name, name=name)
    if not key in keys:
        keys[key] = 1
        return  name
    # duplicate filename.  append a number to the name
    keys[key] += 1
    return  "{name}{number}".format(name=name, number=keys[key])

# names : a dictionary of filenames
#  {filename -> count} 
get_key.keys = dict()

#
# rename_file(old_name, new_name[, dir_path])
# rename a file in the specified directory
#
def rename_file(old_name, new_name, dir_path=None):
    old_file = old_name
    new_file = new_name
    if dir_path:
        # files are in the same directory
        old_file = os.path.join(dir_path, old_name)
        new_file = os.path.join(dir_path, new_name)
    try:
        if os.path.isfile(old_file):
            os.rename(old_file, new_file)
            return  new_file  # the new file path
        else:
            return  None      # old file not found
    except OSError as e:
        # no error handling, just return None
        return  None

#
# write_file(url, file_path)
# download a resource and save it to a file
#
# if the file already exists, overwrite it
# downloads from scryfall.io are not rate limited
#
def write_file(url, file_path):
    with open(file_path, 'wb') as file:
        if not url:
            return  0 # only truncate file
        req = requests.get(url)
        return  file.write(req.content)

#
# find_set(set_code)
# Find a Magic: The Gathering set of cards matching set code
#
# returns a set or None
#
def find_set(set_code):
    url = f"https://api.scryfall.com/sets/{set_code}"
    try:
        response = get_request_limited(url)

        if response.status_code == 200:
            body = response.json()
            return body
        else:
            return None
    except Exception as e: # JSONDecodeError
        return None

#
# get_all_cards_url()
# get the URL for bulk data containing all Magic: The Gathering cards
#
# bulk data files may be very large, in excess of 1GB
#
# returns  URL for the JSON of all MTG cards
#
def get_all_cards_url():
    res = get_request_limited('https://api.scryfall.com/bulk-data')
    content = res.json()
    # response contains URIs for card images, JSON, sets, etc.
    all_cards_uri = None
    for bulk_data in content['data']:
        # confirm type of bulk data
        if bulk_data['type'] == 'all_cards':
            all_cards_uri = bulk_data['download_uri']
            break
    return  all_cards_uri

#
# get_card_data_and_download(output_dir, query_parts, confirm, use_set_names)
# collect card data from the Scryfall API and download the card image
#
# query_parts is a dict(parameter -> value) or a string
#  "name:Mountain set:inv"
#  {"name": "Mountain", "set": "inv"}
# confirm is a boolean; if True, confirm query results before downloading
#
# apply a rate limit to API requests in this function
# use asynchronous IO to download card json and images faster
#
def get_card_data_and_download(output_dir, query_parts, confirm=False, 
                               use_set_names=False):
    if not isinstance(query_parts, str):
        # query_parts is a dict
        query = ' '.join(f'{key}:{val}' for key, val in query_parts.items())
    else:
        # query_parts is a string
        query = query_parts.strip()
        # query_parts = None, query_dict = ...
    
    params = {
        "q": query,
        "unique": "prints",  # select multiple prints of a card
        "include_variations": "true",
        "format": "json"  # content format
    }
    uri = "https://api.scryfall.com/cards/search?" + urllib.parse.urlencode(params)

    try:
        saved = 0
        not_saved = 0

        # query results are paginated
        while uri:
            response = get_request_limited(uri)
            if response.status_code == 404:
                break  # no results found
            if response.status_code != 200:
                raise Exception(f"Request to scryfall failed: \
{response.status_code} {response.reason}")
            
            res = response.json()
            if res['total_cards'] == 0:
                return 0, 0  # no cards found
            
            if confirm and saved + not_saved == 0:
                # confirm the first 10 cards before downloading
                item = 0
                if res['total_cards'] == 1:
                    print('1 card found')
                else:
                    print('{count} cards found'.format(count=res['total_cards']))
                # print up to 10 cards
                for card in res["data"]:
                    if item >= 10:
                        print(' ...')
                        break
                    set_name = card['set'].upper() if not use_set_names \
                        else card['set_name']
                    print(' {set_name}:{name}'.format(set_name=set_name,
                                                      name=card['name']))
                    item += 1
                reply = input('Is this correct? ').strip()
                if reply in ('n', 'N', 'no', 'NO'):
                    not_saved += res['total_cards']
                    break

            for card in res["data"]:
                # save the card image
                # no additional rate limits are required.  save_card_image()
                # makes download requests to scryfall.io
                (stored, not_stored) = save_card_image(output_dir, card, 
                                                       use_set_names)
                if stored > 0:
                    saved += stored
                if not_stored > 0:
                    not_saved += not_stored
        
            if res['has_more'] and res['next_page']:
                uri = res['next_page']
            else:
                uri = None
    except Exception as e:
        print(str(e))

    return saved, not_saved

#
# save_card_image(output_dir, card, use_set_names=False)
# download the card image and store with a unique filename
#
def save_card_image(output_dir, card, use_set_names=False):
    set_name = get_valid_filename(card['set'].upper())
    if use_set_names:
        set_name = get_valid_filename(card['set_name'])
    # initialize output directory for set
    dir_path = os.path.join(output_dir, set_name)
    makedirs(dir_path)

    # get a unique filename and rename previous files if necessary
    def get_filename(card, alt=None):
        if alt:
            prev_name = card['name']
            card['name'] += alt
        key = get_key(card, set_name)
        if alt:
            card['name'] = prev_name
        # check number at end of key
        match = re.search(r'[0-9]{1,}$', key)
        if match and int(match[0]) == 2:
            # rename previous file -> file1
            original = key[:-1]  # remove the last character, a number
            rename_file("{0}.full.jpg".format(original), 
                "{base}1.full.jpg".format(base=original), dir_path)
        return  os.path.join(dir_path, f"{key}.full.jpg")

    saved_count = 0
    not_saved_count = 0

    # download and store the card images
    if 'card_faces' in card and len(card['card_faces']) > 0:
        if 'layout' in card and card['layout'] == 'adventure':
            # adventure cards have an alternate name: card_faces[0]
            write_file(card['image_uris']['large'], 
                      get_filename(card['card_faces'][0]))
            print(f" saved {set_name}:{card['name']}")
            saved_count += 1
        elif 'layout' in card and card['layout'] == 'split':
            # split cards have an alternate name: face[0] + face[1]
            write_file(card['image_uris']['large'], 
get_filename(card['card_faces'][0], card['card_faces'][1]['name']))
            print(f" saved {set_name}:{card['name']}")
            saved_count += 1
        elif 'layout' in card and card['layout'] == 'flip':
            # flip cards are two images: faces[0], flip(faces[1])
            file_0 = get_filename(card['card_faces'][0])
            write_file(card['image_uris']['large'], file_0)
            image = Image.open(file_0)
            pixels = image.transpose(Image.Transpose.ROTATE_180)
            pixels.save(get_filename(card['card_faces'][1]))
            pixels.close()
            image.close()
            print(f" saved {set_name}:{card['name']}")
            saved_count += 1
        elif 'layout' in card and card['layout'] == 'reversible_card':
            # reversibles are not coded in Forge card rules, thus there is no
            # back loaded for this card.  store the back with -bk postfix.
            write_file(card['card_faces'][0]['image_uris']['large'],
                      get_filename(card['card_faces'][0]))
            write_file(card['card_faces'][1]['image_uris']['large'],
                      get_filename(card['card_faces'][1], "-bk"))
            print(f" saved {set_name}:{card['name']}")
            saved_count += 1
        else:
            # transform layout cards have two card images
            for card_face in card['card_faces']:
                write_file(card_face['image_uris']['large'], 
                          get_filename(card_face))
            print(f" saved {set_name}:{card['name']}")
            saved_count += 1
    elif 'image_uris' in card:
        write_file(card['image_uris']['large'], get_filename(card))
        print(f" saved {set_name}:{card['name']}")
        saved_count += 1
    else:
        print(f"No valid image found for card: {card['name']}")
        not_saved_count += 1

    return saved_count, not_saved_count

#
# download_cards_list(output_dir, list_name, use_set_names)
# download card images from a list of card names, sets and card numbers
#
# entries in the list should be formatted as:
#  <card_name> [<set>] <card number>
# example:
#  Mountain [ltr] 300   Mountain from set LTR, card number 300
#  Island [ltr]         Islands from set LTR
#  Soldier              Soldiers from all sets
#  [MOE]                Card set MOE
#
def download_cards_list(output_dir, list_name, use_set_names=False):
    try:
        with open(list_name, "r") as file:
            card_list = file.readlines()  # Read the list of cards from a file
    except FileNotFoundError:
        print(f"File not found: {list_name}")
        return 0, 0
    except Exception as e:
        print(f"Error reading file {list_name}: {str(e)}")
        return 0, 0

    saved_count = 0
    not_saved_count = 0

    # an entry in the list may select multiple cards
    for entry in card_list:
        # truncate at comment
        comment_index = entry.find('#')
        if comment_index >= 0:
            entry = entry[:comment_index]
        entry = entry.strip()  # remove leading and trailing whitespace
        # skip empty lines
        if len(entry) < 1:
            continue

        # find set code in brackets
        set_code_match = re.search(r'(\[|\()(.+)(\]|\))', entry)

        if not set_code_match:
            # only a card name, no set code
            parameters = {'name': entry}
        else:
            # include set code and optionals in query
            parameters = {'set': set_code_match[2]}
            card_name = entry[:set_code_match.start()].strip()
            # ignore null card names
            if len(card_name) > 0:
                parameters['name'] = card_name
            card_number = entry[set_code_match.end()+1:].strip()
            # ignore invalid card numbers
            if len(card_number) > 0 and card_number.isalnum():
                parameters['number'] = card_number

        saved, not_saved = get_card_data_and_download(output_dir, parameters, 
            use_set_names=use_set_names)
        saved_count += saved
        not_saved_count += not_saved

        if saved == 0:
            if not_saved == 0:
                print("No cards match:", entry)
                not_saved_count += 1
            else: # not_saved > 0:
                print("Failed to download cards for:", entry)

    return  saved_count, not_saved_count

#
# download_set(output_dir, set_code, use_set_names)
# download card images from a specific Magic: The Gathering set
#
def download_set(output_dir, set_code, use_set_names=False):
    if not set_code:
        print("Invalid set code: None")
        return 0, 0  # no set code provided
    set_code = set_code.strip().lower()
    if not set_code or not set_code.isalnum():
        print("Invalid set code:", set_code)
        return 0, 0

    return  get_card_data_and_download(output_dir, f'set:{set_code}',
                                       use_set_names=use_set_names)

#
# unit_test()
# run unit tests for the downloader
#
def unit_test():
    global write_file
    # Function to run unit tests for the script
    print("Running unit tests...")
    # set output directory for unit test
    output_dir = os.path.join(os.getcwd(), "unit-test")
    # create the test directory
    makedirs(output_dir)

    # Test 1: get_valid_filename function
    errors = 0
    name = "Test Card Name"
    result = get_valid_filename(name)
    if result != name:
        print("Test 1.1 failed: get_valid_filename returned " + result)
        errors += 1
    name = "Good-Kind?Name*5"
    result = get_valid_filename(name)
    if result != "Good-KindName5":
        print("Test 1.2 failed: get_valid_filename returned " + result)
        errors += 1
    # end of test 1
    if errors == 0:
        print('Test 1 passed')

    # Test 2: save_card_image function
    errors = 0
    # disable fetch URL in write_file
    write_file_orig = write_file
    write_file = lambda url, file_path: write_file_orig(None, file_path)

    # Test 2.1: save land cards
    card = {
        'set': 'UT2-1',
        'set_name': "Unit Test 2.1",
        'name': "Mountain",
        'image_uris': {'large': 'https://api.scryfall.com/cards/300/large.jpg'}
    }
    # write_file("http://127.0.0.1/image.jpg", os.path.join(output_dir, "image.jpg"))
    save_card_image(output_dir, card, True)
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + ".full.jpg")):
        print("Test 2.1 failed: save_card_image did not save Mountain")
        errors += 1
    card['name'] = "Island"
    save_card_image(output_dir, card, True)
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + ".full.jpg")):
        print("Test 2.1 failed: save_card_image did not save Island")
        errors += 1
    
    # Test 2.2: save the same land card, renaming subsequent images
    card = {
        'set': 'UT2-2',
        'set_name': "Unit Test 2.2",
        'name': "Island",
        'image_uris': {'large': 'https://api.scryfall.com/cards/300/large.jpg'}
    }
    save_card_image(output_dir, card, True)
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + ".full.jpg")):
        print("Test 2.2 failed: save_card_image did not save Island")
        errors += 1
    save_card_image(output_dir, card, True)
    if os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + ".full.jpg")):
        print("Test 2.2 failed: save_card_image did not rename Island to Island1")
        errors += 1
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + "1.full.jpg")):
        print("Test 2.2 failed: save_card_image did not save Island1")
        errors += 1
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + "2.full.jpg")):
        print("Test 2.2 failed: save_card_image did not save Island2")
        errors += 1
    save_card_image(output_dir, card, True)
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + "3.full.jpg")):
        print("Test 2.2 failed: save_card_image did not save Island3")
        errors += 1

    # Test 2.3: save multiple sets
    card = {
        'set': 'UT2-3',
        'set_name': "Unit Test 2.3.1",
        'name': "Plains",
        'image_uris': {'large': 'https://api.scryfall.com/cards/300/large.jpg'}
    }
    save_card_image(output_dir, card, True)
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + ".full.jpg")):
        print("Test 2.3.1 failed: save_card_image did not save properly")
        errors += 1
    card['set_name'] = "Unit Test 2.3.2"
    save_card_image(output_dir, card, True)
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + ".full.jpg")):
        print("Test 2.3.2 failed: save_card_image did not save properly")
        errors += 1
    if not os.path.isfile(os.path.join(output_dir, 'Unit Test 2.3.1', card['name'] + ".full.jpg")):
        print("Test 2.3.2 failed: errant renaming of file")
        errors += 1
    card['set_name'] = "Unit Test 2.3.3"
    save_card_image(output_dir, card, True)
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + ".full.jpg")):
        print("Test 2.3.3 failed: save_card_image did not save properly")
        errors += 1
    # end of test 2
    if errors == 0:
        print("Test 2 passed")

    # Test 3: save cards with multiple faces
    errors = 0
    card = {
        'set': 'UT3',
        'set_name': "Unit Test 3",
        'name': "Red Bandit // Crimson Zombie",
        'layout': "transform",
        'card_faces': (
            {'name': 'Red Bandit', 'image_uris': {'large': 'https://api.scryfall.com/cards/300/large_front.jpg'}},
            {'name': 'Crimson Zombie', 'image_uris': {'large': 'https://api.scryfall.com/cards/300/large_front.jpg'}}
        )
    }
    save_card_image(output_dir, card, False)
    if not os.path.isfile(os.path.join(output_dir, card['set'], card['card_faces'][0]['name'] + ".full.jpg")):
        print("Test 3.1.1 failed: save_card_image did not save front of transform card")
        errors += 1
    if not os.path.isfile(os.path.join(output_dir, card['set'], card['card_faces'][1]['name'] + ".full.jpg")):
        print("Test 3.1.1 failed: save_card_image did not save rear of transform card")
        errors += 1
    # test with duplicate
    save_card_image(output_dir, card, False)
    if not os.path.isfile(os.path.join(output_dir, card['set'], card['card_faces'][0]['name'] + "2.full.jpg")):
        print("Test 3.1.2 failed: save_card_image did not save front of transform card 2")
        errors += 1
    if not os.path.isfile(os.path.join(output_dir, card['set'], card['card_faces'][1]['name'] + "2.full.jpg")):
        print("Test 3.1.2 failed: save_card_image did not save rear of transform card 2")
        errors += 1
    if not os.path.isfile(os.path.join(output_dir, card['set'], card['card_faces'][0]['name'] + "1.full.jpg")):
        print("Test 3.1.2 failed: save_card_image did not rename front of transform card 1")
        errors += 1
    if not os.path.isfile(os.path.join(output_dir, card['set'], card['card_faces'][1]['name'] + "1.full.jpg")):
        print("Test 3.1.2 failed: save_card_image did not rename rear of transform card 1")
        errors += 1
    # reversible cards
    card = {
        'set': 'UT3',
        'set_name': "Unit Test 3",
        'name': "Blue Bird // Blue Bird",
        'layout': "reversible_card",
        'card_faces': (
            {'name': 'Blue Bird', 'image_uris': {'large': 'https://api.scryfall.com/cards/300/large_front.jpg'}},
            {'name': 'Blue Bird', 'image_uris': {'large': 'https://api.scryfall.com/cards/300/large_front.jpg'}}
        )
    }
    save_card_image(output_dir, card, False)
    if not os.path.isfile(os.path.join(output_dir, card['set'], card['card_faces'][0]['name'] + ".full.jpg")):
        print("Test 3.2 failed: save_card_image did not save front of reversible")
        errors += 1
    if not os.path.isfile(os.path.join(output_dir, card['set'], card['card_faces'][1]['name'] + "-bk.full.jpg")):
        print("Test 3.2 failed: save_card_image did not save rear of reversible")
        errors += 1
    # adventure card
    card = {
        'set': 'UT3',
        'set_name': "Unit Test 3",
        'name': "George of the Jungle // Banana Tally",
        'layout': "adventure",
        'image_uris': {'large': 'https://api.scryfall.com/cards/300/large.jpg'},
        'card_faces': (
            {'name': 'George of the Jungle'}, #, 'image_uris': {'large': 'https://api.scryfall.com/cards/300/large_front.jpg'}},
            {'name': 'Banana Tally'}  #, 'image_uris': {'large': 'https://api.scryfall.com/cards/300/large_front.jpg'}}
        )
    }
    save_card_image(output_dir, card, False)
    if not os.path.isfile(os.path.join(output_dir, card['set'], 
                                       card['card_faces'][0]['name'] + ".full.jpg")):
        print("Test 3.3 failed: save_card_image did not save adventure card")
        errors += 1
    if os.path.isfile(os.path.join(output_dir, card['set'], card['card_faces'][1]['name'] + ".full.jpg")):
        print("Test 3.3 failed: save_card_image saved second face of adventure card")
        errors += 1
    # split card
    card = {
        'set': 'UT3',
        'set_name': "Unit Test 3",
        'name': "Python // Java",
        'layout': "split",
        'image_uris': {'large': 'https://api.scryfall.com/cards/300/large.jpg'},
        'card_faces': (
            {'name': 'Python'}, #, 'image_uris': {'large': 'https://api.scryfall.com/cards/300/large_front.jpg'}},
            {'name': 'Java'}  #, 'image_uris': {'large': 'https://api.scryfall.com/cards/300/large_front.jpg'}}
        )
    }
    save_card_image(output_dir, card, False)
    if not os.path.isfile(os.path.join(output_dir, card['set'], 
                                       card['card_faces'][0]['name'] + card['card_faces'][1]['name'] + ".full.jpg")):
        print("Test 3.4 failed: save_card_image did not save adventure card")
        errors += 1
    if os.path.isfile(os.path.join(output_dir, card['set'], card['card_faces'][1]['name'] + ".full.jpg")):
        print("Test 3.4 failed: save_card_image saved second face of adventure card")
        errors += 1
    # end of Test 3
    if errors == 0:
        print("Test 3 passed")
    
    # Test 4: find sets
    errors = 0
    magic_set = find_set('inv')
    if not magic_set or magic_set['code'] != 'inv':
        print("Test 4.1 failed: Invasion set not found")
        errors += 1
    magic_set = find_set('vito')
    if magic_set:
        print("Test 4.2 failed: bogus set found")
        errors += 1
    # end of test 4
    if errors == 0:
        print("Test 4 passed")

    # Test 5: Download cards from lists/long.txt
    errors = 0
    list_path = os.path.join("lists", "long.txt")
    
    # skip test if list file doesn't exist
    prev_dir = output_dir
    output_dir = os.path.join(output_dir, 'Unit Test 5')
    if not os.path.exists(list_path):
        print(f"Test 5 aborted: card list {list_path} not found")
        errors += 1
    else:
        # calculate expected results from download
        expected = (16, 5)  # saved, not_saved
        # download cards
        result = download_cards_list(output_dir, list_path)
        if expected != result:  # recursive equality for tuples - wow
            print('Test 5: result {0} did not match expected {1}'.format(result, expected))
            errors += 1
    output_dir = prev_dir
    # end of test 5
    if errors == 0:
        print("Test 5 passed")

    print("Unit test complete")

# begin main script
if __name__ == "__main__":
    # optionally run unit tests
    testing = False
    if testing:
        unit_test()
        exit(0)  # Exit after running unit tests

    # parse command line arguments
    args = arg_parser.parse_args()
    
    # write card images to an output directory
    output_directory = args.output_directory
    if not os.path.isabs(args.output_directory):
        output_directory = os.path.join(os.getcwd(), args.output_directory)
    makedirs(output_directory)
    print("Writing files in", output_directory, '\n')

    option = None
    # prompt the user to select an option
    while option not in ('1', '2', '3'):
        if option is not None:
            print("Invalid option. Please try again.\n")
        option = input("Choose a download method:\n\
 1. Set of cards\n\
 2. List of cards\n\
 3. Scryfall query\n\
Select: ")

    print(end='\n')
    if option == '1':
        # Download a set
        # prompt the user to enter the set code
        set_code = input("Enter the set code (e.g., 'inv'): ")
        start = datetime.datetime.now()
        (saved, not_saved) = download_set(output_directory, set_code, 
                                          args.set_names)
    elif option == '2':
        # Download cards from a list
        # prompt the user to enter the name of the card list
        list_name = input("Enter the name of the card list file: ").strip()
        start = datetime.datetime.now()
        (saved, not_saved) = download_cards_list(output_directory, list_name,
                                                 args.set_names)
    elif option == '3':
        # Download a Scryfall query
        print("Queries are key-value pairs like name:Mountain set:bng")
        # prompt the user to enter the query
        query = input("Query: ")
        start = datetime.datetime.now()
        (saved, not_saved) = get_card_data_and_download(output_directory, query,
            confirm=True, use_set_names=args.set_names)
        if saved == 0 and not_saved == 0:
            print("No cards found")
    else:
        print("Invalid option selected.")
        exit(0)

    end = datetime.datetime.now()
    print(f"\nTotal cards saved:     {saved}")
    print(f"Total cards not saved: {not_saved}")

    elapsed_time = end - start  # Calculate the elapsed time of transfer
    print("Elapsed time:", elapsed_time)