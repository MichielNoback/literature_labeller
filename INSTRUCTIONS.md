# Literature Labeler

**Personal info**
session name: `labeller_helper`

## Background

The desired outcome of this project is a dashboard app that can be used to manually label a collection of Pubmed publications.
It should be generic in the sense that a config file will specify what labels can be added, and what names they represent.

The project should be carried out in several stages. These are outlined below.

## Stage 1 

Create a random sample dataset from `data/pubmed_scan_2026_02_02_all_data_filtered.txt`: take 15000 entries and write to `data/pubmed_scan_2026_02_02_sample.txt`
Note: Both these files should be in `.gitignore`

## Stage 2
Decision-making:

- which technology to use for the dashboard. Please inform about the best candidates for this. Preferred base language is Python.
- is csv (or similar) better than Excel as data format?
- is it best to write to the original input file, or create a copy of it to write labels to, or even create an embedded sqlite database? Labelling will certainly be done in several stages, and the result of all sessions should be kept together.

## Stage 3

Specify and create an appropriate config file. My first ideas are:
- path to dataset with pubmed publications to be labelled; in the first example, use `data/pubmed_sample_with_keywords.cs`
- path to a keywords file; in the first example, use `data/PESTICIDE_TERMS_20260323_with_compound_data.csv`
- set of possible labels; in the first example, use as specified in the listing below

label:name:display_name
0:negative:Negative
1:human_animal;Human/Animal
2:environmental:Environmental
3:foodstuff:Foods and Fluids
4:other:Other

## Stage 4

Build the app.
This one has several substages/features that may be added later as well (after building has already started)
These are listed below.

### Read and verify data
- Read the config file. 
- Verify file contents:
    - The file with pubmed publications should have the following columns: pmid, title, abstract. Any other columns can simply be hidden and maintained in the output.
    - the file with keywords is read-only and should at least contain the columns: ID,name,synonyms
- Read the data files

### Display entries one at a time for labelling

- The dashboard should pick an entry from the collection, and display the following:
    - pmid
    - title
    - abstract
- The title and abstract should have highlighting of keywords that are found in the keywords file
    - this should be case-insensitive, and also take into consideration alternative spelling schemes for chemicals (e.g, a space instead of hyphen)
- The dashboard should provide the user with a choice of label (by mouse-click or by keyword shortcut); efficiency in user experience is very important here
- Store the chosen label, including a timestamp (e.g. 2026-07-10;21:21)
- Include an edit decision option: by pressing the arrow-left key, the last annotated entry should reappear and be editable with a new label.
- At the end of a session, the user clicks "Exit". All new data (labels) should be written to a csv file where data of previous sessions are also present. 

