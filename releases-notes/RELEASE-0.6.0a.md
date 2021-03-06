# Buli Commander :: Release 0.6.0a [2020-12-29]


## Implement *Clipboard manager*

Clipboard panel catch and store clipboard content, allowing it to be re-used later.

Are managed from clipboard:
- Krita layers
- Krita selections
- Raster images
- Vector images
- Files (KRA, JPEG, PNG, GIF, WEBP, SVG)
- Url (KRA, JPEG, PNG, GIF, WEBP, SVG)

![Clipboard cache](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-6-0a_clipboard-manager.png)

### Clipboard functions

Items in clipboard manager can be:
- Pushed back to clipboard
- Pasted as new layer
- Pasted as new document
- Pasted as reference image
- Opened (available only for files)
- Switched from _session cache_ <> _persistent cache_

### Clipboard settings

![Clipboard settings](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-6-0a_clipboard-settings.png)

The _Manage clipboard content_ settings defines the way _Buli Commander_ works with clipboard:
- **Always**: data set to clipboard are stored by manager, even when _Buli Commander_ is closed
- **When active**: data set to clipboard are stored by manager when _Buli Commander_ is opened
- **Manually**: data set to clipboard are stored on user action

> **Note:** When _Buli Commander_ is configured to be available in system tray, clipboard management can be temporary de-activated
>
> ![Clipboard settings](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-6-0a_clipboard-systray-options.png)


#### Option _Parse Text and HTML content for URLs_
When checked, all text content copied to clipboard is parsed to find image URLs; when found items are added to manager.

#### Option _Automatically download from URLs_
When checked, URLs added to manager a downloaded automatically, otherwise user have to execute download manually.

#### Option _Use persistent cache_
By default, clipboard content is stored in a session cache, cleared on each Krita startup.
When checked, clipboard content is stored automatically in a cache for which data is kept over sessions.

#### Option _Paste as new document when no document is active_
When checked, _paste_ action **from Buli Commander** create a new document if there's no active document.


### Clipboard cache

Session cache and/or persistent cache can be cleared at any moment from settings dialog box.

![Clipboard cache](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-6-0a_clipboard-settings-cache.png)


## Implement function *Open file as reference image*

File can now be opened as reference image.

## Implement tool *Copy to clilboard*

This tools allows to copy selected files to clipboard:
- In a text editor, paste list of selected path/file names
- In a file manager, paste selected path/file names
- In an image editor, paste image (last image from selected file, if more than one file is selected)

## Improve Krita image information - *Reference images*

Image information panel provides for Krita file the list of references images:
- Reference image size
- Reference image thumbnail

![Reference image information](https://github.com/Grum999/BuliCommander/raw/master/screenshots/r0-6-0a_infopanel-refimg.jpeg)

> Note: A click on image reference allows to open it as a new document

## Improve UI - *Context menu*

Add context menu to files panel



## Fix bug - *Active panel not highlighted*

Path bar in active panel wasn't highlighted systematically.\
Problem should now be fixed.
