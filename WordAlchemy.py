import tweepy
import random
import psycopg2

# the input filename
categoriesFileName = "categories.txt"

# Insert a single word into Words
INSERT_WORD = "INSERT INTO Base.Words (Word) VALUES (%s);"

# Insert a category into Categories
INSERT_CATEGORY = "INSERT INTO Base.Categories (Category, is_base) VALUES (%s, %s);"

# Insert a single entry of the M:M Words to Categories relationship
INSERT_IS_IN = "INSERT INTO Base.Is_In (Word, Category) VALUES (%s, %s);"

# Select all words that have at least the specified categories,
# to use replace "PutCategoriesHere" with a list of categories
SELECT_WORDS_BY_CATEGORIES = "SELECT Word FROM " \
                                "(SELECT Word FROM " \
                                    "(SELECT Word FROM Base.Is_In WHERE Category IN PutCategoriesHere ) AS t " \
                                "GROUP BY Word HAVING COUNT(*) = (%s))" \
                             " AS relevent_cats;"

# Same as above, but can exclude certain categories
# Replace "PutExcludedCategoriesHere" with the list of excluded categories
SELECT_WORDS_BY_CATEGORIES_AND_EXCLUDE = "SELECT Word FROM " \
                                "(SELECT Word FROM " \
                                    "(SELECT Word FROM Base.Is_In WHERE Category IN PutCategoriesHere AND Category NOT IN PutExcludedCategoriesHere ) AS t " \
                                "GROUP BY Word HAVING COUNT(*) = (%s))" \
                             " AS relevent_cats;"

# Select all words with a given category
SELECT_WORDS_BY_CATEGORY = "SELECT Word FROM Base.Is_In WHERE Category = %s;"

# Select for a specific word, used to see if that word is in the Words table
SELECT_SPECIFIC_WORD = "SELECT Word FROM Base.Words WHERE Word = "

# Select all of the base categories, those that are chosen as the theme of a formula
# (and not modfiers or processes on those words)
SELECT_BASE_CATEGORIES = "SELECT Category FROM Base.Categories WHERE is_base = TRUE;"

# Select a specific category, used to see if that category is in the Categories table
SELECT_CATEGORY = "SELECT Category FROM Base.Categories WHERE Category = %s;"

# Used to clear the database
CLEAR_DATABASE = "TRUNCATE Base.Is_In, Base.Words, Base.Categories;"

# the cursor, initialized in main (so that it can be closed after everything in main is done)
curr = None

# initialize the db, currently only calls refreshDB, used to do more
# and could do more in the future
def init(curr, conn):
    refreshDB(curr, conn)

# Retrieve Categories and Words and store in the Database
# Input file consists of lines of category declarations,
# and then a series of M amount of 1:1 word to category relationships,
# creating an M:M overall relationship
#
# Input File Format:
# "
# category1
# category2
# category3
# ...
# /////
# category1 word1
# category1 word2
# category2 word1
# ...
# "
def refreshDB(curr, conn):
    # open the file
    inputFile = open(categoriesFileName)

    # clear the database. For now, I didn't think a flag to
    # declare if the db was necessary.
    curr.execute(CLEAR_DATABASE)
    conn.commit()

    # whether or not the database is still in category definitions
    in_definitions = True
    for line in inputFile:
        # create categories
        if (in_definitions):
            line = line.strip()
            # if at the divider line, switch to creating relationships
            if (line == "/////"):
                in_definitions = False
                continue

            # else create the category
            lineParts = line.split(" ")
            category = lineParts[0]
            is_base = lineParts[1]
            curr.execute(INSERT_CATEGORY, (category, is_base))

        # create words and relationships
        else:
            lineParts = line.strip().split(" ")

            if (len(lineParts) > 1):
                category = lineParts[0]
                word = lineParts[1]

                # search the database to find if word is in the db already
                curr.execute(SELECT_SPECIFIC_WORD + "\'" + word + "\';")
                if (curr.fetchone() == None):
                    # if not, create a new word entry
                    curr.execute(INSERT_WORD, (word,))

                # insert the relationship
                curr.execute(INSERT_IS_IN, (word, category))
    inputFile.close()


