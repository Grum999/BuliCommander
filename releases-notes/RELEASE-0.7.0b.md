# Buli Commander :: Release 0.7.0b [2021-xx-xx]

## Beta release!
Plugin is now stable enough to be considered in *beta* version instead of previous *alpha* state.


## Implement *Search*
A search functionality has been implemented and let user to search for files/images with specific characteristics.

### Basic search
The basic search interface can be used for most common searches:
- Source path with miscellaneous options
- File properties (name, path, size, date/time)
- Image properties (width, height, aspect ratio, ...)

![Basic search](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-7-0b_search_basic.jpeg)

Result is displayed in current file panel.

### Advanced search
The advanced search interface use a node system to allow to build very complex searches.
- Multiple source path
- Combination of files & images properties filtering
- Multiple output possibilities with sort

![Advanced search](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-7-0b_search_advanced.jpeg)


Results from advanced search interface can be plugged with *Export files list* tools to generate different report type:
- text files
- pdf document
- krita document
- png/jpeg sequences

### Console
When search is executed, it could take more or less time, according to number of files to analyse and search complexity.

Search progress is displayed in a console:
![Search console](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-7-0b_search_console.jpeg)

A search in progress can be cancelled.

### Save & Load search definition
For user doing frequent identical searches, search definition can be saved and loaded.


## File panels

### New fields
New fields have been added to file panel, and it's not possible to select which one are visible:
![Search console](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-7-0b_filespanel_fields.jpeg)

### Grid view
A grid view mode has been added:
![Search console](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-7-0b_filespanel_gridview.jpeg)

### Selections
Selected items are kept in panel when content is updated (files added, deleted, updated; even if not managed by Buli Commander)
- Do not reload content, but do update
- Improve sort refresh to avoid flickering effects


## Improve *Export files list*

### Save & Load export definition
It's now possible to save and load export definition; no need to reconfigure them each time :-)

### Available fields & order
Some new fields are available for export.
Fields can be re-ordered by drag-n-drop.

![Export file list](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-7-0b_search_console.jpeg)



## Improve image information

### Krita files - *Animated images*
Review method to determinate if Krita file is animated.
Also improve provided informations about animation:
- Frame rate
- Rendered frames (start, end, number of frames, duration)
- Last frame (number, duration)
- Total keyframes (find through all layers)

![Animated image information](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-7-0b_infopanel-image_animatedkra.jpeg)

### Krita files - *All*
Add Krita version from which document has been created/edited


### All files
Add new properties:
- Resolution
- Image dimension in unit (mm, cm, in) if resolution is available
- Image ratio
- Image number of pixels

![Information panel](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-7-0b_infopanel-imgnfo.jpeg)

Also improve preview for images with transparency (checkerboard not impacted anymore by pan&zoom actions)


## Improve performances
- Review how metadata & thumbnail cache are built and stored to improve performances
- Improved asynchronous thumbnail loading


## Recognized files format
The following files format are taken in account:
- KRZ
- BMP




## Improve UI
User interface has been slightly improved:
- Create directory dialog box
- Delete file/directory dialog box
  *+Warning displayed if at least one directory is not empty*
- Copy/Move file/directory dialog box
- Review most of dialog boxes (messages, confirmation, ...)
- Improve clipboard panel for url for which download failed (display and error status + error message)
- Review console for conversion files dialog box
- Sliders for thumbnail size now display current selected size
- An option allows to move **Buli Commander** menu entry from *Tools > Scripts* to *File*
- Add possibility from Krita settings (*Settings > Configure Krita... > Keyboard Shortcut >> Scripts*) to define a shortcut to open Buli Commander


## Fix bug - *Read Krita files*
- Some animated files weren't considered as animated by Buli Commander
- Some files with reference images (linked instead of embedded) weren't properly read


## Fix bug - *Specific to Windows*
- Monospace font is now properly applied in interface
- Copy/Move was not working due to unescaped separator `\` in paths
- Export files tool is now working on Windows
- A "Copy file" action from windows explorer now properly load files (if image files) into clipboard


## Fix bug - *Miscellaneous*
- Fix compatibility with Krita 5
- After cache was cleared, it was not possible anymore to regenerate it
- Files for which extension was not lowercase were not recognized as valid files and not visible in panel list
- If zoom level was changed during thumbnail loading, progress bar was not hidden when load process was finished
- Copy/Move was not working properly if target path was renamed
- When a document without image preview (or image preview not able to load) was selected, a python script message error was displayed
- When a document without image preview (directory, non image file or not thumbnail preview activated) was selected, size of Icon was growing each time selected document was changed
- When theme was changed in Krita, a python script message error about 'autoreload' was displayed
- When from one panel (located in directory A) a directory B was deleted, if opposite panel was located to deleted directory (or subdirectory of deleted directory), panel refresh was not properly made and mouse cursor was stuck on "wait"
- When Buli Commander is defined to be automatically opened at startup, if user had time to open a document before start/end of plugin initialization, a script error was raised
- Fix miscellaneous minor bugs



## Technical improvements - *Use & enhance common plugin library PkTk*
Use of PkTk library, that provides common modules, classes & widget.
And also most classes that can be re-used for other plugins have been moved to PkTk library.
*Note: PkTk library is not yet available in its own repository, need to wait for that*
