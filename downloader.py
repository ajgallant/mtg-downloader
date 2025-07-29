#!/usr/bin/env python3
# $Id: downloader.py 297 2025-07-29 18:11:41Z drew $

###
#
# downloader.py - Magic: The Gathering card image downloader
# 
# Fetch sets of Magic: The Gathering card images from scryfall.com
#
# The downloader can fetch all cards from a set, query or a list of cards.  
# The list of cards can be specified in a text file, where each line follows
# the format:
#
#  <card_name> [<set>] <card number>
#
# examples:
#  Mountain [ltr] 300    Mountain from set LTR, card number 300
#  Island [ltr]          Islands from set LTR
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
# git repository
#  https://github.com/ajgallant/mtg-downloader.git
# a fork of
#  https://github.com/Wookappa/mtg-set-dowloader-binder.git
#
###

import os
import re
import datetime
import json
#import ijson
import requests
import urllib3
import urllib.request
from ratelimit import limits, sleep_and_retry
# ratelimit sleep_and_retry is best used by a single thread.  conditions and
# semaphores could be used to ensure each thread calls the decorated function
# in turn.

# Disable SSL verification warning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
# get_valid_filename(name)
# convert string to a valid filename
#
def get_valid_filename(name):
    filename = str(name).strip()
    # Perform substitutions
    filename = filename.replace(' // ', '-+')
    # Remove any characters that are not alphanumeric or accepted punctuation
    return re.sub(r'(?u)[^-\w .;,:+\']', '', filename) # (?u) is unicode regex

#
# get_unique_filename(card)
# generate a unique filename for the card based on its set name and card name
#
# append an optional numeric suffix to the filename if it already exists
# e.g. "Mountain" -> "Mountain", "Mountain2", "Mountain3",
#
def get_unique_filename(card):
    names = get_unique_filename.names

    if 'image_uris' in card:
        name = get_valid_filename(card['name'])
    elif 'type_line' in card and card['type_line'] != 'Card // Card':
        if 'card_faces' in card: # and len(card['card_faces']) == 2
            name = get_valid_filename(card['card_faces'][0]['name'])
    elif 'layout' in card and card['layout'] == 'reversible_card':
        if 'card_faces' in card: # and len(card['card_faces']) == 2:
            name = get_valid_filename(card['card_faces'][0]['name'])

    key = "{set_name}/{name}".format(set_name=card['set_name'], name=name)
    if not key in names:
        names[key] = 1
        return  name
    # duplicate filename.  append a number to the name
    names[key] += 1
    return  "{name}{number}".format(name=name, number=names[key])

# names : a dictionary of filenames
#  {filename -> count} 
get_unique_filename.names = dict()

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
# writefile(url, file_path)
# download a resource and save it to a file
#
# if the file already exists, overwrite it
# downloads from scryfall.io are not rate limited
#
def writefile(url, file_path):
    with open(file_path, 'wb') as file:
        if not url:
            return  0 # only truncate file
        req = requests.get(url)
        return  file.write(req.content)

#
# check_set_exists(set_code)
# check if a Magic: The Gathering set exists based on its set code
#
# returns a set or None
#
def check_set_exists(set_code):
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
# return a download URL for the card JSON
#
def get_all_cards_url():
    res = get_request_limited('https://api.scryfall.com/bulk-data')
    content = res.json()
    # response contains URIs for card images, JSON, sets, etc.
    return content['data'][3]['download_uri']