# the twitter API initialization
# not used, since twitter has yet to process my developer application
def setup_api():
    auth = tweepy.OAuthHandler('consumer_key',
             'consumer_secret')
    auth.set_access_token('access_token',
             'access_token_secret')
    return tweepy.API(auth)

# gets a random base category (one used to declare a base theme for the formula)
# @param used_categories is a list of already used categories
def get_base_category(used_categories):
    curr.execute(SELECT_BASE_CATEGORIES)
    categoryList = curr.fetchall()

    selected = []

    while True:
        categoryIndex = random.randint(0, len(categoryList) - 1)
        category = categoryList[categoryIndex][0]
        if(category not in selected):
            selected.append(category)

        if(category not in used_categories):
            break
        elif(len(selected) > len(used_categories)):
            raise Exception("More requests for base categories than valid words available, Selected: ", selected, " CategoryList: ", categoryList, "Used Categories: ", used_categories)

    used_categories.append(category)

    return category

# gets a random word that has at least the categories specified in the categories parameter
# @param categories can either be a single string or a tuple of string categories
# @param used_words is a dictionary mapping category tuples to lists of all the already used words for those categoires
# @param exclude is an optional string or tuple of categories that the word will not be in
def get_word(categories, used_words, exclude = None):

    # change a single string into a tuple
    if (isinstance(categories, str)):
        categories = (categories,)
    if (isinstance(exclude, str)):
        exclude = (exclude,)

    # formatting the categories to be put in the insertion statement
    categories_string = str(categories)
    if(len(categories) == 1):
        categories_string = categories_string[:len(categories_string) - 2] + ")"

    exclude_string = str(exclude)
    if(exclude != None):
        if(len(exclude) == 1):
            exclude_string = exclude_string[:len(exclude_string) - 2] + ")"


    # select all words with fulfilling those categories, and excluding ones in specified categories, if present
    current_select = ""
    if(exclude == None):
        current_select = SELECT_WORDS_BY_CATEGORIES.replace("PutCategoriesHere", categories_string)
    else:
        current_select = SELECT_WORDS_BY_CATEGORIES_AND_EXCLUDE.replace("PutCategoriesHere", categories_string)\
            .replace("PutExcludedCategoriesHere", exclude_string)

    curr.execute(current_select, (len(categories),))
    wordList = curr.fetchall()

    # if no fulfilling words, we have an oversight in the permutations of our categories from the input file
    if(len(wordList) == 0):
        raise Exception("Word not found, categories: " + str(categories))

    # initialize vars for next code paragraph
    selected = []
    if(categories not in used_words.keys()):
        used_words[categories] = []

    # find a word not already used_words for these categories
    used_words_for_categories = used_words[categories]
    while True:
        wordIndex = random.randint(0,len(wordList) - 1)
        word = wordList[wordIndex][0]
        if(word not in selected):
            selected.append(word)

        if(word not in used_words_for_categories):
            break
        elif(len(selected) > len(used_words_for_categories)):
            raise Exception("More requests for words of these categories that valid words available: ", categories, " Selected: ", selected, " WordList: ", wordList, "Exclude: ", exclude, "Used Words: ", used_words_for_categories)

    used_words_for_categories.append(word)

    return word

