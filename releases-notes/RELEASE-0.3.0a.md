# Buli Commander :: Release 0.3.0a [2020-09-27]

> ### Note: due to use of specific Krita’s API introduced with Krita 4.4.0, this version is not compatible with Krita 4.3.0 and other previous versions


## Implement progress bar on directory file content analysis
When there’s many files (hundred or more) reading files information (image size) cant take time: in this case, a progress bar is displayed while files are analyzed.

![Directory content analysis progress](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-3-0a_progress-analysis.png)


## Implement progress bar on background thumbnail load
When there’s many files (hundred or more) generating and/or loading cache thumbnails can take time: in this case, a progress bar is displayed while thumbnail are loaded in background.

![Thumbnails loading progress](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-3-0a_progress-thumbload.png)


## Add a *copy to clipboard* context menu on information panel

A right click on image information panel display a context menu to easily copy information to clipboard.

![Information panel - context menu](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-3-0a_infopanel-ctxmenu.png)

*Text result copied in clipboard:*
```
[ Image ]
╔═══════════╤══════════════════════════════════════╗
║Property   │Value                                 ║
╠═══════════╪══════════════════════════════════════╣
║Format     │Krita native image                    ║
╟───────────┼──────────────────────────────────────╢
║Size       │6201x8770                             ║
║Resolution │600.00ppi                             ║
╟───────────┼──────────────────────────────────────╢
║Mode       │RGB with Alpha                        ║
║Depth      │8-bit integer/channel                 ║
║Profile    │sRGB-elle-V2-srgbtrc.icc              ║
╟───────────┼──────────────────────────────────────╢
║Animated   │No                                    ║
╟───────────┼──────────────────────────────────────╢
║Layers     │78                                    ║
╟───────────┼──────────────────────────────────────╢
║File layers│3 file layers found                   ║
╟───────────┼──────────────────────────────────────╢
║File layer │chinese-girl-head.kra                 ║
║Modified   │-                                     ║
║File size  │-                                     ║
║Image size │-                                     ║
╟───────────┼──────────────────────────────────────╢
║File layer │chinese-girl--dress-phoenix.kra       ║
║Modified   │2020-06-21 12:10:43                   ║
║File size  │34.64MiB (36318374)                   ║
║Image size │1650x1597                             ║
╟───────────┼──────────────────────────────────────╢
║File layer │chinese-girl--dress-middle-flowers.kra║
║Modified   │2020-03-14 23:49:12                   ║
║File size  │8.30MiB (8703876)                     ║
║Image size │1446x2433                             ║
╚═══════════╧══════════════════════════════════════╝
```


## Improve “Open as new” function
When opening a document “as new document”, BuliCommander can now define automatically the file name of new created document, according to defined pattern.

![Open as settings](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-3-0a_settings.png)


## Implement and improve copy/move/delete function

> Note: copy/move function is now working properly, but it still recommended to not use it with production work as more tests still need to be made

Confirmation of action allows to display detailed information about what will be copied/moved/deleted.

*Example of confirmation dialog box for copy and delete actions*

![Progress Analysis](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-3-0a_copyfiles_dialog.png)

![Progress Analysis](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-3-0a_deletefiles_dialog.png)


*Copy in action*

![Progress Analysis](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-3-0a_copyfiles_progress.png)


For copy/move action, when a target file already exists, a choice is asked to user with the following possibilities:

* Directory:
  * Rename directory
    * Write into existing directory
    * Skip action for the directory
  * File:
    * Rename file
    * Overwrite existing file
    * Skip action for the file

Renaming option allows use of pattern (like for “Open as new” configuration) to apply automatically a new name for file.

*Target directory exist example*

![Progress Analysis](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-3-0a_copyfiles_alreadyexists.png)

*Target file exist example*

![Progress Analysis](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-3-0a_copyfiles_alreadyexists2.jpeg)


## Update theme loading

When user change Krita’s interface theme, theme is now properly applied to Buli Commander.

![Progress Analysis](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-3-0a_theme_change.webp)


## Fix a bug on Setting “cache” tab

Cache information wasn’t updated properly: it’s now fixed :-)