#
# get_card_data_and_download(query_parts, confirm)
# collect card data from the Scryfall API and download the card image
#
# query_parts is a dict(parameter -> value) or a string
#  "name:Mountain set:inv"
#  {"name": "Mountain", "set": "inv"}
# confirm is a boolean; if True, confirm query results before downloading
#
# apply a rate limit to this function as it may be called frequently
def get_card_data_and_download(query_parts, confirm=False):
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
                    print(' {set_name}:{name}'.format(set_name=card['set_name'],
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
                (stored, not_stored) = save_card_image(card)
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
# save_card_image(card)
# download the card image and store with a unique filename
#
def save_card_image(card):
    set_name = get_valid_filename(card['set_name']) # part of file path
    dir_path = os.path.join(output_dir, set_name)
    os.makedirs(dir_path, exist_ok=True)

    # get a unique filename and rename previous files if necessary
    def get_filename(card):
        name = get_unique_filename(card)
        if len(name) > 1 and name[-1] == '2':
            # rename previous file -> file1
            original = name[:-1]  # remove the last character, a number
            rename_file("{0}.full.jpg".format(original), 
                "{base}1.full.jpg".format(base=original), dir_path)
        return  name

    #collector_number = get_valid_filename(card['collector_number']) # card num
    name = get_filename(card)
    file_path = file_path_front = file_path_rear = None
    saved_count = 0
    not_saved_count = 0

    # join the file path with the card name
    if 'image_uris' in card:
        file_path = os.path.join(dir_path, f"{name}.full.jpg")
    elif 'type_line' in card and card['type_line'] != 'Card // Card':
        if 'card_faces' in card: # and len(card['card_faces']) == 2:
            file_path_front = os.path.join(dir_path, f"{name} front.full.jpg")
            file_path_rear = os.path.join(dir_path, f"{name} rear.full.jpg")
    elif 'layout' in card and card['layout'] == 'reversible_card':
        if 'card_faces' in card: # and len(card['card_faces']) == 2:
            file_path_front = os.path.join(dir_path, f"{name} front.full.jpg")
            file_path_rear = os.path.join(dir_path, f"{name} rear.full.jpg")

    # download the card image and save it to the file path
    if file_path is not None:
        writefile(card['image_uris']['large'], file_path)
        print(f" saved {set_name}:{card['name']}")
        saved_count += 1
    elif file_path_front is not None and file_path_rear is not None:
        writefile(card['card_faces'][0]['image_uris']['large'],
                  file_path_front)
        print(f" saved {set_name}:{card['card_faces'][0]['name']}")
        writefile(card['card_faces'][1]['image_uris']['large'], file_path_rear)
        print(f" saved {set_name}:{card['card_faces'][1]['name']}")
        saved_count += 1
    else:
        print(f"No valid image found for card: {card['name']}")
        not_saved_count += 1

    return saved_count, not_saved_count

#
# download_cards_list(list_name)
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
def download_cards_list(list_name):
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
        entry = entry.strip()  # remove leading and trailing whitespace
        if len(entry) < 2 or entry[0] == '#':
            # skip empty lines and comments
            continue

        # find set code in brackets
        set_code_match = re.search(r'(\[)(.+)(\])', entry)

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

        saved, not_saved = get_card_data_and_download(parameters)
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
# download_set(set_code)
# download card images from a specific Magic: The Gathering set
#
def download_set(set_code):
    if not set_code:
        print("Invalid set code: None")
        return 0, 0  # no set code provided
    set_code = set_code.strip().lower()
    if not set_code or not set_code.isalnum():
        print("Invalid set code:", set_code)
        return 0, 0

    return  get_card_data_and_download(f'set:{set_code}')

#
# unit_test()
# run unit tests for the downloader
#
def unit_test():
    global output_dir, writefile
    # Function to run unit tests for the script
    print("Running unit tests...")
    # set output directory for unit test
    output_dir = os.path.join(os.getcwd(), "test")
    # create the test directory
    os.makedirs(output_dir, exist_ok=True)

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
    if errors == 0:
        print('Test 1 passed')

    # Test 2: save_card_image function
    errors = 0
    # disable fetch URL in writefile
    writefile_orig = writefile
    writefile = lambda url, file_path: writefile_orig(None, file_path)

    # Test 2.1: save land cards
    card = {
        'set_name': "Unit Test 2.1",
        'name': "Mountain",
        'image_uris': {'large': 'https://api.scryfall.com/cards/300/large.jpg'}
    }
    # writefile("http://127.0.0.1/image.jpg", os.path.join(output_dir, "image.jpg"))
    save_card_image(card)
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + ".full.jpg")):
        print("Test 2.1 failed: save_card_image did not save Mountain")
        errors += 1
    card['name'] = "Island"
    save_card_image(card)
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + ".full.jpg")):
        print("Test 2.1 failed: save_card_image did not save Island")
        errors += 1
    
    # Test 2.2: save the same land card, renaming subsequent images
    card = {
        'set_name': "Unit Test 2.2",
        'name': "Island",
        'image_uris': {'large': 'https://api.scryfall.com/cards/300/large.jpg'}
    }
    save_card_image(card)
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + ".full.jpg")):
        print("Test 2.2 failed: save_card_image did not save Island")
        errors += 1
    save_card_image(card)
    if os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + ".full.jpg")):
        print("Test 2.2 failed: save_card_image did not rename Island to Island1")
        errors += 1
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + "1.full.jpg")):
        print("Test 2.2 failed: save_card_image did not save Island1")
        errors += 1
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + "2.full.jpg")):
        print("Test 2.2 failed: save_card_image did not save Island2")
        errors += 1
    save_card_image(card)
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + "3.full.jpg")):
        print("Test 2.2 failed: save_card_image did not save Island3")
        errors += 1

    # Test 2.3: save multiple sets
    card = {
        'set_name': "Unit Test 2.3.1",
        'name': "Plains",
        'image_uris': {'large': 'https://api.scryfall.com/cards/300/large.jpg'}
    }
    save_card_image(card)
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + ".full.jpg")):
        print("Test 2.3.1 failed: save_card_image did not save properly")
        errors += 1
    card['set_name'] = "Unit Test 2.3.2"
    save_card_image(card)
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + ".full.jpg")):
        print("Test 2.3.2 failed: save_card_image did not save properly")
        errors += 1
    if not os.path.isfile(os.path.join(output_dir, 'Unit Test 2.3.1', card['name'] + ".full.jpg")):
        print("Test 2.3.2 failed: errant renaming of file")
        errors += 1
    card['set_name'] = "Unit Test 2.3.3"
    save_card_image(card)
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['name'] + ".full.jpg")):
        print("Test 2.3.3 failed: save_card_image did not save properly")
        errors += 1
    if errors == 0:
        print("Test 2 passed")

    # Test 3: save card with multiple faces
    errors = 0
    card = {
        'set_name': "Unit Test 3",
        'name': "Red Bandit // Crimson Zombie",
        'layout': "reversible_card",
        'card_faces': (
            {'name': 'Red Bandit', 'image_uris': {'large': 'https://api.scryfall.com/cards/300/large_front.jpg'}},
            {'name': 'Crimson Zombie', 'image_uris': {'large': 'https://api.scryfall.com/cards/300/large_front.jpg'}}
        )
    }
    save_card_image(card)
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['card_faces'][0]['name'] + " front.full.jpg")):
        print("Test 3 failed: save_card_image did not save front of Two-Faced Card")
        errors += 1
    if not os.path.isfile(os.path.join(output_dir, card['set_name'], card['card_faces'][0]['name'] + " rear.full.jpg")):
        print("Test 3 failed: save_card_image did not save rear of Two-Faced Card")
        errors += 1
    if errors == 0:
        print("Test 3 passed")
    
    # Test 4: check_set_exists
    errors = 0
    magic_set = check_set_exists('inv')
    if not magic_set or magic_set['code'] != 'inv':
        print("Test 4.1 failed: Invasion set not found")
        errors += 1
    magic_set = check_set_exists('vito')
    if magic_set:
        print("Test 4.2 failed: bogus set found")
        errors += 1

    if errors == 0:
        print("Test 4 passed")
    print("Unit test complete")