# Dynamically generates the recipe
def generate_formula():
    # randomly select a formula to use from the available (hardcoded) stock
    formulaNum = random.randint(0, 6)

    formula = []

    used_words = {}
    used_categories = []

    # the initial category for the formula
    category = get_base_category(used_categories)

    # formulaNum = 6

    # generate the first formula
    if(formulaNum == 0):
        first_word = get_word(category, used_words, "hardened")
        modification_word = get_word("modification", used_words, "hardened")
        third_word = get_word(category, used_words, "hardened")
        fourth_word = get_word((category, "hardened"), used_words)
        fifth_word = get_word(category, used_words, "hardened")

        dissolution_word = get_word("dissolution", used_words)
        fusion_word = get_word("fusion_past", used_words)
        fusion_present_word = get_word("fusion_present", used_words)
        separation_word = get_word("separation", used_words)

        formula += "Formula 1: Purification of ", str(first_word), " that is put into the Alloy of Asem\n"
        formula += "Take ", str(first_word), " purified of any imperfections, ", dissolution_word, " it, let it cool.\n"
        formula += "After having well ", fusion_word, " and covered it with ", str(modification_word), " ", dissolution_word, " it again.\n"
        formula += "Crush together some ", str(modification_word), ", some ", str(third_word), ", and some ", fifth_word, ", rub it on the ", str(first_word), " and ", dissolution_word, " a third time\n"
        formula += "After " , fusion_present_word," ", separation_word, " the ", str(first_word), " after having purified it by washing: for it will be like hard ", str(fourth_word), ".\n"
        formula += "Then if you wish to employ it in the manufacture of ", str(fourth_word), " objects, of such a kind that they cannot be found out and which have the hardness of ", str(fourth_word), ",\n"
        formula += "blend four parts of ", str(fourth_word)," and three parts of ", str(first_word), " and the product will become as a ", str(fourth_word), " object.\n"
        formula += "To neutralize, take with a grain of salt."

    # generate the second formula
    elif(formulaNum == 1):
        first_word = get_word(category, used_words)
        second_word = get_word(category, used_words)
        third_word = get_word(category, used_words)
        fourth_word = get_word(category, used_words)

        dissolution_word = get_word("dissolution_plural", used_words)
        transmografication_word = get_word("transmogrification", used_words)
        dissolution_present_word = get_word("dissolution", used_words)
        object_word = get_word("object", used_words)

        formula += "Formula 2: The Doubling of ", str(first_word), "\n"
        formula += "One takes: refined ", str(second_word), " 40 drachmas; "
        formula += str(first_word), ", 8 drachmas; ", str(third_word), " in buttons, 40 drachmas:\n"
        formula += "one first ", dissolution_word, " the ", str(second_word), " and after two heatings, the ", str(
            third_word), "; then the ", first_word, ".\n"
        formula += "When all are ", transmografication_word, ", ", dissolution_present_word ," several times and cool by means of the preceding composition.\n"
        formula += "After having augmented the ", object_word," by these proceedings, clean it with ", str(fourth_word), "\n"
        formula += "The tripling is affected by the same procedure, with weight being proportioned in conformity with what has been stated above.\n"
        formula += "To neutralize, take with a grain of salt."

    # generate the third formula
    elif(formulaNum == 2):
        first_word = get_word(category, used_words)
        second_word = get_word(category, used_words)
        third_word = get_word(category, used_words)
        fourth_word = get_word(category, used_words)


        dissolution_present_word = get_word("dissolution", used_words)
        fusion_container_action_word = get_word("fusion_container_action", used_words)
        dissolution_word = get_word("dissolution", used_words)

        formula += "Formula 3: The Coloration of ", first_word, "\n"
        formula += "To color ", first_word, " to render it fit for usage. \n"
        formula += "(Procure) ", second_word, ", ", third_word, ", and ", fourth_word, " (for) the purification of (the) ", first_word, ";\n"
        formula += dissolution_present_word, " it all and ", fusion_container_action_word, " it in the vessel (which contains it) the ", first_word, " described in the preceding preparation;\n"
        formula += "let it remain some time, (and then) having drawn (the ", first_word, ") from the vessel, ", dissolution_word ," it upon the coals;\n"
        formula += "then again ", fusion_container_action_word , " it in the vessel which contains the above-mentioned preparation;\n"
        formula += "do this several times until it becomes fit for use.\n"
        formula += "To neutralize, take with a grain of salt."

    # generate the fourth formula
    elif(formulaNum == 3):
        second_category = get_base_category(used_categories)

        first_word = get_word(category, used_words)
        second_word = get_word(second_category, used_words)
        third_word = get_word(second_category, used_words)

        fusion_container_action_word = get_word("fusion_container_action_past", used_words)

        formula += "Formula 4: The Falsification of ", first_word, "\n"
        formula += "(Add) ", second_word, " and ", third_word, ", equal parts to one part of ", first_word, ".\n"
        formula += "After the ", first_word, " has been ", fusion_container_action_word, " in the furnace and it has become of good color,\n"
        formula += "throw upon it these two ingredients, and removing (the ", first_word, ") let it cool and the ", first_word, " is seemingly doubled.\n"
        formula += "To neutralize, take with a grain of salt."

    # generate the fifth formula
    elif(formulaNum == 4):
        second_category = get_base_category(used_categories)

        first_word = get_word(category, used_words)
        second_word = get_word(second_category, used_words)
        third_word = get_word(second_category, used_words)
        fourth_word = get_word(category, used_words)
        fifth_word = get_word((category + "-" + second_category), used_words)


        formula += "Formula 5: Manufacture of ", fifth_word ,"\n"
        formula += "...prepared with ", first_word, "; ", second_word, " 2 mina; ", third_word, " in grains, 1 mina;\n"
        formula += "melting first the ", first_word, ", throw on it the ", third_word , " and some talc called ", fourth_word, ", a half to one mina; \n"
        formula += "proceed until you see the ", second_word, " and the ", fourth_word, " melt;\n"
        formula += "after which the remainder will have been dissipated and only the ", second_word, " will remain,\n"
        formula += "then let it cool, and use it as ", fifth_word, " preferable to the genuine.\n"
        formula += "To neutralize, take with a grain of salt."

    # generate the sixth formula
    elif (formulaNum == 5):
        if(category == "literary_techniques"):
            category = get_base_category([category])
        first_word = get_word(category, used_words, ("hardened", "literary_techniques"))
        second_word = get_word("literary_techniques", used_words)

        formula += "Formula 6: Purification of ", first_word, "\n"
        formula += "How ", first_word, " is purified and made brilliant.\n"
        formula += "Take a part of ", first_word, " and an equal weight of ", second_word, ":\n"
        formula += "place in a furnace and keep up the melting until the ", second_word, " has just been consumed;\n"
        formula += "repeat the operation several times until it becomes brilliant.\n"
        formula += "To neutralize, take with a grain of salt."

    # generate the seventh formula
    elif (formulaNum == 6):
        first_word = get_word(category, used_words)
        second_word = get_word(category, used_words)
        third_word = get_word(category, used_words)

        formula += "Formula 7: A Procedure for writing in letters of ", first_word, "\n"
        formula += "To write in letters of ", first_word, ", take some ", second_word, ", pour it in a suitable vessel, and add to it some ", first_word, " in leaves;\n"
        formula += "when the ", first_word, " appears dissolved in the ", second_word, ", agitate sharply;\n"
        formula += "add a little ", third_word, ", 1 grain for example, and, (after) letting stand, write in the letters of ", first_word,".\n"
        formula += "To neutralize, take with a grain of salt."

    return ''.join(formula)

# Sends the tweets for the recipe
def send_tweets():
    # not used, until twitter approves my developer application
    api = setup_api()

    full_text = generate_formula()
    print(full_text)

    # will tweet the tweets when the twitter thing is approved

    # tweetList = full_text.split("\n")
    # for tweet in tweetList:
        # Send the tweet
        # out = api.update_status(tweet)
        # print ('https://twitter.com/WordAlchemy/status/%s' % out.id_str)

    return

if __name__ == "__main__":
    # connect to the database.
    # If you want to run this yourself, you'll need to input your own PostgreSQL database information
    # The Schema for my database is in the "Create Database.txt" file in this directory.
    # You may notice my database is not very secure.
    # Considering that this project is meant to be run by individuals on their machines,
    # I don't think that's an issue.

    conn = psycopg2.connect("dbname=wordAlc user=postgres password=postgres host=localhost")
    curr = conn.cursor()

    # do the actual operations
    init(curr, conn)
    send_tweets()

    # commit the changes to the database
    conn.commit()
