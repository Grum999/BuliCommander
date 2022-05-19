# Buli Commander :: Release 0.8.0b [2022-xx-xx]

## File panels

### Grid view mode - File/Image information
A grid view mode has been improved: it's now possible to define, through settings, informations to display with thumbnail.

*Settings for grid view mode*
![Settings](./../screenshots/r0-8-0b_settings_files-gridview.jpeg)
*--> Drag'n'drop properties to reorder*

*Grid view mode: properties "Over" thumbnails*
![File panel-grid mode Over](./../screenshots/r0-8-0b_files-gridview-over.jpeg)

*Grid view mode: properties on "Bottom side" of thumbnails*
![File panel-grid mode Over](./../screenshots/r0-8-0b_files-gridview-bottom.jpeg)

### Markers
Markers are set to files and allows to manually prepare selections.

#### Why markers?
It's already possible to select files, so why markers? What's the difference?

Selection in BuliCommander works as usually in list: it's possible to make multi-selection with <kbd>Shift</kbd> and <kbd>Ctrl</kbd> modifiers.

When a file is selected without pressing a modifier key, current selection is replaced by a new one: the selected file.
It's the standard about how selections works within a list.

Markers allow to prepare selection.

#### How to use markers?
The menu *Edit* provides some new functionalities to work with markers:

| Menu item | Shortcut | Function |
| --- | --- | --- |
| `Select marked` | <kbd>Ctrl</kbd>+<kbd>M</kbd> | Select all marked files |
| `Mark/Unmark` | <kbd>Space</kbd> | Invert marked state of current item and select next item |
| `Mark all` | <kbd>Ctrl</kbd>+<kbd>Space</kbd> | Mark all files |
| `Mark none` | <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Space</kbd> | Unmark all files |
| `Invert marks` | <kbd>Shift</kbd>+<kbd>Space</kbd> | Invert marked state for all files |

> Notes:
> - Changing selection have no impact on marked files
> - Changing directory have no impact on marked files
>   - Changing directory and going back to a directory where some files have been marked, they're still here
>   - Marked files are kept for current session only: when BuliCommander is closed, marks are lost
> - Marked files are for current panel only
>   - If both panels are on the same directory, you can have different marked files
> - When files are marked, current selected items are unchanged except for `Mark/Unmark` action

Main usage is to walk through files in directory with <kbd>Up</kbd>/<kbd>Down</kbd> arrow keys and mark files for which characteristics are interesting.
Once all interesting files are marked, made a selection and then work on selected files.

Marked files are highlighted by a small triangle in bottom/right side

*A marked file in list view*
![Marked file in listview](./../screenshots/r0-8-0b_files-listview-marked.jpeg)

*A marked file in grid  view*
![Marked file in gridview](./../screenshots/r0-8-0b_files-gridview-marked.jpeg)


### Multiple files selection
With version 0.8.0b, when multiple files are selected, properties for the last selected/unselected file are provided in informations panel (with previous version, a message _"No preview for multiple selection"_ was displayed)