# begin main script
if __name__ == "__main__":
    # optionally run unit tests
    testing = False
    if testing:
        unit_test()
        exit(0)  # Exit after running unit tests

    output_dir = os.path.join(os.getcwd(), "art") # write card images to output_dir
    os.makedirs(output_dir, exist_ok=True)
    print("Writing files in", output_dir, '\n')

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

    print() # '\n'
    if option == '1':
        # Download a set
        # prompt the user to enter the set code
        set_code = input("Enter the set code (e.g., 'inv'): ")
        start = datetime.datetime.now()
        (saved, not_saved) = download_set(set_code)
    elif option == '2':
        # Download cards from a list
        # prompt the user to enter the name of the card list
        list_name = input("Enter the name of the card list file: ").strip()
        start = datetime.datetime.now()
        (saved, not_saved) = download_cards_list(list_name)
    elif option == '3':
        # Download a Scryfall query
        print("Queries are key-value pairs like name:Mountain set:bng")
        # prompt the user to enter the query
        query = input("Query: ")
        start = datetime.datetime.now()
        (saved, not_saved) = get_card_data_and_download(query, confirm=True)
        if saved == 0 and not_saved == 0:
            print("No cards found")
    else:
        print("Invalid option selected.")
        exit(0)

    end = datetime.datetime.now()
    print(f"\nTotal cards saved:     {saved}")
    print(f"Total cards not saved: {not_saved}")

    elapsed_time = end - start  # Calculate the elapsed time
    print("Elapsed time:", elapsed_time)
