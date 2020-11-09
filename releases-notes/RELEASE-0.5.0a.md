# Buli Commander :: Release 0.5.0a [YYYY-MM-DD]


## Implement tool *Convert files*

The convert tool allows to convert multiples KRA/PNG/JPEG files to KRA/PNG/JPEG files.
- Target format PNG/JPEG provides similar options than Krita *export* option (modulo: EXIF/IPTC are not managed)
- Target file name can be defined with markup (allowing to set, or not, the same base filename than original file)
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

