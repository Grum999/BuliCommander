# Buli Commander

An [orthodox file manager](https://en.wikipedia.org/wiki/File_manager#Orthodox_file_managers) plugin for [Krita](https://krita.org).


## What is Buli Commander?
*Buli Commander* is a Python plugin made for [Krita](https://krita.org) (free professional and open-source painting program).


Initially, my idea was to implement my own open dialog box to replace the default one from [Krita](https://krita.org),
because the default one doesn't satisfy me:
- No file preview
- No file information

As I'm used to work with orthodox file managers like [Midnight Commander](https://midnight-commander.org/) and
[Krusader](https://krusader.org/), I finally decided to implement my own open dialog box in this way.


## Disclaimer
> **Please note that current version is a pretty early preview version**

While *Buli Commander* version is not published under version 1.0.0, please take in consideration the following points:
- There's bugs, some of them are known, some are not (yet?) known
- Implementation can be rewritten, so a bug can disappear naturally on next version... or not :-)
- All functionalities are not yet implemented or not yet fully implemented
- Current user interface and current functionalities are not definitive and can be changed on next version

>Please also note that, as plugin is not yet finished and **not yet fully tested**, it's not recommended to use it on a
>[Krita](https://krita.org) installation used for a production workflow: test it/use it on a testing installation


## Screenshots
_Main user interface: dual panel mode_

![Main interface-dual panel mode](https://github.com/Grum999/BuliCommander/raw/master/screenshots/main_interface.png)

_Main user interface: single panel mode_

![Main interface-single panel mode](https://github.com/Grum999/BuliCommander/raw/master/screenshots/main_interface_singlepanel.png)

_Settings interface: navigation_

![Settings interface-Navigation](https://github.com/Grum999/BuliCommander/raw/master/screenshots/settings_navigation.png)


_Settings interface: images default action_

![Settings interface-Images](https://github.com/Grum999/BuliCommander/raw/master/screenshots/settings_imagefiles.png)



## Functionalities

Here a list of some functionalities:
- Dual panel interface, with different possible layouts
- Intuitive navigation bar:
 - Home directory
 - Previous directory
 - Up directory
 - Manual input (ie: just type path by yourself) or Breadcrumbs mode
- Directories tree
- Bookmarks management
- Views management (ie: select files, add them to a view without moving file and create your own list of files)
- Improved last opened/saved documents access
- Quick filtering (use of wildcard and/or regular expression)
- Show/hide backup files
- Show/hide Krita managed files only
- Image file information
  - File properties
  - Image properties (format, dimension, mode/depth, profile)
  - Krita image properties (About + Author)
- File manipulation (copy, move, delete)
- Miscellaneous opening modes
  - Improved GIF/WEBP import file


## Download, Install & Execute

### Download
+ **[ZIP ARCHIVE - v0.3.0a](https://github.com/Grum999/BuliCommander/releases/download/0.3.0a/bulicommander.zip)**
+ **[SOURCE](https://github.com/Grum999/BuliCommander)**


### Installation

Plugin installation in [Krita](https://krita.org) is not intuitive and needs some manipulation:

1. Open [Krita](https://krita.org) and go to **Tools** -> **Scripts** -> **Import Python Plugins...** and select the **bulicommander.zip** archive and let the software handle it.
2. Restart [Krita](https://krita.org)
3. To enable *Buli Commander* go to **Settings** -> **Configure Krita...** -> **Python Plugin Manager** and click the checkbox to the left of the field that says **Buli Commander**.
4. Restart [Krita](https://krita.org)

### Execute
When you want to execute *Buli Commander*, simply go to **Tools** -> **Scripts** and select **Buli Commander**.


### Tested platforms
Plugin has been tested with Krita 4.3.0 (appimage) on Linux Debian 10

Currently don't kwow if plugin works on Windows and MacOs.
I think it should be Ok, because of use of python and PyQt high level and multi OS file system functions, but...


## Plugin's life

### What's new?
_[2020-09-27] Version 0.3.0a_
- Implement progress bar on background thumbnail load
- Implement progress bar on directory file content analysis
- Fix bug on Setting "cache" tab
- Add "copy" context menu on information panel
- Improve "Open as new" function
- Update theme loading (when user change Krita's interface theme, reload properly BC theme)
- Implement and improve copy/move/delete function



_[2020-09-11] Version 0.2.0a_
- ORA file preview use (if exists) merged image preview instead of thumbnail
- Add BACKUP files list linked to a file
- Add FILE LAYERS files list linked to a KRA image
- Improve backup extension file management (take in account suffix from Krita setting + numbered backup files)

_[2020-09-05] Version 0.1.1a_
- Fix a dependency to unexisting library

_[2020-09-05] Version 0.1.0a_
- First public version


### Bugs
Yes, we have.



### What’s next?
Not able to define precisely in which order functionalities will be implemented, neither when, but here a list of what is currently expected for final 1.0.0 version:
- File(s) rename
- Shortcut to launch *Buli Commander*
- Possibility (as an option) to replace current Open dialog box with *Buli Commander*
- Generate and display thumbnails with ICC profile taken in account
- Add a gridview mode
- Implement *Search* tool
- Implement batch tool conversion
- Implement *Documents* tab
- Implement *Clipoard* tab
- Add context menu
- Add opening modes


## License

### *Buli Commander* is released under the GNU General Public License (version 3 or any later version).

*Buli Commander* is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or any later version.

*Buli Commander* is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should receive a copy of the GNU General Public License along with *Buli Commander*. If not, see <https://www.gnu.org/licenses/>.


Long story short: you're free to download, modify as well as redistribute *Buli Commander* as long as this ability is preserved and you give contributors proper credit. This is the same license under which Krita is released, ensuring compatibility between the two.
