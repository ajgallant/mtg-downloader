# MTG Scryfall Downloader

The MTG Scryfall Downloader will download sets of Magic: The Gathering card images from Scryfall. Image filenames are compatible with the MTG game Forge for Mac OS and Linux.  Additionally, it includes a script to generate a `.HTML` file for Binder.

## Scripts

- `downloader.py`: This script enables you to download card images for a specific Magic: The Gathering set from Scryfall using the Scryfall API. It prompts the user to enter the set code, then proceeds to download the card images into the `art` directory. The script relies on the Scryfall API to discover cards and `scryfall.io` for card images.<p>
This script also allows you to download card images from a list of cards specified in a text file. It reads the card names, set codes, and card numbers from the file and retrieves the corresponding card data and images from Scryfall. The downloaded images are saved in the `art` directory.

- `Binder_Generator.py`: Generates an `.HTML` page that represents a card binder for the Magic: The Gathering cards downloaded using the MTG Set Scryfall Downloader script. The generated HTML file, named `binder.html`, provides a visual representation of the downloaded cards, organized in a grid-like format. It includes interactive features such as image previews, pagination, and navigation buttons to browse through the card collection.

## Prerequisites

Before using the scripts, make sure you have Python (version 3.8+) installed on your system.<p>
Install the package dependencies using the Python package manager, pip:

```shell
pip install -r requirements.txt
```

## Usage

1. Clone the repository to your local machine:

   ```shell
   git clone https://github.com/ajgallant/mtg-downloader.git
   ```

2. Navigate to the repository directory:

   ```shell
   cd mtg-downloader
   ```

3. Run the desired script:

   - For downloading card images, start the downloader script:

     ```shell
     downloader.py
     ```
     Select the desired option:
     1. Download card images from a specific set by entering the set code at the prompt.
   
     2. Download card images from a list of cards by providing the path to the text file containing the list at the prompt. Each line of the file selects a group of cards to be downloaded. It should be formatted as follows:

            ```
            CardName [SetCode] CardNumber
            ```
            
            - `CardName` the name of the card, without any additional spaces.
            - `SetCode` the set code, enclosed in brackets.
            - `CardNumber` the card number within the set.
            
            For example, the "cards.txt" file could be structured:
            
            ```
            # Cards for the Competition 2022 deck
            Black Lotus   [UNL]   1
            Force of Will [ALL]
            Brainstorm
            [iko]
            [ALL] 17
            ```
         
         Make sure each selection is on a separate line and that each field is separated by spaces.  If Scryfall finds no cards which match a line in the list, then it will print a warning and continue downloading cards in the list.
     
     Upon conclusion of the download, the card images may be found in the `art` directory.

   - For generating Binder:

     ```shell
     python Binder_Generator.py
     ```
        This will prompt you to select an image folder containing the downloaded Magic: The Gathering card images.
        
        1. Select the image folder:        
          You will be presented with a list of folders in the `art/` directory.
          Enter the number corresponding to the desired image folder.
        2. Specify the grid size:
          Enter the number of rows and columns you want to display in the grid.
        3. The default grid size is 8 rows and 4 columns.
        4. The binder.html file will be generated based on your selections.
        
        Open the binder.html file in a web browser to view the card binder representation of the downloaded Magic: The Gathering cards.
        
        The generated HTML page provides an interactive and visually appealing way to browse through your downloaded card collection. It allows you to view card images, navigate between pages, and explore the cards within the binder.
        
        Please note that the `Binder_Generator.py` script should be executed after running the `downloader.py` script to download the card images. Ensure that the downloaded card images are present in the designated art directory before running `Binder_Generator.py`.

## Note

- Make sure to comply with the terms of use of the Scryfall API and the API usage policies when using the scripts.
- The proper functioning of the scripts relies on the availability of the Scryfall API. Ensure that the API is accessible and operational before running the scripts.
- These scripts are provided "as is" without any warranty. The author assumes no responsibility for any damages arising from the use of these scripts.