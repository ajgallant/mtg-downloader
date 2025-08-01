# MTG Scryfall Downloader

The MTG Scryfall Downloader will download sets of [Magic: The Gathering](https://magic.wizards.com/en) card images from [Scryfall](https://scryfall.com/). Image filenames are compatible with the MTG game [Forge](https://card-forge.github.io/forge/) for Mac OS and Linux.  Additionally, it includes a script to generate a `.HTML` file for Binder.

## Scripts

- `downloader.py`: The downloader enables you to download card images for a specific Magic: The Gathering set from Scryfall using the Scryfall API. It prompts the user to enter the set code, then proceeds to download the card images into the `art` directory. The script relies on the [Scryfall API](https://scryfall.com/docs/api) to discover cards and `scryfall.io` for card image transfer.<p>
Batches of cards enumerated in a text file may also be downloaded. The downloader reads the card names, set codes, and card numbers from the file and retrieves the corresponding card data and images from Scryfall. The downloaded images are saved in the `art` directory.<p>
For more advanced card selection, the user may download the results of a [Scryfall query](https://scryfall.com/docs/syntax) after confirming the query results.

- `Binder_Generator.py`: Generates an `.HTML` page that represents a card binder for the Magic: The Gathering cards downloaded using the MTG Set Scryfall Downloader script. The generated HTML file, named `binder.html`, provides a visual representation of the downloaded cards, organized in a grid-like format. It includes interactive features such as image previews, pagination, and navigation buttons to browse through the card collection.

## Prerequisites

Before using the scripts, make sure you have [Python](https://www.python.org/downloads/) version 3.11 and git installed on your system.

## Usage

1. Clone the repository to your local machine:

   ``
   git clone https://github.com/ajgallant/mtg-downloader.git
   ``

2. Navigate to the repository directory:

   ``
   cd mtg-downloader
   ``

3. Install the package dependencies using the Python package manager, pip:

  ``
  pip install -r requirements.txt
  ``

4. Run the desired script.<p>

   #### Download Card Images
   
   Start the downloader script:
	
	``downloader.py``
	
	Then choose from three options for content selection:
	
	(1) Select card images from a specific set by entering the set code at the prompt.
	   
	(2) Select card images from a list of cards by providing the path to the text file containing the list at the prompt. Each line of the file selects a group of cards to be downloaded. It should be formatted as follows:<br>
		
 	``CardName [SetCode] CardNumber``
	
	 <p>
	 - *CardName* the name of the card, without any additional spaces.
	 - *SetCode* the set code, enclosed in brackets or parens.
	 - *CardNumber* the card number within the set.

    For example, the "cards.txt" file could be structured:
    </p>
	
	 ```
	 # Cards for the Competition 2022 deck
    Black Lotus   [UNL]   1
    Force of Will (ALL)
    Brainstorm
    (iko)
    [ALL] 17
     ```

   <p>
   	Make sure each selection is on a separate line and that each field is separated by spaces.  If Scryfall finds no cards which match a line in the list, then it will print a warning and continue downloading cards in the list.
	    
	 (3) Select card images from the results of a Scryfall query.  The downloader will print the first 10 results of the query and begin the download after confirmation.
	 
	 Upon conclusion of the download, the card images may be found in the `art` directory.

    #### Generate Binder
    
    Execute the Binder script:

     ``python Binder_Generator.py``
     
    At the prompt, select an image folder containing the downloaded Magic: The Gathering card images.
        
    1. Select the image folder:        
      You will be presented with a list of folders in the `art/` directory.
      Enter the number corresponding to the desired image folder.
    2. Specify the grid size:
      Enter the number of rows and columns you want to display in the grid.
    3. The default grid size is 8 rows and 4 columns.
    4. The binder.html file will be generated based on your selections.
        
    Open the binder.html file in a web browser to view the card binder representation of the downloaded Magic: The Gathering cards.
    
    The generated HTML page provides an interactive and visually appealing way to browse through your downloaded card collection. It allows you to view card images, navigate between pages, and explore the cards within the binder.
    
    Please note that the `Binder_Generator.py` should be executed after running the `downloader.py` to download the card images. Ensure that the downloaded card images are present in the designated ``art`` directory before running `Binder_Generator.py`.

## Future Enhancements

- Select the image size and quality from three URIs: small, normal, and large.
- Asynchronous transfer of images and search results.
- Support a tokenized file name format specified in a configuration file.
- Publish v1.0 of the ``mtg-downloader`` Python module and define a public interface + classes.  Exported functions could be renamed, annotated ##Exported## and use additional parameters.

## Note

- Make sure to comply with the terms of use of the Scryfall API and the API usage policies.
- The proper functioning of the scripts relies on the availability of the Scryfall API. Ensure that the API is accessible and operational before running the scripts.
- These scripts are provided "as is" without any warranty. The author assumes no responsibility for any damages arising from the use of these scripts.