# Buli Commander :: Release 0.5.0a [YYYY-MM-DD]


## Implement function *Rename*

It's now possible to rename files & directories directly from *BuliCommander*

### Renaming a single file/directory

*Renaming a single file*

![Rename file](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-5-0a_rename-single.png)

A simple dialog box to set new file (or directory) name\
(I don't really like to rename items directly into file explorer...)


### Renaming multiple files/directories

> **Note:**
> Multiples files *OR* mulitples directories can be renamed at the same time, not the both
> If files and directories are selected, function is not available

The renaming functionnality provides a set of functions and keywords to build new file name.\
The dedicated *expression language* tries to be as simple as possible, to let non developper being able to use it.

Interface provides an editor with:
 - Highlighted syntax
 - Autocompletion popup with basic help
 - Syntax validator
 - Preview for *Original file name > New file name* renaming


*Renaming multiple files: syntax not valid example*

![Rename file](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-5-0a_rename-multi01.png)


*Renaming multiple files: autocompletion&help example*

![Rename file](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-5-0a_rename-multi02.png)


*Renaming multiple files: renaming rules example*

![Rename file](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-5-0a_rename-multi03.png)


Available *function* list:
- `[upper:<value>]`
- `[lower:<value>]`
- `[capitalize:<value>]`
- `[camelize:<value>]`
- `[replace:<value>, "<search>", "<replace>"]`
- `[regex:<value>, "<pattern>"]`
- `[regex:<value>, "<pattern>", "<replace>"]`
- `[index:<value>, "<separator>", <index>]`
- `[sub:<value>, <start>]`
- `[sub:<value>, <start>, <length>]`
- `[len:<value>]`

Available *keyword* list:
- `{file:baseName}`
- `{file:ext}`
- `{file:path}`
- `{file:format}`
- `{file:date}`
- `{file:date:yyyy}`
- `{file:date:mm}`
- `{file:date:dd}`
- `{file:time}`
- `{file:time:hh}`
- `{file:time:mm}`
- `{file:time:ss}`
- `{file:hash:md5}`
- `{file:hash:sha1}`
- `{file:hash:sha256}`
- `{file:hash:sha512}`
- `{image:size}`
- `{image:size:width}`
- `{image:size:width:####}`
- `{image:size:height}`
- `{image:size:height:####}`
- `{date}`
- `{date:yyyy}`
- `{date:mm}`
- `{date:dd}`
- `{time}`
- `{time:hh}`
- `{time:mm}`
- `{time:ss}`
- `{counter}`
- `{counter:####}`


## Implement tool *Convert files*

The convert tool allows to convert multiples KRA/PNG/JPEG files to KRA/PNG/JPEG files.
- Target format PNG/JPEG provides similar options than Krita *export* option (modulo: EXIF/IPTC are not managed)
- Target file name can be defined from rules, allowing to set or not, the same base file name than original file\
  => Use the same *expression language* than one defined for renaming files
- If target already exist, file conversion is automatically skipped

> **Note:**
>
> This functionnality is slow compared to some tools like *imagemagick* (this might be relative to internal Krita opening/export process..?)
>
> Do not consider this as the best way to made conversion `PNG -> JPEG` or `JPEG -> PNG`: tool is mostly here to convert `KRA -> PNG/JPEG` or `PNG/JPEG -> KRA`


*Perimeter to convert + target file format options*

![Perimeter to convert + target file format options](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-5-0a_convert_options.png)


*Target directory*

![Target directory](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-5-0a_convert_target.png)


## Implement context menu for directories tree

Add a simple context menu that allow to expand/collapse all subdirectories


## Implement shortcut for quick filter

Panel's quick filter can be activated/deactivated through `CTRL + SHIFT + F` shortcut


## Improve Krita image information - *Used fonts list*

Image information panel provides for Krita file the list of used fonts.

If a font is missing on system, font is highlighted.

*Used font list (all OK) example*

![Font list - ok](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-5-0a_infopanel_font_ok.png)


*Used font list (KO) example*

![Font list - ko](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-5-0a_infopanel_font_ko.png)


## Improve Krita image information - *Embedded palettes*

Image information panel provides for Krita file the list of embedded palettes.
Information is "minimal":
- Palette name
- Palette dimension
- Number of colors

> Note: Palette preview is not provided

![Embedded palette example](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-5-0a_infopanel_embeddedpalettes.png)


## Improve Krita Export file list - *Square paper sizes*

Add some new paper sizes with *Square* format.


## Improve Krita Export file list - *Thumbnail mode*

Add possibility to define how image are drawn in thumbnail area:
- Fit mode: entire image is drawn (default mode)
- Crop mode: image is cropped for a better composition


*Image fit mode*

![Export file list - image fit](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-5-0a_exportlist_imgfit.png)


*Image crop mode*

![Export file list - image crop](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-5-0a_exportlist_imgcrop.png)

## Fix bug -  *cropped path bar*

Tried to fix this annoying bug, it should be Ok now... I hope :-)

*Cropped path bar*

![Cropped path bar](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-5-0a_bug-croppedpathbar.png)


## Fix bug - *Invalid font*

For an unknown reason, some user interface were defined with a local installed font instead of embedded Qt 'DejaVu Sans' font.\
Fixed this problem.

## Fix bug - *Invalid key configuration*

A bad copy/paste to manage automated saved settings for *Export file list* tool and pouf, script was crashing when trying to export files to PNG/JPEG file format.\
Fixed this problem.
